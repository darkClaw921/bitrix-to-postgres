"""Pydantic schemas for selector endpoints."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# --- Requests ---


class SelectorMappingItem(BaseModel):
    """Mapping configuration for a selector-chart pair."""

    dashboard_chart_id: int
    target_column: str = Field(..., max_length=255)
    target_table: Optional[str] = Field(None, max_length=255)
    operator_override: Optional[str] = Field(None, max_length=30)


class SelectorCreateRequest(BaseModel):
    """Request to create a dashboard selector."""

    name: str = Field(..., max_length=100)
    label: str = Field(..., max_length=255)
    selector_type: str = Field(..., max_length=30)
    operator: str = Field("equals", max_length=30)
    config: Optional[dict[str, Any]] = None
    sort_order: int = 0
    is_required: bool = False
    mappings: list[SelectorMappingItem] = []


class SelectorUpdateRequest(BaseModel):
    """Request to update a dashboard selector."""

    name: Optional[str] = Field(None, max_length=100)
    label: Optional[str] = Field(None, max_length=255)
    selector_type: Optional[str] = Field(None, max_length=30)
    operator: Optional[str] = Field(None, max_length=30)
    config: Optional[dict[str, Any]] = None
    sort_order: Optional[int] = None
    is_required: Optional[bool] = None


class MappingCreateRequest(BaseModel):
    """Request to add a chart mapping to a selector."""

    dashboard_chart_id: int
    target_column: str = Field(..., max_length=255)
    target_table: Optional[str] = Field(None, max_length=255)
    operator_override: Optional[str] = Field(None, max_length=30)


class FilterValue(BaseModel):
    """Single filter value from the client."""

    name: str
    value: Any


class FilterRequest(BaseModel):
    """Request with filter values for chart data."""

    filters: list[FilterValue] = []


# --- Responses ---


class MappingResponse(BaseModel):
    """Selector-chart mapping response."""

    id: int
    selector_id: int
    dashboard_chart_id: int
    target_column: str
    target_table: Optional[str] = None
    operator_override: Optional[str] = None
    created_at: Optional[datetime] = None


class SelectorResponse(BaseModel):
    """Dashboard selector response."""

    id: int
    dashboard_id: int
    name: str
    label: str
    selector_type: str
    operator: str = "equals"
    config: Optional[dict[str, Any]] = None
    sort_order: int = 0
    is_required: bool = False
    mappings: list[MappingResponse] = []
    created_at: Optional[datetime] = None


class SelectorListResponse(BaseModel):
    """List of selectors for a dashboard."""

    selectors: list[SelectorResponse]


class SelectorOptionsResponse(BaseModel):
    """Dropdown options for a selector."""

    options: list[Any]
