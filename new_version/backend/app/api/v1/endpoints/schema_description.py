"""Schema description endpoints."""

from fastapi import APIRouter, HTTPException

from app.api.v1.schemas.schema_description import (
    ColumnInfo,
    SchemaDescriptionResponse,
    SchemaTablesResponse,
    TableInfo,
)
from app.core.exceptions import AIServiceError
from app.core.logging import get_logger
from app.domain.services.ai_service import AIService
from app.domain.services.chart_service import ChartService

logger = get_logger(__name__)

router = APIRouter()

ai_service = AIService()
chart_service = ChartService()


@router.get("/describe", response_model=SchemaDescriptionResponse)
async def describe_schema() -> SchemaDescriptionResponse:
    """AI-generated markdown description of all CRM tables."""
    try:
        schema_context = await chart_service.get_schema_context()
        if not schema_context.strip():
            raise HTTPException(
                status_code=400,
                detail="Не найдено CRM-таблиц в базе данных.",
            )

        tables_raw = await chart_service.get_tables_info()
        tables = [
            TableInfo(
                table_name=t["table_name"],
                columns=[ColumnInfo(**c) for c in t["columns"]],
                row_count=t.get("row_count"),
            )
            for t in tables_raw
        ]

        markdown = await ai_service.generate_schema_description(schema_context)

        return SchemaDescriptionResponse(tables=tables, markdown=markdown)

    except AIServiceError as e:
        logger.error("AI service error", error=e.message)
        raise HTTPException(status_code=502, detail=e.message) from e


@router.get("/tables", response_model=SchemaTablesResponse)
async def get_tables() -> SchemaTablesResponse:
    """List CRM tables with columns (no AI)."""
    tables_raw = await chart_service.get_tables_info()
    tables = [
        TableInfo(
            table_name=t["table_name"],
            columns=[ColumnInfo(**c) for c in t["columns"]],
            row_count=t.get("row_count"),
        )
        for t in tables_raw
    ]
    return SchemaTablesResponse(tables=tables)
