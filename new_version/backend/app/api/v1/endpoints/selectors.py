"""Internal endpoints for dashboard selector CRUD (dashboard editor)."""

from fastapi import APIRouter, HTTPException

from app.api.v1.schemas.selectors import (
    MappingCreateRequest,
    MappingResponse,
    SelectorCreateRequest,
    SelectorListResponse,
    SelectorOptionsResponse,
    SelectorResponse,
    SelectorUpdateRequest,
)
from app.core.exceptions import AIServiceError, DashboardServiceError
from app.core.logging import get_logger
from app.domain.services.ai_service import AIService
from app.domain.services.chart_service import ChartService
from app.domain.services.dashboard_service import DashboardService
from app.domain.services.selector_service import SelectorService

logger = get_logger(__name__)

router = APIRouter()
selector_service = SelectorService()
ai_service = AIService()
chart_service = ChartService()
dashboard_service = DashboardService()


@router.post("/{dashboard_id}/selectors", response_model=SelectorResponse)
async def create_selector(
    dashboard_id: int, request: SelectorCreateRequest
) -> SelectorResponse:
    """Create a new selector for a dashboard."""
    try:
        mappings = [m.model_dump() for m in request.mappings] if request.mappings else None
        selector = await selector_service.create_selector(
            dashboard_id=dashboard_id,
            name=request.name,
            label=request.label,
            selector_type=request.selector_type,
            operator=request.operator,
            config=request.config,
            sort_order=request.sort_order,
            is_required=request.is_required,
            mappings=mappings,
        )
        return SelectorResponse(**selector)
    except DashboardServiceError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    except Exception as e:
        if "uq_dashboard_selector_name" in str(e):
            raise HTTPException(
                status_code=409,
                detail=f"Селектор с именем '{request.name}' уже существует",
            ) from e
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{dashboard_id}/selectors", response_model=SelectorListResponse)
async def list_selectors(dashboard_id: int) -> SelectorListResponse:
    """List all selectors for a dashboard."""
    selectors = await selector_service.get_selectors_for_dashboard(dashboard_id)
    return SelectorListResponse(
        selectors=[SelectorResponse(**s) for s in selectors]
    )


@router.put("/{dashboard_id}/selectors/{selector_id}", response_model=SelectorResponse)
async def update_selector(
    dashboard_id: int, selector_id: int, request: SelectorUpdateRequest
) -> SelectorResponse:
    """Update a selector."""
    try:
        update_data = request.model_dump(exclude_unset=True)
        selector = await selector_service.update_selector(selector_id, **update_data)
        return SelectorResponse(**selector)
    except DashboardServiceError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.delete("/{dashboard_id}/selectors/{selector_id}")
async def delete_selector(dashboard_id: int, selector_id: int) -> dict:
    """Delete a selector and its mappings."""
    deleted = await selector_service.delete_selector(selector_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Селектор не найден")
    return {"ok": True}


@router.post(
    "/{dashboard_id}/selectors/{selector_id}/mappings",
    response_model=MappingResponse,
)
async def add_mapping(
    dashboard_id: int, selector_id: int, request: MappingCreateRequest
) -> MappingResponse:
    """Add a chart mapping to a selector."""
    try:
        mapping = await selector_service.add_mapping(
            selector_id=selector_id,
            dashboard_chart_id=request.dashboard_chart_id,
            target_column=request.target_column,
            target_table=request.target_table,
            operator_override=request.operator_override,
        )
        return MappingResponse(**mapping)
    except Exception as e:
        if "uq_selector_chart_mapping" in str(e):
            raise HTTPException(
                status_code=409,
                detail="Маппинг для этого чарта уже существует",
            ) from e
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{dashboard_id}/selectors/{selector_id}/mappings/{mapping_id}")
async def remove_mapping(
    dashboard_id: int, selector_id: int, mapping_id: int
) -> dict:
    """Remove a chart mapping from a selector."""
    deleted = await selector_service.remove_mapping(mapping_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Маппинг не найден")
    return {"ok": True}


@router.get(
    "/{dashboard_id}/selectors/{selector_id}/options",
    response_model=SelectorOptionsResponse,
)
async def get_selector_options(
    dashboard_id: int, selector_id: int
) -> SelectorOptionsResponse:
    """Get dropdown options for a selector."""
    try:
        options = await selector_service.get_selector_options(selector_id)
        return SelectorOptionsResponse(options=options)
    except DashboardServiceError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.get("/{dashboard_id}/charts/{dc_id}/columns")
async def get_chart_columns(dashboard_id: int, dc_id: int) -> dict:
    """Get column names from a dashboard chart's SQL query."""
    dashboard = await dashboard_service.get_dashboard_by_id(dashboard_id)
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    dc = next((c for c in dashboard["charts"] if c["id"] == dc_id), None)
    if not dc:
        raise HTTPException(status_code=404, detail="Chart not found on dashboard")

    sql = dc.get("sql_query")
    if not sql:
        return {"columns": []}

    columns = await chart_service.get_chart_columns(sql)
    return {"columns": columns}


@router.post("/{dashboard_id}/selectors/generate", response_model=SelectorListResponse)
async def generate_selectors(dashboard_id: int) -> SelectorListResponse:
    """Generate selectors using AI based on dashboard charts."""
    dashboard = await dashboard_service.get_dashboard_by_id(dashboard_id)
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    charts_list = dashboard.get("charts", [])
    if not charts_list:
        raise HTTPException(status_code=400, detail="Dashboard has no charts")

    # Build charts context for AI
    charts_lines: list[str] = []
    for c in charts_list:
        title = c.get("title_override") or c.get("chart_title") or f"Chart #{c['id']}"
        sql = c.get("sql_query", "")
        charts_lines.append(
            f"Dashboard Chart ID: {c['id']}\n"
            f"Title: {title}\n"
            f"SQL: {sql}\n"
        )
    charts_context = "\n".join(charts_lines)

    # Get schema context
    schema_desc = await chart_service.get_any_latest_schema_description()
    if not schema_desc:
        raise HTTPException(
            status_code=400,
            detail="Schema description not found. Generate one first via /api/v1/schema/describe.",
        )
    schema_context = schema_desc["markdown"]

    try:
        ai_selectors = await ai_service.generate_selectors(charts_context, schema_context)
    except AIServiceError as e:
        raise HTTPException(status_code=502, detail=e.message) from e

    # Create generated selectors in the database
    created: list[dict] = []
    for idx, sel_data in enumerate(ai_selectors):
        try:
            mappings = []
            for m in sel_data.get("mappings", []):
                mappings.append({
                    "dashboard_chart_id": m["dashboard_chart_id"],
                    "target_column": m["target_column"],
                    "target_table": m.get("target_table"),
                    "operator_override": m.get("operator_override"),
                })

            config = sel_data.get("config")

            selector = await selector_service.create_selector(
                dashboard_id=dashboard_id,
                name=sel_data.get("name", f"ai_selector_{idx}"),
                label=sel_data.get("label", f"Filter {idx + 1}"),
                selector_type=sel_data.get("selector_type", "text"),
                operator=sel_data.get("operator", "equals"),
                config=config,
                sort_order=idx,
                is_required=sel_data.get("is_required", False),
                mappings=mappings if mappings else None,
            )
            created.append(selector)
        except Exception as e:
            logger.warning(
                "Failed to create AI-generated selector",
                name=sel_data.get("name"),
                error=str(e),
            )

    return SelectorListResponse(selectors=[SelectorResponse(**s) for s in created])
