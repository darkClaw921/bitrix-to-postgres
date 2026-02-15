"""Selector management endpoints (internal, requires app auth)."""

from fastapi import APIRouter, HTTPException

from app.api.v1.schemas.selectors import (
    ChartColumnsResponse,
    ChartTablesResponse,
    FilterPreviewRequest,
    FilterPreviewResponse,
    SelectorCreateRequest,
    SelectorListResponse,
    SelectorOptionsResponse,
    SelectorOptionItem,
    SelectorResponse,
    SelectorUpdateRequest,
)
from app.core.logging import get_logger
from app.domain.services.selector_service import SelectorService

logger = get_logger(__name__)

router = APIRouter()
selector_service = SelectorService()


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
