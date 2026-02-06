"""Schema description endpoints."""

from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Path, Query

from app.api.v1.schemas.schema_description import (
    ColumnInfo,
    SchemaDescriptionListItem,
    SchemaDescriptionListResponse,
    SchemaDescriptionResponse,
    SchemaDescriptionUpdate,
    SchemaTablesResponse,
    TableInfo,
)
from app.core.exceptions import AIServiceError, ChartServiceError
from app.core.logging import get_logger
from app.domain.services.ai_service import AIService
from app.domain.services.chart_service import ChartService

logger = get_logger(__name__)

router = APIRouter()

ai_service = AIService()
chart_service = ChartService()


@router.get("/describe", response_model=SchemaDescriptionResponse)
async def describe_schema(
    entity_tables: Optional[str] = Query(
        None,
        description="Comma-separated list of entity tables to include (e.g., 'crm_deals,crm_contacts'). "
        "Related reference tables will be automatically included.",
    ),
    include_related: bool = Query(
        True,
        description="If true, automatically include related reference tables for specified entities",
    ),
) -> SchemaDescriptionResponse:
    """AI-generated markdown description of CRM tables.

    If entity_tables is specified, only those tables and their related reference tables
    will be included. For example, requesting 'crm_deals' will also include:
    - ref_crm_statuses (Statuses & Stages)
    - ref_crm_deal_categories (Deal Pipelines)
    - ref_crm_currencies (Currencies)
    - ref_enum_values (Enum Field Values)

    The generated description is automatically saved and can be retrieved later.
    """
    try:
        table_filter = None
        if entity_tables:
            table_filter = [t.strip() for t in entity_tables.split(",") if t.strip()]

        schema_context = await chart_service.get_schema_context(
            table_filter=table_filter, include_related=include_related
        )
        if not schema_context.strip():
            raise HTTPException(
                status_code=400,
                detail="Не найдено CRM-таблиц в базе данных.",
            )

        tables_raw = await chart_service.get_tables_info(
            table_filter=table_filter, include_related=include_related
        )
        tables = [
            TableInfo(
                table_name=t["table_name"],
                columns=[ColumnInfo(**c) for c in t["columns"]],
                row_count=t.get("row_count"),
            )
            for t in tables_raw
        ]

        markdown = await ai_service.generate_schema_description(schema_context)

        # Save the generated description
        saved = await chart_service.save_schema_description(
            markdown=markdown,
            entity_filter=table_filter,
            include_related=include_related,
        )

        return SchemaDescriptionResponse(
            id=saved["id"],
            tables=tables,
            markdown=saved["markdown"],
            entity_filter=saved["entity_filter"],
            include_related=saved["include_related"],
            created_at=saved["created_at"],
            updated_at=saved["updated_at"],
        )

    except AIServiceError as e:
        logger.error("AI service error", error=e.message)
        raise HTTPException(status_code=502, detail=e.message) from e


@router.get("/tables", response_model=SchemaTablesResponse)
async def get_tables(
    entity_tables: Optional[str] = Query(
        None,
        description="Comma-separated list of entity tables to include (e.g., 'crm_deals,crm_contacts'). "
        "Related reference tables will be automatically included.",
    ),
    include_related: bool = Query(
        True,
        description="If true, automatically include related reference tables for specified entities",
    ),
) -> SchemaTablesResponse:
    """List CRM tables with columns (no AI).

    If entity_tables is specified, only those tables and their related reference tables
    will be included. For example, requesting 'crm_deals' will also include:
    - ref_crm_statuses (Statuses & Stages)
    - ref_crm_deal_categories (Deal Pipelines)
    - ref_crm_currencies (Currencies)
    - ref_enum_values (Enum Field Values)
    """
    table_filter = None
    if entity_tables:
        table_filter = [t.strip() for t in entity_tables.split(",") if t.strip()]

    tables_raw = await chart_service.get_tables_info(
        table_filter=table_filter, include_related=include_related
    )
    tables = [
        TableInfo(
            table_name=t["table_name"],
            columns=[ColumnInfo(**c) for c in t["columns"]],
            row_count=t.get("row_count"),
        )
        for t in tables_raw
    ]
    return SchemaTablesResponse(tables=tables)


