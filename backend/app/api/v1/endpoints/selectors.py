"""Selector management endpoints (internal, requires app auth)."""

import asyncio

from fastapi import APIRouter, HTTPException

from app.api.v1.schemas.selectors import (
    ChartColumnsResponse,
    ChartTablesResponse,
    FilterPreviewRequest,
    FilterPreviewResponse,
    GenerateSelectorsJobResponse,
    GenerateSelectorsRequest,
    GenerateSelectorsResponse,
    GenerateSelectorsStatusResponse,
    SelectorCreateRequest,
    SelectorListResponse,
    SelectorOptionsResponse,
    SelectorOptionItem,
    SelectorResponse,
    SelectorUpdateRequest,
)
from app.core.exceptions import AIServiceError, ChartServiceError
from app.core.job_store import create_job, get_job, update_job
from app.core.logging import get_logger
from app.domain.services.ai_service import AIService
from app.domain.services.chart_service import ChartService
from app.domain.services.dashboard_service import DashboardService
from app.domain.services.selector_service import SelectorService

logger = get_logger(__name__)

router = APIRouter()
selector_service = SelectorService()
chart_service = ChartService()
dashboard_service = DashboardService()
ai_service = AIService()


@router.post("/{dashboard_id}/selectors", response_model=SelectorResponse)
async def create_selector(
    dashboard_id: int, request: SelectorCreateRequest
) -> SelectorResponse:
    """Create a new selector for a dashboard."""
    selector = await selector_service.create_selector(
        dashboard_id=dashboard_id,
        name=request.name,
        label=request.label,
        selector_type=request.selector_type,
        operator=request.operator,
        config=request.config,
        sort_order=request.sort_order,
        is_required=request.is_required,
    )

    # Create mappings if provided
    if request.mappings:
        await selector_service._replace_mappings(
            selector["id"],
            [m.model_dump() for m in request.mappings],
        )
        selector = await selector_service.get_selector_by_id(selector["id"])

    return SelectorResponse(**selector)


@router.get("/{dashboard_id}/selectors", response_model=SelectorListResponse)
async def list_selectors(dashboard_id: int) -> SelectorListResponse:
    """Get all selectors for a dashboard."""
    selectors = await selector_service.get_selectors_for_dashboard(dashboard_id)
    return SelectorListResponse(
        selectors=[SelectorResponse(**s) for s in selectors]
    )


@router.put("/{dashboard_id}/selectors/{selector_id}", response_model=SelectorResponse)
async def update_selector(
    dashboard_id: int, selector_id: int, request: SelectorUpdateRequest
) -> SelectorResponse:
    """Update a selector (including full replace of mappings if provided)."""
    existing = await selector_service.get_selector_by_id(selector_id)
    if not existing or existing["dashboard_id"] != dashboard_id:
        raise HTTPException(status_code=404, detail="Селектор не найден")

    mappings_data = None
    if request.mappings is not None:
        mappings_data = [m.model_dump() for m in request.mappings]

    updated = await selector_service.update_selector(
        selector_id=selector_id,
        name=request.name,
        label=request.label,
        selector_type=request.selector_type,
        operator=request.operator,
        config=request.config,
        sort_order=request.sort_order,
        is_required=request.is_required,
        mappings=mappings_data,
    )

    if not updated:
        raise HTTPException(status_code=404, detail="Селектор не найден")

    return SelectorResponse(**updated)


