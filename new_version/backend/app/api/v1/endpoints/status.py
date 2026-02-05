"""Monitoring and status endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.sync import (
    EntityStats,
    SyncHistoryResponse,
    SyncLogEntry,
    SyncStatsResponse,
)
from app.core.logging import get_logger
from app.domain.entities.base import EntityType
from app.infrastructure.database.connection import get_engine, get_session
from app.infrastructure.database.dynamic_table import DynamicTableBuilder
from app.infrastructure.scheduler import get_scheduler_status

logger = get_logger(__name__)

router = APIRouter()


@router.get("/history", response_model=SyncHistoryResponse)
async def get_sync_history(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    sync_type: Optional[str] = Query(None, description="Filter by sync type"),
    date_from: Optional[datetime] = Query(None, description="Start date filter"),
    date_to: Optional[datetime] = Query(None, description="End date filter"),
    session: AsyncSession = Depends(get_session),
) -> SyncHistoryResponse:
    """Get sync history logs with pagination and filters.

    Args:
        page: Page number (1-indexed)
        per_page: Number of items per page (max 100)
        entity_type: Filter by entity type (deal, contact, lead, company)
        status: Filter by status (running, completed, failed)
        sync_type: Filter by sync type (full, incremental, webhook)
        date_from: Start date for filtering
        date_to: End date for filtering
    """
    engine = get_engine()

    # Build WHERE clause
    conditions = []
    params: dict = {}

    if entity_type:
        conditions.append("entity_type = :entity_type")
        params["entity_type"] = entity_type
    if status:
        conditions.append("status = :status")
        params["status"] = status
    if sync_type:
        conditions.append("sync_type = :sync_type")
        params["sync_type"] = sync_type
    if date_from:
        conditions.append("started_at >= :date_from")
        params["date_from"] = date_from
    if date_to:
        conditions.append("started_at <= :date_to")
        params["date_to"] = date_to

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # Get total count
    count_query = text(f"SELECT COUNT(*) FROM sync_logs {where_clause}")

    async with engine.begin() as conn:
        result = await conn.execute(count_query, params)
        total = result.scalar() or 0

    # Calculate offset
    offset = (page - 1) * per_page
    params["limit"] = per_page
    params["offset"] = offset

    # Get paginated results
    data_query = text(
        f"""
        SELECT id, entity_type, sync_type, status, records_processed,
               error_message, started_at, completed_at
        FROM sync_logs
        {where_clause}
        ORDER BY started_at DESC NULLS LAST, id DESC
        LIMIT :limit OFFSET :offset
        """
    )

    async with engine.begin() as conn:
        result = await conn.execute(data_query, params)
        rows = result.fetchall()

    history = []
    for row in rows:
        history.append(
            SyncLogEntry(
                id=row[0],
                entity_type=row[1],
                sync_type=row[2],
                status=row[3],
                records_processed=row[4],
                error_message=row[5],
                started_at=row[6],
                completed_at=row[7],
            )
        )

    return SyncHistoryResponse(
        history=history,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/stats", response_model=SyncStatsResponse)
async def get_sync_stats(
    session: AsyncSession = Depends(get_session),
) -> SyncStatsResponse:
    """Get synchronization statistics per entity type.

    Returns total records count, last sync time, and last modified date
    for each entity type.
    """
    engine = get_engine()

    entities: dict[str, EntityStats] = {}
    total_records = 0

    for entity_type in EntityType.all():
        table_name = EntityType.get_table_name(entity_type)

        # Check if table exists
        if not await DynamicTableBuilder.table_exists(table_name):
            entities[entity_type] = EntityStats(count=0, last_sync=None, last_modified=None)
            continue

        # Get count from actual table
        try:
            count_query = text(f"SELECT COUNT(*) FROM {table_name}")
            async with engine.begin() as conn:
                result = await conn.execute(count_query)
                count = result.scalar() or 0
        except Exception:
            count = 0

        # Get last sync info from sync_state
        state_query = text(
            """
            SELECT last_modified_date, total_records
            FROM sync_state
            WHERE entity_type = :entity_type
            """
        )

        async with engine.begin() as conn:
            result = await conn.execute(state_query, {"entity_type": entity_type})
            state_row = result.fetchone()

        # Get last sync time from sync_config
        config_query = text(
            """
            SELECT last_sync_at
            FROM sync_config
            WHERE entity_type = :entity_type
            """
        )

        async with engine.begin() as conn:
            result = await conn.execute(config_query, {"entity_type": entity_type})
            config_row = result.fetchone()

        last_sync = config_row[0] if config_row else None
        last_modified = state_row[0] if state_row else None

        entities[entity_type] = EntityStats(
            count=count,
            last_sync=last_sync,
            last_modified=last_modified,
        )
        total_records += count

    return SyncStatsResponse(
        entities=entities,
        total_records=total_records,
    )


@router.get("/scheduler")
async def get_scheduler_info() -> dict:
    """Get scheduler status and job information."""
    return get_scheduler_status()


@router.get("/health")
async def detailed_health_check() -> dict:
    """Get detailed health check with database connectivity."""
    engine = get_engine()

    # Check database connection
    db_status = "connected"
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"

    # Get scheduler status
    scheduler = get_scheduler_status()

    # Count tables
    tables_query = text(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name LIKE 'crm_%'
        """
    )

    crm_tables = []
    try:
        async with engine.begin() as conn:
            result = await conn.execute(tables_query)
            crm_tables = [row[0] for row in result.fetchall()]
    except Exception:
        pass

    return {
        "status": "healthy" if db_status == "connected" else "unhealthy",
        "database": db_status,
        "scheduler": {
            "running": scheduler["running"],
            "jobs_count": scheduler["job_count"],
        },
        "crm_tables": crm_tables,
    }
