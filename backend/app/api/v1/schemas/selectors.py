"""Pydantic schemas for selector endpoints."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# --- Requests ---


class MappingCreateRequest(BaseModel):
    """Single chart mapping within a selector.

    The optional ``post_filter_*`` fields enable two-step filtering: when the
    selector value semantically refers to a different table than the chart's
    own data, the generated SQL becomes
    ``WHERE target_column IN (SELECT post_filter_resolve_id_column FROM
    post_filter_resolve_table WHERE post_filter_resolve_column <op> :value)``.
    """

    dashboard_chart_id: int
    target_column: str = Field(..., max_length=255)
    target_table: Optional[str] = Field(None, max_length=255)
    operator_override: Optional[str] = Field(None, max_length=30)
    post_filter_resolve_table: Optional[str] = Field(None, max_length=255)
    post_filter_resolve_column: Optional[str] = Field(None, max_length=255)
    post_filter_resolve_id_column: Optional[str] = Field(None, max_length=255)


class SelectorCreateRequest(BaseModel):
    """Request to create a new selector."""

    name: str = Field(..., max_length=100)
    label: str = Field(..., max_length=255)
    selector_type: str = Field(..., max_length=30)
    operator: str = Field("equals", max_length=30)
    config: Optional[dict[str, Any]] = None
    sort_order: int = 0
    is_required: bool = False
    mappings: list[MappingCreateRequest] = []


class SelectorUpdateRequest(BaseModel):
    """Request to update a selector (full replace of mappings if provided)."""

    name: Optional[str] = Field(None, max_length=100)
    label: Optional[str] = Field(None, max_length=255)
    selector_type: Optional[str] = Field(None, max_length=30)
    operator: Optional[str] = Field(None, max_length=30)
    config: Optional[dict[str, Any]] = None
    sort_order: Optional[int] = None
    is_required: Optional[bool] = None
    mappings: Optional[list[MappingCreateRequest]] = None


class FilterValue(BaseModel):
    """Single filter value from the client."""

    name: str
    value: Any


class FilterRequest(BaseModel):
    """Request body for filtered chart data."""

    filters: list[FilterValue] = []


# --- Responses ---


class MappingResponse(BaseModel):
    """Chart mapping within a selector."""

    id: int
    selector_id: int
    dashboard_chart_id: int
    target_column: str
    target_table: Optional[str] = None
    operator_override: Optional[str] = None
    post_filter_resolve_table: Optional[str] = None
    post_filter_resolve_column: Optional[str] = None
    post_filter_resolve_id_column: Optional[str] = None
    created_at: Optional[datetime] = None


class SelectorResponse(BaseModel):
    """Single selector with its mappings."""

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


class SelectorOptionItem(BaseModel):
    """Single option for dropdown/multi-select."""

    value: Any
    label: str


class SelectorOptionsResponse(BaseModel):
    """Options for a selector."""

    options: list[SelectorOptionItem]


class BatchSelectorOptionsResponse(BaseModel):
    """Batch options for all selectors of a dashboard."""

    options: dict[int, list[SelectorOptionItem]]


class ChartColumnsResponse(BaseModel):
    """Column names from a chart's SQL query."""

    columns: list[str]


class ChartTablesResponse(BaseModel):
    """Table names extracted from a chart's SQL query."""

    tables: list[str]


# --- Filter Preview ---


class FilterPreviewRequest(BaseModel):
    """Request to preview how a filter modifies a chart's SQL."""

    selector_name: str = Field(..., max_length=100)
    selector_type: str = Field(..., max_length=30)
    operator: str = Field("equals", max_length=30)
    target_column: str = Field(..., max_length=255)
    target_table: Optional[str] = Field(None, max_length=255)
    sample_value: str = Field("example_value")


class FilterPreviewResponse(BaseModel):
    """Response with original and filtered SQL."""

    original_sql: str
    filtered_sql: str
    where_clause: str


# --- AI Selector Generation ---


class GenerateSelectorsRequest(BaseModel):
    """Optional payload for AI selector generation.

    ``user_request`` lets the user describe in natural language which selectors
    they want (e.g. "нужны фильтры по дате создания и менеджеру"). It is passed
    to the AI as a high-priority hint.

    ``chart_ids`` restricts selector generation to a subset of dashboard charts
    (``dashboard_charts.id`` values). When ``None`` or empty, all charts of the
    dashboard are used.
    """

    user_request: Optional[str] = Field(None, max_length=2000)
    chart_ids: Optional[list[int]] = None


class GenerateSelectorsResponse(BaseModel):
    """Response from AI-generated selector suggestions for a dashboard."""

    selectors: list[SelectorCreateRequest]