@router.delete("/{dashboard_id}/selectors/{selector_id}")
async def delete_selector(dashboard_id: int, selector_id: int) -> dict:
    """Delete a selector."""
    existing = await selector_service.get_selector_by_id(selector_id)
    if not existing or existing["dashboard_id"] != dashboard_id:
        raise HTTPException(status_code=404, detail="Селектор не найден")

    deleted = await selector_service.delete_selector(selector_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Селектор не найден")
    return {"ok": True}


@router.get(
    "/{dashboard_id}/selectors/{selector_id}/options",
    response_model=SelectorOptionsResponse,
)
async def get_selector_options(
    dashboard_id: int, selector_id: int
) -> SelectorOptionsResponse:
    """Get options for a dropdown/multi-select selector."""
    existing = await selector_service.get_selector_by_id(selector_id)
    if not existing or existing["dashboard_id"] != dashboard_id:
        raise HTTPException(status_code=404, detail="Селектор не найден")

    options = await selector_service.get_selector_options(selector_id)
    return SelectorOptionsResponse(
        options=[SelectorOptionItem(**o) for o in options]
    )


@router.get(
    "/{dashboard_id}/charts/{dc_id}/columns",
    response_model=ChartColumnsResponse,
)
async def get_chart_columns(dashboard_id: int, dc_id: int) -> ChartColumnsResponse:
    """Get column names from a chart's SQL query."""
    columns = await selector_service.get_chart_columns(dc_id)
    return ChartColumnsResponse(columns=columns)


@router.get(
    "/{dashboard_id}/charts/{dc_id}/tables",
    response_model=ChartTablesResponse,
)
async def get_chart_tables(dashboard_id: int, dc_id: int) -> ChartTablesResponse:
    """Get table names from a chart's SQL query (FROM/JOIN clauses)."""
    tables = await selector_service.get_chart_tables(dc_id)
    return ChartTablesResponse(tables=tables)


@router.post(
    "/{dashboard_id}/charts/{dc_id}/preview-filter",
    response_model=FilterPreviewResponse,
)
async def preview_filter(
    dashboard_id: int, dc_id: int, request: FilterPreviewRequest
) -> FilterPreviewResponse:
    """Preview how a filter would modify a chart's SQL query."""
    result = await selector_service.preview_filter(
        dc_id=dc_id,
        target_column=request.target_column,
        operator=request.operator,
        target_table=request.target_table,
        sample_value=request.sample_value,
    )
    return FilterPreviewResponse(**result)


async def _run_generate_job(
    job_id: str,
    dashboard_id: int,
    charts: list[dict],
    request: GenerateSelectorsRequest | None,
) -> None:
    update_job(job_id, "running")
    try:
        charts_lines: list[str] = []
        for c in charts:
            try:
                cols = await selector_service.get_chart_columns(c["id"])
            except Exception:
                cols = []
            tables = await selector_service.get_chart_tables(c["id"])
            title = c.get("title_override") or c.get("chart_title") or "Chart"
            charts_lines.append(
                f"### dashboard_chart_id={c['id']} — {title}\n"
                f"Tables: {', '.join(tables) if tables else '(none)'}\n"
                f"Columns: {', '.join(cols) if cols else '(unknown)'}\n"
                f"SQL:\n```sql\n{c.get('sql_query', '')}\n```"
            )
        charts_context = "\n\n".join(charts_lines)

        try:
            latest = await chart_service.get_any_latest_schema_description()
            schema_context = (
                latest["markdown"]
                if latest and latest.get("markdown")
                else await chart_service.get_schema_context()
            )
        except Exception:
            schema_context = await chart_service.get_schema_context()

        user_request = request.user_request if request else None
        raw_selectors = await ai_service.generate_selectors(
            charts_context, schema_context, user_request=user_request
        )
        update_job(job_id, "done", result=raw_selectors)
    except Exception as e:
        logger.error("generate_selectors job failed", job_id=job_id, error=str(e))
        update_job(job_id, "error", error=str(e))


@router.post(
    "/{dashboard_id}/selectors/generate",
    response_model=GenerateSelectorsJobResponse,
    status_code=202,
)
async def generate_selectors(
    dashboard_id: int,
    request: GenerateSelectorsRequest | None = None,
) -> GenerateSelectorsJobResponse:
    """Queue an AI-generate job for selectors. Returns job_id; poll GET /selectors/generate/{job_id}."""
    dashboard = await dashboard_service.get_dashboard_by_id(dashboard_id)
    if not dashboard:
        raise HTTPException(status_code=404, detail="Дашборд не найден")

    charts = dashboard.get("charts") or []
    if not charts:
        raise HTTPException(status_code=400, detail="В дашборде нет чартов для анализа")

    if request and request.chart_ids:
        allowed_ids = set(request.chart_ids)
        charts = [c for c in charts if c.get("id") in allowed_ids]
        if not charts:
            raise HTTPException(
                status_code=400,
                detail="Ни один из выбранных чартов не найден в дашборде",
            )

    job_id = create_job()
    asyncio.create_task(_run_generate_job(job_id, dashboard_id, charts, request))
    return GenerateSelectorsJobResponse(job_id=job_id, status="pending")


@router.get(
    "/{dashboard_id}/selectors/generate/{job_id}",
    response_model=GenerateSelectorsStatusResponse,
)
async def get_generate_selectors_job(
    dashboard_id: int, job_id: str
) -> GenerateSelectorsStatusResponse:
    """Poll the status of a generate-selectors job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job не найден или истёк")

    if job["status"] in ("pending", "running"):
        return GenerateSelectorsStatusResponse(job_id=job_id, status=job["status"])

    if job["status"] == "error":
        return GenerateSelectorsStatusResponse(
            job_id=job_id, status="error", error=job["error"]
        )

    # done — coerce raw dicts into SelectorCreateRequest
    selectors: list[SelectorCreateRequest] = []
    for raw in job["result"] or []:
        try:
            selectors.append(SelectorCreateRequest(**raw))
        except Exception as e:
            logger.warning("Invalid selector from AI", error=str(e), raw=raw)

    return GenerateSelectorsStatusResponse(
        job_id=job_id, status="done", selectors=selectors
    )
