"""Plan (target value) endpoints.

Implements ``/api/v1/plans`` — CRUD over the ``plans`` table, batch
create, plan templates (CRUD + expand + apply), the
``/{plan_id}/vs-actual`` analytics endpoint, and meta-endpoints
(``/meta/tables``, ``/meta/numeric-fields``, ``/meta/managers``)
consumed by the frontend when the user picks a table, a numeric field,
or filters managers by department.

Domain logic lives in two services:

* :class:`app.domain.services.plan_service.PlanService` — CRUD over
  ``plans`` + ``batch_create_plans`` + analytics.
* :class:`app.domain.services.plan_template_service.PlanTemplateService` —
  CRUD over ``plan_templates`` + ``expand_template``.

This module is a thin HTTP layer translating service exceptions into
``HTTPException`` with the appropriate status code. Auth is applied at
the router level (see ``app/api/v1/__init__.py``); endpoints that need
the authenticated user id pull it via ``Depends(get_current_user)``.
"""

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import text

from app.api.v1.schemas.plans import (
    NumericFieldInfo,
    NumericFieldsResponse,
    PlanAIGenerateRequest,
    PlanAIGenerateResponse,
    PlanBatchCreateRequest,
    PlanCreateRequest,
    PlanDraft,
    PlanManagerInfo,
    PlanManagersResponse,
    PlanResponse,
    PlanTemplateApplyRequest,
    PlanTemplateCreateRequest,
    PlanTemplateExpandRequest,
    PlanTemplateResponse,
    PlanTemplateUpdateRequest,
    PlanUpdateRequest,
    PlanVsActualResponse,
    TableInfo,
    TablesResponse,
    plan_row_to_response,
)
from app.config import get_settings
from app.core.auth import get_current_user
from app.core.exceptions import AIServiceError
from app.core.logging import get_logger
from app.domain.services.chart_service import ChartService
from app.domain.services.department_service import DepartmentService
from app.domain.services.plan_service import (
    NUMERIC_DATA_TYPES,
    PlanConflictError,
    PlanNotFoundError,
    PlanService,
    PlanServiceError,
    PlanValidationError,
)
from app.domain.services.plan_template_service import (
    PlanTemplateConflictError,
    PlanTemplateNotFoundError,
    PlanTemplateService,
    PlanTemplateServiceError,
    PlanTemplateValidationError,
)
from app.domain.services.plans_ai_service import PlansAIService
from app.infrastructure.database.connection import get_dialect, get_engine

logger = get_logger(__name__)

router = APIRouter()

plan_service = PlanService()
plan_template_service = PlanTemplateService()
chart_service = ChartService()
plans_ai_service = PlansAIService(plan_service=plan_service)


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


def _raise_for_template_error(exc: PlanTemplateServiceError) -> None:
    """Translate a PlanTemplateService exception into an HTTPException."""
    if isinstance(exc, PlanTemplateNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, PlanTemplateConflictError):
        # Используем 400 для builtin-блокировок (это бизнес-правило, а не
        # дубликат), как и указано в acceptance criteria задачи. 409 тут
        # не подходит — нет конфликта ресурсов.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, PlanTemplateValidationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
    assigned_by_id: Optional[List[str]] = Query(None),
    period_type: Optional[str] = Query(None),
    period_value: Optional[str] = Query(None),
) -> list[PlanResponse]:
    """Return plans, optionally filtered by table/field/assignee(s)/period_type/period_value.

    ``assigned_by_id`` may be repeated to filter by multiple managers:
    ``?assigned_by_id=1&assigned_by_id=2``.
    """
    filters: dict[str, Any] = {
        "table_name": table_name,
        "field_name": field_name,
        "period_type": period_type,
        "period_value": period_value,
    }
    if assigned_by_id:
        filters["assigned_by_ids"] = assigned_by_id
    rows = await plan_service.list_plans(filters)
    return [plan_row_to_response(r) for r in rows]


# ---------------------------------------------------------------------------
# Batch create (defined BEFORE /{plan_id} so the literal path wins)
# ---------------------------------------------------------------------------


