"""Public endpoints for chart embeds and dashboard access (no app auth)."""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from app.api.v1.schemas.dashboards import (
    DashboardAuthRequest,
    DashboardAuthResponse,
    DashboardResponse,
)
from app.api.v1.schemas.charts import ChartDataResponse
from app.config import get_settings
from app.core.exceptions import ChartServiceError, DashboardAuthError, DashboardServiceError
from app.core.logging import get_logger
from app.domain.services.chart_service import ChartService
from app.domain.services.dashboard_service import DashboardService

logger = get_logger(__name__)

router = APIRouter()
chart_service = ChartService()
dashboard_service = DashboardService()


@router.get("/chart/{chart_id}/meta")
async def get_chart_meta(chart_id: int) -> dict:
    """Get chart metadata for embedding (public, no auth)."""
    chart = await chart_service.get_chart_by_id(chart_id)
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found")

    return {
        "id": chart["id"],
        "title": chart["title"],
        "description": chart.get("description"),
        "chart_type": chart["chart_type"],
        "chart_config": chart["chart_config"],
    }


@router.get("/chart/{chart_id}/data", response_model=ChartDataResponse)
async def get_chart_data(chart_id: int) -> ChartDataResponse:
    """Get chart data for embedding (public, no auth)."""
    settings = get_settings()

    chart = await chart_service.get_chart_by_id(chart_id)
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found")

    try:
        sql = chart["sql_query"]
        chart_service.validate_sql_query(sql)
        sql = chart_service.ensure_limit(sql, settings.chart_max_rows)
        data, exec_time = await chart_service.execute_chart_query(sql)

        return ChartDataResponse(
            data=data,
            row_count=len(data),
            execution_time_ms=round(exec_time, 2),
        )
    except ChartServiceError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


@router.post("/dashboard/{slug}/auth", response_model=DashboardAuthResponse)
async def authenticate_dashboard(
    slug: str, request: DashboardAuthRequest
) -> DashboardAuthResponse:
    """Verify dashboard password and return JWT."""
    settings = get_settings()

    try:
        is_valid = await dashboard_service.verify_password(slug, request.password)
        if not is_valid:
            raise HTTPException(status_code=401, detail="Неверный пароль")

        token = dashboard_service.generate_token(slug)
        return DashboardAuthResponse(
            token=token,
            expires_in_minutes=settings.dashboard_token_expiry_minutes,
        )
    except DashboardServiceError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


def _verify_dashboard_token(authorization: Optional[str], slug: str) -> None:
    """Verify JWT token from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    token = authorization[7:]
    try:
        token_slug = dashboard_service.verify_token(token)
        if token_slug != slug:
            raise HTTPException(status_code=403, detail="Токен не для этого дашборда")
    except DashboardAuthError as e:
        raise HTTPException(status_code=401, detail=e.message) from e


@router.get("/dashboard/{slug}", response_model=DashboardResponse)
async def get_public_dashboard(
    slug: str,
    authorization: Optional[str] = Header(None),
) -> DashboardResponse:
    """Get dashboard detail (requires JWT from /auth)."""
    _verify_dashboard_token(authorization, slug)

    dashboard = await dashboard_service.get_dashboard_by_slug(slug)
    if not dashboard:
        raise HTTPException(status_code=404, detail="Дашборд не найден")

    if not dashboard.get("is_active"):
        raise HTTPException(status_code=403, detail="Дашборд деактивирован")

    return DashboardResponse(**dashboard)


@router.get("/dashboard/{slug}/chart/{dc_id}/data", response_model=ChartDataResponse)
async def get_dashboard_chart_data(
    slug: str,
    dc_id: int,
    authorization: Optional[str] = Header(None),
) -> ChartDataResponse:
    """Get chart data within a dashboard (requires JWT)."""
    _verify_dashboard_token(authorization, slug)
    settings = get_settings()

    # Get dashboard to verify chart belongs to it
    dashboard = await dashboard_service.get_dashboard_by_slug(slug)
    if not dashboard:
        raise HTTPException(status_code=404, detail="Дашборд не найден")

    # Find the chart in dashboard
    dc_chart = None
    for c in dashboard.get("charts", []):
        if c["id"] == dc_id:
            dc_chart = c
            break

    if not dc_chart:
        raise HTTPException(status_code=404, detail="Чарт не найден в дашборде")

    try:
        sql = dc_chart["sql_query"]
        chart_service.validate_sql_query(sql)
        sql = chart_service.ensure_limit(sql, settings.chart_max_rows)
        data, exec_time = await chart_service.execute_chart_query(sql)

        return ChartDataResponse(
            data=data,
            row_count=len(data),
            execution_time_ms=round(exec_time, 2),
        )
    except ChartServiceError as e:
        raise HTTPException(status_code=400, detail=e.message) from e


# === Linked Dashboard Endpoints ===


@router.get("/dashboard/{slug}/linked/{linked_slug}", response_model=DashboardResponse)
async def get_linked_dashboard(
    slug: str,
    linked_slug: str,
    authorization: Optional[str] = Header(None),
) -> DashboardResponse:
    """Get a linked dashboard detail (requires JWT for main slug)."""
    _verify_dashboard_token(authorization, slug)

    # Verify the link exists and both dashboards are active
    is_linked = await dashboard_service.verify_linked_access(slug, linked_slug)
    if not is_linked:
        raise HTTPException(status_code=403, detail="Связанный дашборд не найден или не активен")

    dashboard = await dashboard_service.get_dashboard_by_slug(linked_slug)
    if not dashboard:
        raise HTTPException(status_code=404, detail="Дашборд не найден")

    return DashboardResponse(**dashboard)


@router.get(
    "/dashboard/{slug}/linked/{linked_slug}/chart/{dc_id}/data",
    response_model=ChartDataResponse,
)
async def get_linked_dashboard_chart_data(
    slug: str,
    linked_slug: str,
    dc_id: int,
    authorization: Optional[str] = Header(None),
) -> ChartDataResponse:
    """Get chart data from a linked dashboard (requires JWT for main slug)."""
    _verify_dashboard_token(authorization, slug)
    settings = get_settings()

    # Verify the link
    is_linked = await dashboard_service.verify_linked_access(slug, linked_slug)
    if not is_linked:
        raise HTTPException(status_code=403, detail="Связанный дашборд не найден или не активен")

    dashboard = await dashboard_service.get_dashboard_by_slug(linked_slug)
    if not dashboard:
        raise HTTPException(status_code=404, detail="Дашборд не найден")

    # Find chart in linked dashboard
    dc_chart = None
    for c in dashboard.get("charts", []):
        if c["id"] == dc_id:
            dc_chart = c
            break

    if not dc_chart:
        raise HTTPException(status_code=404, detail="Чарт не найден в дашборде")

    try:
        sql = dc_chart["sql_query"]
        chart_service.validate_sql_query(sql)
        sql = chart_service.ensure_limit(sql, settings.chart_max_rows)
        data, exec_time = await chart_service.execute_chart_query(sql)

        return ChartDataResponse(
            data=data,
            row_count=len(data),
            execution_time_ms=round(exec_time, 2),
        )
    except ChartServiceError as e:
        raise HTTPException(status_code=400, detail=e.message) from e
