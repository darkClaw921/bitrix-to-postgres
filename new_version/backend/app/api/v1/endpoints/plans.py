"""Plan (target value) endpoints.

Implements ``/api/v1/plans`` — CRUD over the ``plans`` table, the
``/{plan_id}/vs-actual`` analytics endpoint and two small meta-endpoints
(``/meta/tables``, ``/meta/numeric-fields``) consumed by the frontend
form when the user picks a table and a numeric field.

Domain logic lives in :class:`app.domain.services.plan_service.PlanService`;
this module is a thin HTTP layer translating service exceptions into
``HTTPException`` with the appropriate status code.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import text

from app.api.v1.schemas.plans import (
    NumericFieldInfo,
    NumericFieldsResponse,
    PlanCreateRequest,
    PlanResponse,
    PlanUpdateRequest,
    PlanVsActualResponse,
    TableInfo,
    TablesResponse,
    plan_row_to_response,
)
from app.core.logging import get_logger
from app.domain.services.plan_service import (
    NUMERIC_DATA_TYPES,
    PlanConflictError,
    PlanNotFoundError,
    PlanService,
    PlanServiceError,
    PlanValidationError,
)
from app.infrastructure.database.connection import get_dialect, get_engine

logger = get_logger(__name__)

router = APIRouter()

plan_service = PlanService()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _raise_for_service_error(exc: PlanServiceError) -> None:
    """Translate a PlanService exception into the appropriate HTTPException."""
    if isinstance(exc, PlanNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, PlanConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, PlanValidationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Unknown PlanServiceError subclass — surface as 500.
    raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=PlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_plan(payload: PlanCreateRequest) -> PlanResponse:
    """Create a new plan row.

    Validates the referenced table/column (must exist and be numeric) and
    the period mode (fixed vs custom) inside ``PlanService``.
    """
    try:
        row = await plan_service.create_plan(payload.model_dump())
    except PlanServiceError as exc:
        logger.warning("create_plan failed", error=str(exc))
        _raise_for_service_error(exc)

    return plan_row_to_response(row)


@router.get("", response_model=list[PlanResponse])
async def list_plans(
    table_name: Optional[str] = Query(None),
    field_name: Optional[str] = Query(None),
    assigned_by_id: Optional[str] = Query(None),
    period_type: Optional[str] = Query(None),
) -> list[PlanResponse]:
    """Return plans, optionally filtered by table/field/assignee/period_type."""
    filters = {
        "table_name": table_name,
        "field_name": field_name,
        "assigned_by_id": assigned_by_id,
        "period_type": period_type,
    }
    rows = await plan_service.list_plans(filters)
    return [plan_row_to_response(r) for r in rows]


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(plan_id: int) -> PlanResponse:
    """Return a single plan by id, or 404 if it does not exist."""
    row = await plan_service.get_plan(plan_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return plan_row_to_response(row)


@router.put("/{plan_id}", response_model=PlanResponse)
async def update_plan(plan_id: int, payload: PlanUpdateRequest) -> PlanResponse:
    """Update an existing plan.

    Supports both partial (``plan_value`` / ``description`` only) and full
    updates (including the logical key: table/field/period/assignee). The
    service re-validates the numeric column and period mode on full
    updates and raises 409 if the new logical key collides with another
    plan.
    """
    # Only forward fields that were actually provided so that the service
    # layer can distinguish "not touched" from "explicitly set to None".
    update_payload = payload.model_dump(exclude_unset=True)
    try:
        row = await plan_service.update_plan(plan_id, update_payload)
    except PlanServiceError as exc:
        logger.warning("update_plan failed", plan_id=plan_id, error=str(exc))
        _raise_for_service_error(exc)

    return plan_row_to_response(row)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(plan_id: int) -> Response:
    """Delete a plan. Returns 204 on success, 404 if the plan does not exist."""
    deleted = await plan_service.delete_plan(plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Analytics — plan vs actual
# ---------------------------------------------------------------------------


@router.get("/{plan_id}/vs-actual", response_model=PlanVsActualResponse)
async def get_plan_vs_actual(plan_id: int) -> PlanVsActualResponse:
    """Return the plan/actual/variance snapshot for a single plan.

    The service materialises the period bounds and sums the referenced
    numeric column over that range (respecting ``assigned_by_id`` when set).
    """
    try:
        result = await plan_service.get_plan_vs_actual(plan_id)
    except PlanServiceError as exc:
        logger.warning("get_plan_vs_actual failed", plan_id=plan_id, error=str(exc))
        _raise_for_service_error(exc)

    return PlanVsActualResponse(
        plan_id=result["plan_id"],
        plan_value=result["plan_value"],
        actual_value=result["actual_value"],
        variance=result["variance"],
        variance_pct=result["variance_pct"],
        period_effective_from=result["date_from"],
        period_effective_to=result["date_to"],
    )


# ---------------------------------------------------------------------------
# Meta — tables + numeric fields for the UI form
# ---------------------------------------------------------------------------


# Table name prefixes considered "allowed" for plan creation — mirrors the
# whitelist used by ``ChartService.get_allowed_tables`` so that the plan
# form only offers tables the rest of the app can actually query.
_ALLOWED_TABLE_PREFIXES: tuple[str, ...] = (
    "crm_",
    "ref_",
    "bitrix_",
    "stage_history_",
)


@router.get("/meta/tables", response_model=TablesResponse)
async def list_plan_tables() -> TablesResponse:
    """Return the list of tables available as plan targets.

    Reads ``information_schema.tables`` directly (dialect-aware) and keeps
    only the prefixes that are in ChartService's allow-list. The ``plans``
    table itself is excluded — you cannot create a plan of a plan.
    """
    engine = get_engine()
    dialect = get_dialect()

    if dialect == "mysql":
        query = text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE'"
        )
    else:  # postgresql / other
        query = text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = ANY (current_schemas(false)) "
            "AND table_type = 'BASE TABLE'"
        )

    async with engine.begin() as conn:
        rows = (await conn.execute(query)).fetchall()

    names = sorted(
        {
            r[0]
            for r in rows
            if r[0]
            and r[0] != "plans"
            and r[0].startswith(_ALLOWED_TABLE_PREFIXES)
        }
    )

    return TablesResponse(tables=[TableInfo(name=n) for n in names])


@router.get("/meta/numeric-fields", response_model=NumericFieldsResponse)
async def list_numeric_fields(
    table_name: str = Query(..., min_length=1, max_length=64),
) -> NumericFieldsResponse:
    """Return numeric columns of ``table_name`` suitable as a plan target.

    Uses ``PlanService._column_info`` under the hood and filters by the
    same ``NUMERIC_DATA_TYPES`` whitelist that ``create_plan`` validates
    against, so the list the UI shows is always a strict subset of what
    the backend will accept.
    """
    try:
        columns = await plan_service._column_info(table_name)
    except Exception as exc:  # pragma: no cover — defensive guard
        logger.error("list_numeric_fields failed", table_name=table_name, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not columns:
        raise HTTPException(
            status_code=404,
            detail=f"Table '{table_name}' not found or has no columns",
        )

    fields = [
        NumericFieldInfo(name=c["column_name"], data_type=c["data_type"])
        for c in columns
        if c["data_type"] in NUMERIC_DATA_TYPES
    ]
    fields.sort(key=lambda f: f.name)

    return NumericFieldsResponse(table_name=table_name, fields=fields)
