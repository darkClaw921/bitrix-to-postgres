"""Pydantic schemas for dashboard endpoints."""

import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.api.v1.schemas.selectors import SelectorResponse


# --- Requests ---


class DashboardPublishRequest(BaseModel):
    """Request to publish a new dashboard."""

    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    chart_ids: list[int] = Field(..., min_length=1)
    refresh_interval_minutes: int = Field(10, ge=1, le=1440)


class DashboardUpdateRequest(BaseModel):
    """Request to update dashboard metadata."""

    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    refresh_interval_minutes: Optional[int] = Field(None, ge=1, le=1440)


class LayoutItem(BaseModel):
    """Single chart layout position."""

    id: int
    x: int = 0
    y: int = 0
    w: int = 6
    h: int = 4
    sort_order: int = 0


class DashboardLayoutUpdateRequest(BaseModel):
    """Request to update chart layout positions."""

    layouts: list[LayoutItem]


class ChartOverrideUpdateRequest(BaseModel):
    """Request to update chart title/description override."""

    title_override: Optional[str] = Field(None, max_length=255)
    description_override: Optional[str] = None


class DashboardLinkRequest(BaseModel):
    """Request to add a linked dashboard."""

    linked_dashboard_id: int
    label: Optional[str] = Field(None, max_length=255)
    sort_order: int = 0


class DashboardLinkOrderItem(BaseModel):
    """Single link order update."""

    id: int
    sort_order: int = 0


class DashboardLinkUpdateRequest(BaseModel):
    """Request to update link order."""

    links: list[DashboardLinkOrderItem]


class DashboardAuthRequest(BaseModel):
    """Request to authenticate a dashboard."""

    password: str


class IframeCodeRequest(BaseModel):
    """Request to generate iframe code for chart IDs."""

    chart_ids: list[int] = Field(..., min_length=1)
    width: str = "100%"
    height: str = "400px"


# --- Responses ---


class DashboardChartResponse(BaseModel):
    """Chart within a dashboard."""

    id: int
    dashboard_id: int
    chart_id: int
    title_override: Optional[str] = None
    description_override: Optional[str] = None
    layout_x: int = 0
    layout_y: int = 0
    layout_w: int = 6
    layout_h: int = 4
    sort_order: int = 0
    chart_title: Optional[str] = None
    chart_description: Optional[str] = None
    chart_type: Optional[str] = None
    chart_config: Optional[dict[str, Any]] = None
    sql_query: Optional[str] = None
    user_prompt: Optional[str] = None
    created_at: Optional[datetime] = None

    @field_validator("chart_config", mode="before")
    @classmethod
    def parse_chart_config(cls, v: Any) -> dict[str, Any] | None:
        if isinstance(v, str):
            return json.loads(v)
        return v


class DashboardLinkResponse(BaseModel):
    """Linked dashboard info."""

    id: int
    dashboard_id: int
    linked_dashboard_id: int
    sort_order: int = 0
    label: Optional[str] = None
    linked_title: Optional[str] = None
    linked_slug: Optional[str] = None


class DashboardResponse(BaseModel):
    """Dashboard detail response."""

    id: int
    slug: str
    title: str
    description: Optional[str] = None
    is_active: bool = True
    refresh_interval_minutes: int = 10
    charts: list[DashboardChartResponse] = []
    linked_dashboards: list[DashboardLinkResponse] = []
    selectors: list[SelectorResponse] = []
    created_at: datetime
    updated_at: datetime


class DashboardListItem(BaseModel):
    """Dashboard list item."""

    id: int
    slug: str
    title: str
    description: Optional[str] = None
    is_active: bool = True
    refresh_interval_minutes: int = 10
    chart_count: int = 0
    created_at: datetime
    updated_at: datetime


class DashboardListResponse(BaseModel):
    """Paginated dashboard list."""

    dashboards: list[DashboardListItem]
    total: int
    page: int
    per_page: int


class DashboardPublishResponse(BaseModel):
    """Response after publishing a dashboard."""

    dashboard: DashboardResponse
    password: str


class DashboardAuthResponse(BaseModel):
    """Response after dashboard authentication."""

    token: str
    expires_in_minutes: int


class PasswordChangeResponse(BaseModel):
    """Response after password change."""

    password: str


class IframeCodeResponse(BaseModel):
    """Response with iframe HTML code."""

    iframes: list[dict[str, Any]]