@router.post(
    "/batch",
    response_model=list[PlanResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_plans_batch(
    payload: PlanBatchCreateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> list[PlanResponse]:
    """Create many plans in one transaction.

    All-or-nothing: any validation error or logical duplicate rolls back
    the whole batch. ``created_by_id`` is taken from the JWT (``user.id``)
    and applied uniformly to every plan. Mirrors the validation rules of
    :func:`create_plan` — :class:`PlanValidationError` → 400,
    :class:`PlanConflictError` → 409.
    """
    raw_plans = [p.model_dump() for p in payload.plans]
    created_by_id = user.get("id") if user else None

    try:
        rows = await plan_service.batch_create_plans(
            raw_plans, created_by_id=created_by_id
        )
    except PlanServiceError as exc:
        logger.warning("batch_create_plans failed", error=str(exc))
        _raise_for_service_error(exc)

    return [plan_row_to_response(r) for r in rows]


# ---------------------------------------------------------------------------
# Plan templates CRUD + expand + apply (defined BEFORE /{plan_id})
# ---------------------------------------------------------------------------


@router.get("/templates", response_model=list[PlanTemplateResponse])
async def list_plan_templates() -> list[PlanTemplateResponse]:
    """Return all plan templates (including builtin), oldest first."""
    templates = await plan_template_service.list_templates()
    return [
        PlanTemplateResponse.model_validate(t, from_attributes=True)
        for t in templates
    ]


@router.post(
    "/templates",
    response_model=PlanTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_plan_template(
    payload: PlanTemplateCreateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> PlanTemplateResponse:
    """Create a user-defined plan template.

    ``is_builtin`` is forced to ``False`` by the service — this endpoint
    cannot be used to create builtin entries (those are seeded by the
    migration).
    """
    created_by_id = user.get("id") if user else None
    try:
        template = await plan_template_service.create_template(
            payload, created_by_id=created_by_id
        )
    except PlanTemplateServiceError as exc:
        logger.warning("create_plan_template failed", error=str(exc))
        _raise_for_template_error(exc)

    return PlanTemplateResponse.model_validate(template, from_attributes=True)


@router.get(
    "/templates/{template_id}", response_model=PlanTemplateResponse
)
async def get_plan_template(template_id: int) -> PlanTemplateResponse:
    """Return a single template by id, or 404 if it does not exist."""
    template = await plan_template_service.get_template(template_id)
    if template is None:
        raise HTTPException(
            status_code=404, detail=f"Template {template_id} not found"
        )
    return PlanTemplateResponse.model_validate(template, from_attributes=True)


@router.put(
    "/templates/{template_id}", response_model=PlanTemplateResponse
)
async def update_plan_template(
    template_id: int,
    payload: PlanTemplateUpdateRequest,
) -> PlanTemplateResponse:
    """Partial update of a template.

    For builtin templates, changing ``name`` / ``period_mode`` /
    ``assignees_mode`` is rejected with 400 — these fields define the
    semantics of the builtin and must stay stable.
    """
    try:
        template = await plan_template_service.update_template(
            template_id, payload
        )
    except PlanTemplateServiceError as exc:
        logger.warning(
            "update_plan_template failed",
            template_id=template_id,
            error=str(exc),
        )
        _raise_for_template_error(exc)

    return PlanTemplateResponse.model_validate(template, from_attributes=True)


@router.delete(
    "/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_plan_template(template_id: int) -> Response:
    """Delete a template. Returns 400 for builtin, 404 if not found."""
    try:
        await plan_template_service.delete_template(template_id)
    except PlanTemplateServiceError as exc:
        logger.warning(
            "delete_plan_template failed",
            template_id=template_id,
            error=str(exc),
        )
        _raise_for_template_error(exc)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/templates/{template_id}/expand",
    response_model=list[PlanDraft],
)
async def expand_plan_template(
    template_id: int,
    payload: Optional[PlanTemplateExpandRequest] = None,
) -> list[PlanDraft]:
    """Expand a template into per-manager plan drafts.

    Payload is optional — without it, the template is expanded as-is.
    With it, the caller can override ``table_name`` / ``field_name``
    (required for builtin templates with NULL-target) and
    ``period_value``.
    """
    overrides: dict[str, Any] = {}
    if payload is not None:
        if payload.table_name is not None:
            overrides["table_name"] = payload.table_name
        if payload.field_name is not None:
            overrides["field_name"] = payload.field_name
        if payload.period_value is not None:
            overrides["period_value"] = payload.period_value

    try:
        drafts = await plan_template_service.expand_template(
            template_id, overrides=overrides
        )
    except PlanTemplateServiceError as exc:
        logger.warning(
            "expand_plan_template failed",
            template_id=template_id,
            error=str(exc),
        )
        _raise_for_template_error(exc)

    return drafts


@router.post(
    "/templates/{template_id}/apply",
    response_model=list[PlanResponse],
    status_code=status.HTTP_201_CREATED,
)
async def apply_plan_template(
    template_id: int,
    payload: PlanTemplateApplyRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> list[PlanResponse]:
    """Apply a template — convert entries to plans via transactional batch.

    After expand+edit on the UI, the caller sends the final list of
    ``PlanDraft`` entries back; this endpoint maps them into
    :class:`PlanCreateRequest` and delegates to
    :func:`PlanService.batch_create_plans` (same all-or-nothing
    semantics as ``POST /plans/batch``).

    The ``template_id`` in the path must match the one in the payload
    (a guard against copy-paste / form-state mistakes on the client).
    """
    if payload.template_id != template_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "template_id in path and body mismatch "
                f"({template_id} vs {payload.template_id})"
            ),
        )

    # Make sure the template actually exists — surfaces a clean 404
    # before we start mapping entries.
    template = await plan_template_service.get_template(template_id)
    if template is None:
        raise HTTPException(
            status_code=404, detail=f"Template {template_id} not found"
        )

    # For each draft: resolve effective table/field (override → draft →
    # template), then map to the plans schema.
    plans_payloads: list[dict[str, Any]] = []
    for idx, draft in enumerate(payload.entries):
        table_name = (
            payload.table_name
            or draft.table_name
            or template.table_name
        )
        field_name = (
            payload.field_name
            or draft.field_name
            or template.field_name
        )
        if not table_name or not field_name:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Entry #{idx}: table_name/field_name is required "
                    f"(builtin template needs an override)"
                ),
            )

        if draft.plan_value is None:
            raise HTTPException(
                status_code=400,
                detail=f"Entry #{idx}: plan_value is required",
            )

        plans_payloads.append(
            {
                "table_name": table_name,
                "field_name": field_name,
                "assigned_by_id": draft.assigned_by_id,
                "period_type": draft.period_type,
                "period_value": (
                    payload.period_value_override or draft.period_value
                ),
                "date_from": draft.date_from,
                "date_to": draft.date_to,
                "plan_value": draft.plan_value,
                "description": draft.description,
            }
        )

    created_by_id = user.get("id") if user else None

    try:
        rows = await plan_service.batch_create_plans(
            plans_payloads, created_by_id=created_by_id
        )
    except PlanServiceError as exc:
        logger.warning(
            "apply_plan_template failed",
            template_id=template_id,
            error=str(exc),
        )
        _raise_for_service_error(exc)

    logger.info(
        "plan_template applied",
        template_id=template_id,
        created_plans=len(rows),
    )

    return [plan_row_to_response(r) for r in rows]


# ---------------------------------------------------------------------------
# AI generation — preview drafts from a natural-language description (Phase 3)
# ---------------------------------------------------------------------------


@router.post("/ai-generate", response_model=PlanAIGenerateResponse)
async def ai_generate_plans(
    payload: PlanAIGenerateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> PlanAIGenerateResponse:
    """Preview plan drafts generated by LLM from a free-form description.

    Эндпоинт НЕ пишет в БД — он возвращает набор
    :class:`PlanDraft`, который фронт показывает пользователю для
    правок, после чего сохранение идёт через ``POST /plans/batch``.

    Поведение ошибок:

    * Нет API-key (``AI_*`` env vars пустые) → **503** с
      ``AI service not configured``.
    * LLM вернул невалидный JSON → **502** (через
      :class:`AIServiceError`).
    * Нет актуального описания схемы (``GET /api/v1/schema/describe``
      ещё не запускался) → **400** с просьбой сначала сгенерировать
      схему (такое же поведение, как у ``POST /charts/generate``).
    * Любая другая ошибка LLM (connection, rate-limit) —
      :class:`AIServiceError` маппится в **502**.
    """
    settings = get_settings()
    if not (settings.openai_api_key or "").strip():
        raise HTTPException(
            status_code=503,
            detail="AI service not configured",
        )

    # Получаем свежий schema_context так же, как делает
    # ``POST /charts/generate`` — из уже сгенерированного описания схемы.
    schema_desc = await chart_service.get_any_latest_schema_description()
    if not schema_desc:
        raise HTTPException(
            status_code=400,
            detail=(
                "Сначала сгенерируйте описание схемы базы данных "
                "(GET /api/v1/schema/describe)."
            ),
        )
    schema_context = schema_desc["markdown"]

    # Подсказки: table/field пробрасываем только если заданы (None не
    # отличается от отсутствия ключа, см. ``PlansAIService._format_plans_hints``).
    hints: dict[str, Any] = {}
    if payload.table_name is not None:
        hints["table_name"] = payload.table_name
    if payload.field_name is not None:
        hints["field_name"] = payload.field_name

    try:
        response = await plans_ai_service.generate_and_expand(
            description=payload.description,
            schema_context=schema_context,
            hints=hints or None,
        )
    except AIServiceError as exc:
        logger.error("ai_generate_plans: AI error", error=exc.message)
        raise HTTPException(status_code=502, detail=exc.message) from exc
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover — defensive guard
        logger.exception(
            "ai_generate_plans: unexpected error", error=str(exc)
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.info(
        "ai_generate_plans: preview ready",
        user_id=(user or {}).get("id"),
        plans_count=len(response.plans),
        warnings_count=len(response.warnings),
    )

    return response


# ---------------------------------------------------------------------------
# Single-plan GET / PUT / DELETE — must come AFTER more specific paths.
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Meta — active managers (optionally filtered by department)
# ---------------------------------------------------------------------------


@router.get("/meta/managers", response_model=PlanManagersResponse)
async def list_plan_managers(
    department_id: Optional[str] = Query(
        None,
        description=(
            "bitrix_id отдела для фильтрации. Если не задан, возвращаются "
            "все активные пользователи из bitrix_users."
        ),
    ),
    recursive: bool = Query(
        True,
        description=(
            "Если True и задан department_id, включить также менеджеров "
            "всех подотделов (через DepartmentService.collect_descendant_ids)."
        ),
    ),
) -> PlanManagersResponse:
    """Return active managers, optionally filtered by department.

    Без ``department_id`` — все активные юзеры из ``bitrix_users``
    (``active='Y'``). C ``department_id`` — делегирует в
    ``DepartmentService.list_managers_in_departments``; при
    ``recursive=True`` подотделы добавляются через
    ``collect_descendant_ids``.
    """
    if department_id is None:
        # Без фильтра: все активные юзеры. Используем ту же форму
        # SELECT, что и PlanTemplateService — последовательность полей
        # совпадает с ``PlanManagerInfo``.
        engine = get_engine()
        async with engine.begin() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT bitrix_id, name, last_name, active "
                        "FROM bitrix_users "
                        "WHERE active IN ('Y', 'y', '1', 'true', 'TRUE') "
                        "OR active IS NULL "
                        "ORDER BY last_name, name, bitrix_id"
                    )
                )
            ).fetchall()

        managers = [
            PlanManagerInfo(
                bitrix_id=str(r[0]),
                name=r[1],
                last_name=r[2],
                active=r[3],
            )
            for r in rows
        ]
        return PlanManagersResponse(
            department_id=None,
            recursive=False,
            managers=managers,
        )

    # С фильтром по отделу — через DepartmentService.
    dept_service = DepartmentService()
    if recursive:
        dept_ids = await dept_service.collect_descendant_ids(department_id)
    else:
        dept_ids = [str(department_id)]

    if not dept_ids:
        # Отдел не найден — отдаём пустой список без 404 (UI-friendly).
        return PlanManagersResponse(
            department_id=str(department_id),
            recursive=recursive,
            managers=[],
        )

    raw_managers = await dept_service.list_managers_in_departments(
        dept_ids, active_only=True
    )

    return PlanManagersResponse(
        department_id=str(department_id),
        recursive=recursive,
        managers=[
            PlanManagerInfo(
                bitrix_id=m["bitrix_id"],
                name=m.get("name"),
                last_name=m.get("last_name"),
                active=m.get("active"),
            )
            for m in raw_managers
        ],
    )
