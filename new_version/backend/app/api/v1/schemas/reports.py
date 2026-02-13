"""Pydantic schemas for report endpoints."""

import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# --- Requests ---


class ReportConversationRequest(BaseModel):
    """Request for one step of report generation dialog."""

    session_id: Optional[str] = Field(None, description="Session ID (auto-generated if empty)")
    message: str = Field(..., min_length=1, max_length=5000, description="User message")


class ReportSaveRequest(BaseModel):
    """Request to save a report from a conversation session."""

    session_id: str = Field(..., description="Conversation session ID")
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    schedule_type: Optional[str] = Field("once", pattern=r"^(once|daily|weekly|monthly)$")
    schedule_config: Optional[dict[str, Any]] = None


class ReportScheduleUpdateRequest(BaseModel):
    """Request to update report schedule."""

    schedule_type: Optional[str] = Field(None, pattern=r"^(once|daily|weekly|monthly)$")
    schedule_config: Optional[dict[str, Any]] = None
    status: Optional[str] = Field(None, pattern=r"^(draft|active|paused|error)$")


class ReportPromptTemplateUpdateRequest(BaseModel):
    """Request to update report prompt template."""

    content: str = Field(..., min_length=10, description="Prompt template content")


# --- Response components ---


class SqlQueryItem(BaseModel):
    """SQL query with purpose description."""

    sql: str
    purpose: str


class DataResultItem(BaseModel):
    """Result of a single SQL query execution."""

    sql: str
    purpose: str
    rows: list[dict[str, Any]] = []
    row_count: int = 0
    time_ms: float = 0
    error: Optional[str] = None


class ReportPreview(BaseModel):
    """Preview of a generated report before saving."""

    title: str
    description: Optional[str] = None
    sql_queries: list[SqlQueryItem]
    report_template: str
    data_results: list[DataResultItem] = []


# --- Responses ---


class ReportConversationResponse(BaseModel):
    """Response for one step of report generation dialog."""

    session_id: str
    content: str
    is_complete: bool = False
    report_preview: Optional[ReportPreview] = None


class ReportResponse(BaseModel):
    """Saved report response."""

    id: int
    title: str
    description: Optional[str] = None
    user_prompt: str
    status: str
    schedule_type: str
    schedule_config: Optional[dict[str, Any]] = None
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    sql_queries: Optional[list[dict[str, Any]]] = None
    report_template: Optional[str] = None
    is_pinned: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("sql_queries", mode="before")
    @classmethod
    def parse_sql_queries(cls, v: Any) -> Optional[list[dict[str, Any]]]:
        if isinstance(v, str):
            return json.loads(v)
        return v

    @field_validator("schedule_config", mode="before")
    @classmethod
    def parse_schedule_config(cls, v: Any) -> Optional[dict[str, Any]]:
        if isinstance(v, str):
            return json.loads(v)
        return v


class ReportListResponse(BaseModel):
    """Paginated list of reports."""

    reports: list[ReportResponse]
    total: int
    page: int
    per_page: int


class ReportRunResponse(BaseModel):
    """Report run result response."""

    id: int
    report_id: int
    status: str
    trigger_type: str
    result_markdown: Optional[str] = None
    result_data: Optional[list[dict[str, Any]]] = None
    sql_queries_executed: Optional[list[dict[str, Any]]] = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    @field_validator("result_data", mode="before")
    @classmethod
    def parse_result_data(cls, v: Any) -> Optional[list[dict[str, Any]]]:
        if isinstance(v, str):
            return json.loads(v)
        return v

    @field_validator("sql_queries_executed", mode="before")
    @classmethod
    def parse_sql_queries_executed(cls, v: Any) -> Optional[list[dict[str, Any]]]:
        if isinstance(v, str):
            return json.loads(v)
        return v


class ReportRunListResponse(BaseModel):
    """Paginated list of report runs."""

    runs: list[ReportRunResponse]
    total: int
    page: int
    per_page: int


class ReportPromptTemplateResponse(BaseModel):
    """Report prompt template response."""

    id: int
    name: str
    content: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --- Published Reports ---


class PublishReportRequest(BaseModel):
    """Request to publish a report."""

    report_id: int
    title: Optional[str] = None
    description: Optional[str] = None


class PublishedReportLinkRequest(BaseModel):
    """Request to add a linked published report."""

    linked_published_report_id: int
    label: Optional[str] = None
    sort_order: Optional[int] = 0


class PublishedReportLinkOrderItem(BaseModel):
    """Single item for reordering links."""

    id: int
    sort_order: int


class PublishedReportLinkUpdateRequest(BaseModel):
    """Request to update link order."""

    links: list[PublishedReportLinkOrderItem]


class PublishedReportAuthRequest(BaseModel):
    """Request to authenticate to a published report."""

    password: str


class PublishedReportLinkResponse(BaseModel):
    """Response for a published report link."""

    id: int
    sort_order: int
    label: Optional[str] = None
    linked_title: Optional[str] = None
    linked_slug: Optional[str] = None


class PublishedReportResponse(BaseModel):
    """Response for a published report."""

    id: int
    slug: str
    title: str
    description: Optional[str] = None
    report_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    linked_reports: list[PublishedReportLinkResponse] = []


class PublishedReportListItem(BaseModel):
    """Published report list item with report title."""

    id: int
    slug: str
    title: str
    description: Optional[str] = None
    report_id: int
    report_title: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PublishedReportListResponse(BaseModel):
    """Paginated list of published reports."""

    reports: list[PublishedReportListItem]
    total: int
    page: int
    per_page: int


class PublishReportResponse(BaseModel):
    """Response after publishing a report."""

    published_report: PublishedReportResponse
    password: str


class PublishedReportAuthResponse(BaseModel):
    """Response after authenticating to a published report."""

    token: str
    expires_in_minutes: int


class PublicReportRunResponse(BaseModel):
    """Public-facing report run (no result_data or sql_queries_executed)."""

    id: int
    status: str
    trigger_type: str
    result_markdown: Optional[str] = None
    execution_time_ms: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class PublicReportResponse(BaseModel):
    """Public-facing report data with runs and links."""

    id: int
    slug: str
    title: str
    description: Optional[str] = None
    report_title: Optional[str] = None
    runs: list[PublicReportRunResponse] = []
    linked_reports: list[PublishedReportLinkResponse] = []