@router.get("/history", response_model=SchemaDescriptionResponse)
async def get_schema_history(
    entity_tables: Optional[str] = Query(
        None,
        description="Comma-separated list of entity tables to filter by",
    ),
    include_related: bool = Query(
        True,
        description="Filter by include_related flag",
    ),
) -> SchemaDescriptionResponse:
    """Get the latest saved schema description matching the filter.

    Returns the most recently generated schema description that matches
    the specified entity_tables and include_related parameters.
    """
    table_filter = None
    if entity_tables:
        table_filter = [t.strip() for t in entity_tables.split(",") if t.strip()]

    saved = await chart_service.get_latest_schema_description(
        entity_filter=table_filter,
        include_related=include_related,
    )

    if not saved:
        raise HTTPException(
            status_code=404,
            detail="Не найдено сохранённых описаний схемы с указанными параметрами",
        )

    # Get current tables info
    tables_raw = await chart_service.get_tables_info(
        table_filter=table_filter, include_related=include_related
    )
    tables = [
        TableInfo(
            table_name=t["table_name"],
            columns=[ColumnInfo(**c) for c in t["columns"]],
            row_count=t.get("row_count"),
        )
        for t in tables_raw
    ]

    return SchemaDescriptionResponse(
        id=saved["id"],
        tables=tables,
        markdown=saved["markdown"],
        entity_filter=saved["entity_filter"],
        include_related=saved["include_related"],
        created_at=saved["created_at"],
        updated_at=saved["updated_at"],
    )


@router.patch("/{desc_id}", response_model=SchemaDescriptionResponse)
async def update_schema_description(
    desc_id: int = Path(..., description="Schema description ID"),
    update: SchemaDescriptionUpdate = Body(...),
) -> SchemaDescriptionResponse:
    """Update the markdown content of a saved schema description."""
    try:
        saved = await chart_service.update_schema_description(
            desc_id=desc_id,
            markdown=update.markdown,
        )

        # Parse entity_filter for getting tables
        table_filter = None
        if saved["entity_filter"]:
            table_filter = [
                t.strip() for t in saved["entity_filter"].split(",") if t.strip()
            ]

        tables_raw = await chart_service.get_tables_info(
            table_filter=table_filter, include_related=saved["include_related"]
        )
        tables = [
            TableInfo(
                table_name=t["table_name"],
                columns=[ColumnInfo(**c) for c in t["columns"]],
                row_count=t.get("row_count"),
            )
            for t in tables_raw
        ]

        return SchemaDescriptionResponse(
            id=saved["id"],
            tables=tables,
            markdown=saved["markdown"],
            entity_filter=saved["entity_filter"],
            include_related=saved["include_related"],
            created_at=saved["created_at"],
            updated_at=saved["updated_at"],
        )

    except ChartServiceError as e:
        logger.error("Chart service error", error=str(e))
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/list", response_model=SchemaDescriptionListResponse)
async def list_schema_descriptions() -> SchemaDescriptionListResponse:
    """Get a list of all saved schema descriptions."""
    from sqlalchemy import text

    from app.infrastructure.database.connection import get_engine

    engine = get_engine()

    query = text(
        "SELECT id, entity_filter, include_related, created_at, updated_at "
        "FROM schema_descriptions "
        "ORDER BY created_at DESC"
    )

    async with engine.begin() as conn:
        result = await conn.execute(query)
        rows = result.fetchall()

    items = [
        SchemaDescriptionListItem(
            id=row[0],
            entity_filter=row[1],
            include_related=bool(row[2]),
            created_at=row[3],
            updated_at=row[4],
        )
        for row in rows
    ]

    return SchemaDescriptionListResponse(items=items, total=len(items))
