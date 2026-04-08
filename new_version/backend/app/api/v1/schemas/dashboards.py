"""Pydantic schemas for dashboard endpoints."""

import json
from datetime import datetime
from typing import Any, Literal, Optional

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
    tab_label: Optional[str] = Field(None, max_length=255)


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
    hide_title: Optional[bool] = None
    title_font_size_override: Optional[str] = Field(None, max_length=10)


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


# --- Heading items ---


class HeadingConfig(BaseModel):
    """Configuration for a heading dashboard item."""

    text: str = Field(..., min_length=1, max_length=500)
    level: int = Field(default=2, ge=1, le=6)
    align: Literal["left", "center", "right"] = "left"
    color: Optional[str] = None
    bg_color: Optional[str] = None
    divider: bool = False


class HeadingCreateRequest(BaseModel):
    """Request to create a new heading item on a dashboard."""

    heading: HeadingConfig
    layout_x: int = 0
    layout_y: int = 0
    layout_w: int = 12
    layout_h: int = 2
    sort_order: Optional[int] = None


class HeadingUpdateRequest(BaseModel):
    """Request to update the configuration of an existing heading item."""

    heading: HeadingConfig


class ChartAddRequest(BaseModel):
    """Request to attach an existing AI chart to a dashboard.

    Used by the editor's "+ Чарт" UI to add charts to dashboards that have
    already been published. All layout fields are optional: when omitted the
    service computes sensible defaults — ``layout_x=0``, ``layout_w=6``,
    ``layout_h=4``, ``layout_y=MAX(layout_y+layout_h)`` so the new chart
    lands at the bottom of the existing layout without overlap, and
    ``sort_order=MAX+1``. Sending ``layout_y=0`` explicitly is interpreted
    as "place at the very top" — only ``None`` triggers the bottom-append
    fallback.
    """

    chart_id: int = Field(..., gt=0)
    layout_x: Optional[int] = None
    layout_y: Optional[int] = None
    layout_w: Optional[int] = None
    layout_h: Optional[int] = None
    sort_order: Optional[int] = None


# --- Responses ---


class DashboardChartResponse(BaseModel):
    """Polymorphic dashboard item: chart or heading.

    For item_type='chart' the chart-specific fields (chart_id, chart_title,
    chart_type, chart_config, sql_query, user_prompt) are populated.
    For item_type='heading' those fields are None and ``heading_config``
    holds the heading payload (text, level, align, ...).
    """

    id: int
    dashboard_id: int
    item_type: str = "chart"
    chart_id: Optional[int] = None
    heading_config: Optional[dict[str, Any]] = None
    title_override: Optional[str] = None
    description_override: Optional[str] = None
    hide_title: bool = False
    title_font_size_override: Optional[str] = None
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

    @field_validator("heading_config", mode="before")
    @classmethod
    def parse_heading_config(cls, v: Any) -> dict[str, Any] | None:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
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
    tab_label: Optional[str] = None
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
