"""Dashboard management endpoints (internal, requires app auth)."""

from fastapi import APIRouter, HTTPException, Query

from app.api.v1.schemas.dashboards import (
    ChartOverrideUpdateRequest,
    DashboardLayoutUpdateRequest,
    DashboardLinkRequest,
    DashboardLinkResponse,
    DashboardLinkUpdateRequest,
    DashboardListItem,
    DashboardListResponse,
    DashboardPublishRequest,
    DashboardPublishResponse,
    DashboardResponse,
    DashboardUpdateRequest,
    IframeCodeRequest,
    IframeCodeResponse,
    PasswordChangeResponse,
)
from app.config import get_settings
from app.core.exceptions import DashboardServiceError
from app.core.logging import get_logger
from app.domain.services.dashboard_service import DashboardService

logger = get_logger(__name__)

router = APIRouter()
dashboard_service = DashboardService()


@router.post("/publish", response_model=DashboardPublishResponse)
async def publish_dashboard(request: DashboardPublishRequest) -> DashboardPublishResponse:
    """Create a new published dashboard from chart IDs."""
    try:
        result = await dashboard_service.create_dashboard(
            title=request.title,
            chart_ids=request.chart_ids,
            description=request.description,
            refresh_interval_minutes=request.refresh_interval_minutes,
        )
        return DashboardPublishResponse(
            dashboard=DashboardResponse(**result["dashboard"]),
            password=result["password"],
        )
    except DashboardServiceError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    except Exception as e:
        logger.error("Failed to publish dashboard", error=str(e))
        raise HTTPException(status_code=500, detail=f"Ошибка публикации: {str(e)}") from e


@router.get("/list", response_model=DashboardListResponse)
async def list_dashboards(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> DashboardListResponse:
    """Get paginated list of published dashboards."""
    dashboards, total = await dashboard_service.get_dashboards(page, per_page)
    return DashboardListResponse(
        dashboards=[DashboardListItem(**d) for d in dashboards],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{dashboard_id}", response_model=DashboardResponse)
async def get_dashboard(dashboard_id: int) -> DashboardResponse:
    """Get dashboard detail with charts."""
    dashboard = await dashboard_service.get_dashboard_by_id(dashboard_id)
    if not dashboard:
        raise HTTPException(status_code=404, detail="Дашборд не найден")
    return DashboardResponse(**dashboard)


@router.put("/{dashboard_id}", response_model=DashboardResponse)
async def update_dashboard(
    dashboard_id: int, request: DashboardUpdateRequest
) -> DashboardResponse:
    """Update dashboard title/description."""
    try:
        dashboard = await dashboard_service.update_dashboard(
            dashboard_id,
            title=request.title,
            description=request.description,
            refresh_interval_minutes=request.refresh_interval_minutes,
        )
        return DashboardResponse(**dashboard)
    except DashboardServiceError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.delete("/{dashboard_id}")
async def delete_dashboard(dashboard_id: int) -> dict:
    """Delete a dashboard."""
    deleted = await dashboard_service.delete_dashboard(dashboard_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Дашборд не найден")
    return {"deleted": True}


@router.put("/{dashboard_id}/layout", response_model=DashboardResponse)
async def update_layout(
    dashboard_id: int, request: DashboardLayoutUpdateRequest
) -> DashboardResponse:
    """Save chart layout positions."""
    try:
        dashboard = await dashboard_service.update_layout(
            dashboard_id, [item.model_dump() for item in request.layouts]
        )
        return DashboardResponse(**dashboard)
    except DashboardServiceError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.put("/{dashboard_id}/charts/{dc_id}")
async def update_chart_override(
    dashboard_id: int, dc_id: int, request: ChartOverrideUpdateRequest
) -> dict:
    """Update chart title/description override in dashboard."""
    try:
        result = await dashboard_service.update_chart_override(
            dc_id,
            title_override=request.title_override,
            description_override=request.description_override,
        )
        return result
    except DashboardServiceError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.delete("/{dashboard_id}/charts/{dc_id}")
async def remove_chart_from_dashboard(dashboard_id: int, dc_id: int) -> dict:
    """Remove a chart from the dashboard."""
    deleted = await dashboard_service.remove_chart(dc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Элемент дашборда не найден")
    return {"deleted": True}


@router.post("/{dashboard_id}/change-password", response_model=PasswordChangeResponse)
async def change_password(dashboard_id: int) -> PasswordChangeResponse:
    """Generate a new password for the dashboard."""
    try:
        password = await dashboard_service.change_password(dashboard_id)
        return PasswordChangeResponse(password=password)
    except DashboardServiceError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.post("/iframe-code", response_model=IframeCodeResponse)
async def get_iframe_code(request: IframeCodeRequest) -> IframeCodeResponse:
    """Generate iframe HTML code for given chart IDs."""
    settings = get_settings()
    iframes = []

    for chart_id in request.chart_ids:
        iframe_html = (
            f'<iframe src="/embed/chart/{chart_id}" '
            f'width="{request.width}" height="{request.height}" '
            f'frameborder="0" style="border: none;"></iframe>'
        )
        iframes.append({
            "chart_id": chart_id,
            "html": iframe_html,
        })

    return IframeCodeResponse(iframes=iframes)


# === Dashboard Links ===


@router.post("/{dashboard_id}/links", response_model=DashboardLinkResponse)
async def add_dashboard_link(
    dashboard_id: int, request: DashboardLinkRequest
) -> DashboardLinkResponse:
    """Add a linked dashboard (tab)."""
    try:
        link = await dashboard_service.add_link(
            dashboard_id,
            request.linked_dashboard_id,
            label=request.label,
            sort_order=request.sort_order,
        )
        return DashboardLinkResponse(**link)
    except DashboardServiceError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
    except Exception as e:
        if "uq_dashboard_linked" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="Эта связь уже существует") from e
        logger.error("Failed to add dashboard link", error=str(e))
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}") from e


@router.delete("/{dashboard_id}/links/{link_id}")
async def remove_dashboard_link(dashboard_id: int, link_id: int) -> dict:
    """Remove a linked dashboard."""
    deleted = await dashboard_service.remove_link(link_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Связь не найдена")
    return {"deleted": True}


@router.put("/{dashboard_id}/links", response_model=list[DashboardLinkResponse])
async def update_dashboard_links(
    dashboard_id: int, request: DashboardLinkUpdateRequest
) -> list[DashboardLinkResponse]:
    """Update link order."""
    try:
        links = await dashboard_service.update_link_order(
            dashboard_id, [item.model_dump() for item in request.links]
        )
        return [DashboardLinkResponse(**link) for link in links]
    except DashboardServiceError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
