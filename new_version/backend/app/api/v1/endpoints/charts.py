"""Chart generation and management endpoints."""

from fastapi import APIRouter, HTTPException, Query

from app.api.v1.schemas.charts import (
    ChartConfigUpdateRequest,
    ChartDataResponse,
    ChartExecuteSqlRequest,
    ChartGenerateRequest,
    ChartGenerateResponse,
    ChartListResponse,
    ChartPromptTemplateResponse,
    ChartPromptTemplateUpdateRequest,
    ChartResponse,
    ChartSaveRequest,
    ChartSpec,
)
from app.config import get_settings
from app.core.exceptions import AIServiceError, ChartServiceError
from app.core.logging import get_logger
from app.domain.services.ai_service import AIService
from app.domain.services.chart_service import ChartService

logger = get_logger(__name__)

router = APIRouter()

ai_service = AIService()
chart_service = ChartService()


@router.post("/generate", response_model=ChartGenerateResponse)
async def generate_chart(request: ChartGenerateRequest) -> ChartGenerateResponse:
    """Generate a chart from a natural language prompt."""
    settings = get_settings()

    try:
        # 1. Get latest schema description (generated via /schema/describe)
        schema_desc = await chart_service.get_any_latest_schema_description()
        if not schema_desc:
            raise HTTPException(
                status_code=400,
                detail="Сначала сгенерируйте описание схемы базы данных (GET /api/v1/schema/describe).",
            )
        schema_context = schema_desc["markdown"]

        # 2. Get allowed tables
        allowed_tables = await chart_service.get_allowed_tables()

        # 3. Generate chart spec via AI
        spec_dict = await ai_service.generate_chart_spec(
            request.prompt, schema_context
        )
        spec = ChartSpec(**spec_dict)

        # 4. Validate SQL
        chart_service.validate_sql_query(spec.sql_query)
        chart_service.validate_table_names(spec.sql_query, allowed_tables)
        sql = chart_service.ensure_limit(spec.sql_query, settings.chart_max_rows)

        # 5. Execute query
        data, exec_time = await chart_service.execute_chart_query(sql)

        # Update spec with the limited SQL
        spec.sql_query = sql

        return ChartGenerateResponse(
            chart=spec,
            data=data,
            row_count=len(data),
            execution_time_ms=round(exec_time, 2),
        )

    except AIServiceError as e:
        logger.error("AI service error", error=e.message)
        raise HTTPException(status_code=502, detail=e.message) from e
    except ChartServiceError as e:
        logger.error("Chart service error", error=e.message)
        raise HTTPException(status_code=400, detail=e.message) from e


@router.post("/execute-sql", response_model=ChartDataResponse)
async def execute_sql(request: ChartExecuteSqlRequest) -> ChartDataResponse:
    """Execute a SQL query and return data (for preview editing)."""
    settings = get_settings()

    try:
        chart_service.validate_sql_query(request.sql_query)
        allowed_tables = await chart_service.get_allowed_tables()
        chart_service.validate_table_names(request.sql_query, allowed_tables)
        sql = chart_service.ensure_limit(request.sql_query, settings.chart_max_rows)
        data, exec_time = await chart_service.execute_chart_query(sql)

        return ChartDataResponse(
            data=data,
            row_count=len(data),
            execution_time_ms=round(exec_time, 2),
        )
    except ChartServiceError as e:
        logger.error("SQL execution error", error=e.message)
        raise HTTPException(status_code=400, detail=e.message) from e


@router.post("/save", response_model=ChartResponse)
async def save_chart(request: ChartSaveRequest) -> ChartResponse:
    """Save a generated chart to the database."""
    try:
        chart = await chart_service.save_chart(request.model_dump())
        return ChartResponse(**chart)
    except Exception as e:
        logger.error("Failed to save chart", error=str(e))
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения: {str(e)}") from e


@router.get("/list", response_model=ChartListResponse)
async def list_charts(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> ChartListResponse:
    """Get paginated list of saved charts (pinned first)."""
    charts, total = await chart_service.get_charts(page, per_page)
    return ChartListResponse(
        charts=[ChartResponse(**c) for c in charts],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{chart_id}/data", response_model=ChartDataResponse)
async def get_chart_data(chart_id: int) -> ChartDataResponse:
    """Re-execute chart SQL to get fresh data."""
    settings = get_settings()

    chart = await chart_service.get_chart_by_id(chart_id)
    if not chart:
        raise HTTPException(status_code=404, detail="Чарт не найден")

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


@router.patch("/{chart_id}/config", response_model=ChartResponse)
async def update_chart_config(
    chart_id: int, request: ChartConfigUpdateRequest
) -> ChartResponse:
    """Partially update chart_config (deep merge)."""
    try:
        chart = await chart_service.update_chart_config(chart_id, request.config)
        return ChartResponse(**chart)
    except ChartServiceError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@router.delete("/{chart_id}")
async def delete_chart(chart_id: int) -> dict:
    """Delete a chart by ID."""
    deleted = await chart_service.delete_chart(chart_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Чарт не найден")
    return {"deleted": True}


@router.post("/{chart_id}/pin", response_model=ChartResponse)
async def toggle_pin_chart(chart_id: int) -> ChartResponse:
    """Toggle pin status of a chart."""
    try:
        chart = await chart_service.toggle_pin(chart_id)
        return ChartResponse(**chart)
    except ChartServiceError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@router.get("/prompt-template/bitrix-context", response_model=ChartPromptTemplateResponse)
async def get_bitrix_prompt_template() -> ChartPromptTemplateResponse:
    """Get the Bitrix context prompt template for chart generation."""
    template = await chart_service.get_chart_prompt_template("bitrix_context")
    if not template:
        raise HTTPException(status_code=404, detail="Промпт не найден")
    return ChartPromptTemplateResponse(**template)


@router.put("/prompt-template/bitrix-context", response_model=ChartPromptTemplateResponse)
async def update_bitrix_prompt_template(
    request: ChartPromptTemplateUpdateRequest,
) -> ChartPromptTemplateResponse:
    """Update the Bitrix context prompt template for chart generation."""
    try:
        template = await chart_service.update_chart_prompt_template(
            "bitrix_context", request.content
        )
        return ChartPromptTemplateResponse(**template)
    except ChartServiceError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
