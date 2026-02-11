"""Sync management endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.sync import (
    SyncConfigItem,
    SyncConfigResponse,
    SyncConfigUpdateRequest,
    SyncStartRequest,
    SyncStartResponse,
    SyncStatusItem,
    SyncStatusResponse,
)
from app.core.logging import get_logger
from app.domain.entities.base import EntityType
from app.infrastructure.bitrix.client import BitrixClient
from app.infrastructure.database.connection import get_dialect, get_engine, get_session
from app.infrastructure.queue import SyncPriority, SyncTask, SyncTaskType, get_sync_queue
from app.infrastructure.scheduler import reschedule_entity, remove_entity_job

logger = get_logger(__name__)

router = APIRouter()


@router.get("/config", response_model=SyncConfigResponse)
async def get_sync_config(
    session: AsyncSession = Depends(get_session),
) -> SyncConfigResponse:
    """Get current sync configuration for all entity types."""
    engine = get_engine()

    query = text(
        "SELECT entity_type, enabled, sync_interval_minutes, webhook_enabled, last_sync_at "
        "FROM sync_config "
        "ORDER BY entity_type"
    )

    async with engine.begin() as conn:
        result = await conn.execute(query)
        rows = result.fetchall()

    entities = []
    existing_types = set()
    for row in rows:
        existing_types.add(row[0])
        entities.append(
            SyncConfigItem(
                entity_type=row[0],
                enabled=row[1],
                sync_interval_minutes=row[2],
                webhook_enabled=row[3],
                last_sync_at=row[4],
            )
        )

    # Add default entries for any entity types missing from DB
    for entity_type in EntityType.all():
        if entity_type not in existing_types:
            entities.append(
                SyncConfigItem(
                    entity_type=entity_type,
                    enabled=False,
                    sync_interval_minutes=30,
                    webhook_enabled=True,
                    last_sync_at=None,
                )
            )

    return SyncConfigResponse(entities=entities, default_interval_minutes=30)


@router.put("/config", response_model=SyncConfigItem)
async def update_sync_config(
    config: SyncConfigUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> SyncConfigItem:
    """Update sync configuration for an entity type."""
    if config.entity_type not in EntityType.all():
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity type: {config.entity_type}. Must be one of: {EntityType.all()}",
        )

    engine = get_engine()
    dialect = get_dialect()

    updates = []
    params: dict = {"entity_type": config.entity_type}

    if config.enabled is not None:
        updates.append("enabled = :enabled")
        params["enabled"] = config.enabled
    if config.sync_interval_minutes is not None:
        updates.append("sync_interval_minutes = :sync_interval_minutes")
        params["sync_interval_minutes"] = config.sync_interval_minutes
    if config.webhook_enabled is not None:
        updates.append("webhook_enabled = :webhook_enabled")
        params["webhook_enabled"] = config.webhook_enabled

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at = NOW()")
    update_clause = ", ".join(updates)

    params.setdefault("enabled", None)
    params.setdefault("sync_interval_minutes", None)
    params.setdefault("webhook_enabled", None)

    if dialect == "mysql":
        # MySQL: INSERT ... ON DUPLICATE KEY UPDATE, then SELECT
        upsert_query = text(
            f"INSERT INTO sync_config (entity_type, enabled, sync_interval_minutes, webhook_enabled) "
            f"VALUES (:entity_type, "
            f"        COALESCE(:enabled, 1), "
            f"        COALESCE(:sync_interval_minutes, 30), "
            f"        COALESCE(:webhook_enabled, 1)) "
            f"ON DUPLICATE KEY UPDATE {update_clause}"
        )
        async with engine.begin() as conn:
            await conn.execute(upsert_query, params)

        select_query = text(
            "SELECT entity_type, enabled, sync_interval_minutes, webhook_enabled, last_sync_at "
            "FROM sync_config WHERE entity_type = :entity_type"
        )
        async with engine.begin() as conn:
            result = await conn.execute(select_query, {"entity_type": config.entity_type})
            row = result.fetchone()
    else:
        # PostgreSQL: INSERT ... ON CONFLICT ... RETURNING
        upsert_query = text(
            f"INSERT INTO sync_config (entity_type, enabled, sync_interval_minutes, webhook_enabled) "
            f"VALUES (:entity_type, "
            f"        COALESCE(:enabled, true), "
            f"        COALESCE(:sync_interval_minutes, 30), "
            f"        COALESCE(:webhook_enabled, true)) "
            f"ON CONFLICT (entity_type) DO UPDATE SET {update_clause} "
            f"RETURNING entity_type, enabled, sync_interval_minutes, webhook_enabled, last_sync_at"
        )
        async with engine.begin() as conn:
            result = await conn.execute(upsert_query, params)
            row = result.fetchone()

    if not row:
        raise HTTPException(status_code=500, detail="Failed to update config")

    if row[1]:  # enabled
        await reschedule_entity(row[0], row[2])
    else:
        await remove_entity_job(row[0])

    logger.info(
        "Sync config updated",
        entity_type=row[0],
        enabled=row[1],
        interval=row[2],
    )

    return SyncConfigItem(
        entity_type=row[0],
        enabled=row[1],
        sync_interval_minutes=row[2],
        webhook_enabled=row[3],
        last_sync_at=row[4],
    )


@router.post("/start/{entity}", response_model=SyncStartResponse)
async def start_sync(
    entity: str,
    request: SyncStartRequest = SyncStartRequest(),
    session: AsyncSession = Depends(get_session),
) -> SyncStartResponse:
    """Start synchronization for an entity."""
    if entity not in EntityType.all():
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity type: {entity}. Must be one of: {EntityType.all()}",
        )

    if request.sync_type not in ("full", "incremental"):
        raise HTTPException(
            status_code=400,
            detail="sync_type must be 'full' or 'incremental'",
        )

    task_type = SyncTaskType.FULL if request.sync_type == "full" else SyncTaskType.INCREMENTAL
    payload: dict = {}
    if request.filter:
        payload["filter"] = {
            "field": request.filter.field,
            "operator": request.filter.operator,
            "value": request.filter.value,
        }
    task = SyncTask(
        priority=SyncPriority.MANUAL,
        task_type=task_type,
        entity_type=entity,
        sync_type=request.sync_type,
        payload=payload,
    )

    result = await get_sync_queue().enqueue(task)

    status_map = {
        "queued": "started",
        "already_running": "already_running",
        "duplicate": "already_queued",
    }
    status = status_map.get(result["status"], result["status"])

    logger.info(
        "Sync enqueued",
        entity_type=entity,
        sync_type=request.sync_type,
        status=status,
        task_id=result["task_id"],
    )

    return SyncStartResponse(
        status=status,
        entity=entity,
        sync_type=request.sync_type,
        task_id=result["task_id"],
        message=f"{request.sync_type} sync for {entity}: {status}",
    )


@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status(
    session: AsyncSession = Depends(get_session),
) -> SyncStatusResponse:
    """Get current sync status for all entity types."""
    engine = get_engine()
    dialect = get_dialect()

    if dialect == "mysql":
        # MySQL: use subquery with MAX instead of DISTINCT ON
        query = text(
            "SELECT "
            "    sc.entity_type, "
            "    COALESCE(ll.status, 'idle') as status, "
            "    ll.sync_type, "
            "    sc.last_sync_at, "
            "    ll.records_processed, "
            "    ll.error_message "
            "FROM sync_config sc "
            "LEFT JOIN ( "
            "    SELECT sl.* FROM sync_logs sl "
            "    INNER JOIN ( "
            "        SELECT entity_type, MAX(started_at) as max_started "
            "        FROM sync_logs GROUP BY entity_type "
            "    ) latest ON sl.entity_type = latest.entity_type "
            "        AND sl.started_at = latest.max_started "
            ") ll ON sc.entity_type = ll.entity_type "
            "WHERE sc.enabled = 1 "
            "ORDER BY sc.entity_type"
        )
    else:
        # PostgreSQL: DISTINCT ON
        query = text(
            "WITH latest_logs AS ( "
            "    SELECT DISTINCT ON (entity_type) "
            "        entity_type, sync_type, status, records_processed, "
            "        error_message, started_at, completed_at "
            "    FROM sync_logs "
            "    ORDER BY entity_type, started_at DESC "
            ") "
            "SELECT "
            "    sc.entity_type, "
            "    COALESCE(ll.status, 'idle') as status, "
            "    ll.sync_type, "
            "    sc.last_sync_at, "
            "    ll.records_processed, "
            "    ll.error_message "
            "FROM sync_config sc "
            "LEFT JOIN latest_logs ll ON sc.entity_type = ll.entity_type "
            "WHERE sc.enabled = true "
            "ORDER BY sc.entity_type"
        )

    async with engine.begin() as conn:
        result = await conn.execute(query)
        rows = result.fetchall()

    entities = []
    overall_running = False
    sync_queue = get_sync_queue()

    overall_queued = False

    for row in rows:
        entity_type = row[0]
        is_running = sync_queue.is_entity_running(entity_type)
        is_queued = sync_queue.is_entity_queued(entity_type)
        if is_running:
            status = "running"
            overall_running = True
        elif is_queued:
            status = "queued"
            overall_queued = True
        else:
            status = row[1]

        entities.append(
            SyncStatusItem(
                entity_type=entity_type,
                status=status,
                last_sync_type=row[2],
                last_sync_at=row[3],
                records_synced=row[4],
                error_message=row[5] if status == "failed" else None,
            )
        )

    if not entities:
        for entity_type in EntityType.all():
            entities.append(
                SyncStatusItem(
                    entity_type=entity_type,
                    status="idle",
                    last_sync_type=None,
                    last_sync_at=None,
                    records_synced=None,
                    error_message=None,
                )
            )

    return SyncStatusResponse(
        overall_status="running" if overall_running else "queued" if overall_queued else "idle",
        entities=entities,
    )


@router.get("/running")
async def get_running_syncs() -> dict:
    """Get list of currently running syncs and queue status."""
    sync_queue = get_sync_queue()
    queue_status = sync_queue.get_status()
    running_entities = sync_queue.get_running_entities()
    return {
        "running_syncs": running_entities,
        "count": len(running_entities),
        "queue": queue_status,
    }


@router.get("/validate/{entity}")
async def validate_entity_fields(
    entity: str,
) -> dict:
    """Validate field type conversion for an entity."""
    from decimal import Decimal, InvalidOperation
    from dateutil import parser
    from app.infrastructure.database.dynamic_table import DynamicTableBuilder

    if entity not in EntityType.all():
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity type. Must be one of: {', '.join(EntityType.all())}",
        )

    table_name = EntityType.get_table_name(entity)

    try:
        bitrix = BitrixClient()
        all_records = await bitrix.get_entities(entity)
        records = all_records[:10] if len(all_records) > 10 else all_records

        if not records:
            return {
                "entity_type": entity,
                "status": "no_records",
                "message": "No records found in Bitrix24",
                "validation_results": []
            }

        columns = await DynamicTableBuilder.get_table_columns(table_name)
        column_set = set(columns)

        decimal_fields = {'opportunity', 'tax_value'}
        int_fields = {'probability'}
        datetime_fields = {
            'begindate', 'closedate', 'date_create', 'date_modify',
            'moved_time', 'last_activity_time', 'last_communication_time'
        }

        field_results = {}

        for record in records:
            for key, value in record.items():
                col_name = key.lower()

                if col_name == "id" or col_name not in column_set:
                    continue

                if col_name not in field_results:
                    field_results[col_name] = {
                        "field_name": col_name,
                        "original_key": key,
                        "sample_values": [],
                        "valid_count": 0,
                        "invalid_count": 0,
                        "errors": []
                    }

                if len(field_results[col_name]["sample_values"]) < 3:
                    field_results[col_name]["sample_values"].append(str(value)[:100])

                try:
                    if value == "" or value is None:
                        field_results[col_name]["valid_count"] += 1
                    elif col_name in decimal_fields and isinstance(value, str):
                        Decimal(value)
                        field_results[col_name]["valid_count"] += 1
                    elif col_name in int_fields and isinstance(value, str):
                        int(value)
                        field_results[col_name]["valid_count"] += 1
                    elif col_name in datetime_fields and isinstance(value, str):
                        parser.parse(value)
                        field_results[col_name]["valid_count"] += 1
                    else:
                        field_results[col_name]["valid_count"] += 1
                except Exception as e:
                    field_results[col_name]["invalid_count"] += 1
                    error_msg = f"{type(e).__name__}: {str(e)}"
                    if error_msg not in field_results[col_name]["errors"]:
                        field_results[col_name]["errors"].append(error_msg)

        validation_results = sorted(
            field_results.values(),
            key=lambda x: x["invalid_count"],
            reverse=True
        )

        total_fields = len(field_results)
        failed_fields = sum(1 for r in validation_results if r["invalid_count"] > 0)

        return {
            "entity_type": entity,
            "status": "completed",
            "records_tested": len(records),
            "total_fields": total_fields,
            "failed_fields": failed_fields,
            "success_rate": f"{((total_fields - failed_fields) / total_fields * 100):.1f}%" if total_fields > 0 else "0%",
            "validation_results": validation_results
        }

    except Exception as e:
        logger.error("Validation failed", entity_type=entity, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Validation failed: {str(e)}"
        )
