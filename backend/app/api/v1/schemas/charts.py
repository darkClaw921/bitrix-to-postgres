"""Pydantic schemas for chart endpoints."""

import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# --- Requests ---


class ChartGenerateRequest(BaseModel):
    """Request to generate a chart from a natural language prompt."""

    prompt: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Chart description in natural language",
    )
    table_filter: Optional[list[str]] = Field(
        None,
        description='Filter tables, e.g. ["crm_deals", "crm_contacts"]. '
        "Related reference tables (statuses, categories, enum values) will be automatically included.",
    )


class ChartExecuteSqlRequest(BaseModel):
    """Request to execute a raw SQL query and return data."""

    sql_query: str = Field(
        ...,
        min_length=5,
        max_length=5000,
        description="SQL query to execute",
    )


class ChartSaveRequest(BaseModel):
    """Request to save a generated chart."""

    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    user_prompt: str
    chart_type: str = Field(..., pattern=r"^(bar|line|pie|area|scatter|indicator|table|funnel|horizontal_bar)$")
    chart_config: dict[str, Any]
    sql_query: str


class ChartConfigUpdateRequest(BaseModel):
    """Request to partially update chart_config (deep merge)."""

    config: dict[str, Any] = Field(
        ..., description="Partial chart_config to merge with existing"
    )


class ChartSqlUpdateRequest(BaseModel):
    """Request to replace a saved chart's SQL query (manual edit).

    The backend validates the new SQL (SELECT-only, allowed tables, LIMIT) and
    executes it once to verify it works before committing the update.
    """

    sql_query: str = Field(..., min_length=5, max_length=5000)
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None


class ChartSqlRefineRequest(BaseModel):
    """Request to refine an existing chart's SQL via AI.

    The caller provides a free-form instruction describing what to change
    (e.g. "добавь фильтр по последним 30 дням" or "сгруппируй по менеджерам").
    Returns the refined SQL without saving — the client previews/edits and
    then calls PATCH ``/{chart_id}/sql`` to commit.
    """

    instruction: str = Field(..., min_length=3, max_length=2000)


class ChartSqlRefineResponse(BaseModel):
    """Response from AI SQL refinement."""

    sql_query: str


# --- Chart spec (from AI) ---


class LabelResolverSpec(BaseModel):
    """Post-processing rule that replaces raw IDs in a chart row with display labels.

    Stored under ``ai_charts.chart_config.label_resolvers`` (a list). On every
    chart data fetch the backend runs ``ChartService.resolve_labels_in_data``,
    which loads ``SELECT resolve_value_column, resolve_label_column FROM
    resolve_table`` once per resolver and rewrites matching cells in the
    response. Identifiers are validated against ``[A-Za-z_][A-Za-z0-9_]*``.
    """

    column: str = Field(..., description="Column in chart output whose value is the raw ID")
    resolve_table: str = Field(..., description="Reference table holding the labels")
    resolve_value_column: str = Field("id", description="Column in resolve_table matching the raw ID")
    resolve_label_column: str = Field(..., description="Column in resolve_table holding the human label")


class PlanFactConfig(BaseModel):
    """Typed configuration for post-enrichment of a chart with plan values.

    When a chart is published with this block inside ``chart_config.plan_fact``,
    the backend executes the LLM-generated SQL for the fact part only and then
    calls ``PlanService.enrich_rows_with_plan`` to add plan values to each row
    using already-resolved dashboard selectors (managers filter, date range).

    This avoids hard-coding plan periods / managers into the SQL JOIN and keeps
    plan values consistent with whatever selectors are currently applied.
    """

    model_config = ConfigDict(extra="forbid")

    table_name: str = Field(
        ...,
        description="Fact table name, e.g. 'crm_deals'. Must match plans.table_name.",
    )
    field_name: str = Field(
        ...,
        description="Numeric fact column, e.g. 'opportunity'. Must match plans.field_name.",
    )
    date_column: str = Field(
        ...,
        description="Date column in table_name used by the date_range selector; "
        "drives plan period intersection logic.",
    )
    group_by_column: Optional[str] = Field(
        None,
        description="Optional group column (e.g. 'assigned_by_id'). When set, "
        "enrichment splits plan values per group key; otherwise plan is a scalar.",
    )
    plan_key: str = Field(
        "plan",
        description="Name of the result column under which the plan value is "
        "injected into each row.",
    )


class ChartConfig(BaseModel):
    """Typed view over ``ai_charts.chart_config`` JSON.

    Historically ``chart_config`` is a free-form ``dict[str, Any]`` — this model
    intentionally uses ``extra='allow'`` so arbitrary legacy keys (colors,
    label_resolvers, axis settings, etc.) pass through untouched. Only the
    typed fields that the backend actively reads (currently ``plan_fact``) are
    declared here. Old charts without ``plan_fact`` round-trip unchanged and
    ``model_dump(exclude_none=True)`` does not leak a null ``plan_fact`` key.
    """

    model_config = ConfigDict(extra="allow")

    plan_fact: Optional[PlanFactConfig] = Field(
        None,
        description="Optional post-enrichment config — when present, backend "
        "injects plan values into each row after SQL execution.",
    )


class ChartSpec(BaseModel):
    """Chart specification generated by AI."""

    model_config = ConfigDict(extra="ignore")

    title: str
    chart_type: str = Field(..., description="bar | line | pie | area | scatter | indicator | table | funnel | horizontal_bar")
    sql_query: str
    data_keys: dict[str, Any] = Field(
        ..., description='{x: "stage", y: "count"} or {x: "month", y: ["revenue", "cost"]}'
    )
    colors: Optional[list[str]] = None
    description: Optional[str] = None
    label_resolvers: Optional[list[LabelResolverSpec]] = Field(
        None,
        description="Optional post-processing rules to replace raw IDs in result rows with display names",
    )
    chart_config: Optional[dict[str, Any]] = Field(
        None,
        description="Optional free-form chart_config returned by the LLM. Currently "
        "used to carry 'plan_fact' (PlanFactConfig) for post-enrichment — the backend "
        "reads chart_config.plan_fact after SQL execution and injects plan values "
        "into each row. Validated structurally only for the plan_fact key; other "
        "legacy keys (colors, label_resolvers, axis settings, ...) pass through.",
    )


# --- Responses ---


class ChartGenerateResponse(BaseModel):
    """Response for chart generation."""

    chart: ChartSpec
    data: list[dict[str, Any]]
    row_count: int
    execution_time_ms: float


class ChartResponse(BaseModel):
    """Saved chart response."""

    id: int
    title: str
    description: Optional[str] = None
    user_prompt: str
    chart_type: str
    chart_config: dict[str, Any]
    sql_query: str
    is_pinned: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("chart_config", mode="before")
    @classmethod
    def parse_chart_config(cls, v: Any) -> dict[str, Any]:
        if isinstance(v, str):
            return json.loads(v)
        return v


class ChartListResponse(BaseModel):
    """Paginated list of saved charts."""

    charts: list[ChartResponse]
    total: int
    page: int
    per_page: int


class ChartDataResponse(BaseModel):
    """Updated chart data (re-executed SQL)."""

    data: list[dict[str, Any]]
    row_count: int
    execution_time_ms: float


class ChartPromptTemplateResponse(BaseModel):
    """Chart prompt template response."""

    id: int
    name: str
    content: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ChartPromptTemplateUpdateRequest(BaseModel):
    """Request to update chart prompt template."""

    content: str = Field(..., min_length=10, description="Prompt template content")
