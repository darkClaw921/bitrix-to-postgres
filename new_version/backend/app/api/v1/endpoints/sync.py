"""Sync management endpoints."""

import asyncio
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
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
from app.domain.services.sync_service import SyncService
from app.infrastructure.bitrix.client import BitrixClient
from app.infrastructure.database.connection import get_engine, get_session
from app.infrastructure.scheduler import reschedule_entity, remove_entity_job

logger = get_logger(__name__)

router = APIRouter()

# Track currently running syncs
_running_syncs: dict[str, bool] = {}


@router.get("/config", response_model=SyncConfigResponse)
async def get_sync_config(
    session: AsyncSession = Depends(get_session),
) -> SyncConfigResponse:
    """Get current sync configuration for all entity types."""
    engine = get_engine()

    query = text(
        """
        SELECT entity_type, enabled, sync_interval_minutes, webhook_enabled, last_sync_at
        FROM sync_config
        ORDER BY entity_type
        """
    )

    async with engine.begin() as conn:
        result = await conn.execute(query)
        rows = result.fetchall()

    entities = []
    for row in rows:
        entities.append(
            SyncConfigItem(
                entity_type=row[0],
                enabled=row[1],
                sync_interval_minutes=row[2],
                webhook_enabled=row[3],
                last_sync_at=row[4],
            )
        )

    # If no configs exist, create defaults for all entity types
    if not entities:
        for entity_type in EntityType.all():
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
    # Validate entity type
    if config.entity_type not in EntityType.all():
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity type: {config.entity_type}. Must be one of: {EntityType.all()}",
        )

    engine = get_engine()

    # Build update fields dynamically
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

    # UPSERT the config
    updates.append("updated_at = NOW()")
    update_clause = ", ".join(updates)

    # Try to insert first, then update on conflict
    upsert_query = text(
        f"""
        INSERT INTO sync_config (entity_type, enabled, sync_interval_minutes, webhook_enabled)
        VALUES (:entity_type,
                COALESCE(:enabled, true),
                COALESCE(:sync_interval_minutes, 30),
                COALESCE(:webhook_enabled, true))
        ON CONFLICT (entity_type) DO UPDATE SET {update_clause}
        RETURNING entity_type, enabled, sync_interval_minutes, webhook_enabled, last_sync_at
        """
    )

    # Fill in missing params with None for the INSERT part
    params.setdefault("enabled", None)
    params.setdefault("sync_interval_minutes", None)
    params.setdefault("webhook_enabled", None)

    async with engine.begin() as conn:
        result = await conn.execute(upsert_query, params)
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=500, detail="Failed to update config")

    # Update scheduler based on new config
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


async def _run_sync(entity_type: str, sync_type: str) -> None:
    """Background task to run sync."""
    global _running_syncs
    try:
        _running_syncs[entity_type] = True
        bitrix_client = BitrixClient()
        sync_service = SyncService(bitrix_client=bitrix_client)

        if sync_type == "full":
            await sync_service.full_sync(entity_type)
        else:
            await sync_service.incremental_sync(entity_type)
    finally:
        _running_syncs.pop(entity_type, None)


@router.post("/start/{entity}", response_model=SyncStartResponse)
async def start_sync(
    entity: str,
    background_tasks: BackgroundTasks,
    request: SyncStartRequest = SyncStartRequest(),
    session: AsyncSession = Depends(get_session),
) -> SyncStartResponse:
    """Start synchronization for an entity.

    Args:
        entity: Entity type (deal, contact, lead, company)
        request: Sync request with sync_type (full or incremental)
    """
    # Validate entity type
    if entity not in EntityType.all():
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity type: {entity}. Must be one of: {EntityType.all()}",
        )

    # Validate sync type
    if request.sync_type not in ("full", "incremental"):
        raise HTTPException(
            status_code=400,
            detail="sync_type must be 'full' or 'incremental'",
        )

    # Check if already running
    if _running_syncs.get(entity):
        return SyncStartResponse(
            status="already_running",
            entity=entity,
            sync_type=request.sync_type,
            message=f"Sync for {entity} is already running",
        )

    # Start sync in background
    background_tasks.add_task(_run_sync, entity, request.sync_type)

    logger.info(
        "Sync started",
        entity_type=entity,
        sync_type=request.sync_type,
    )

    return SyncStartResponse(
        status="started",
        entity=entity,
        sync_type=request.sync_type,
        message=f"Started {request.sync_type} sync for {entity}",
    )


@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status(
    session: AsyncSession = Depends(get_session),
) -> SyncStatusResponse:
    """Get current sync status for all entity types."""
    engine = get_engine()

    # Get latest sync log for each entity type
    query = text(
        """
        WITH latest_logs AS (
            SELECT DISTINCT ON (entity_type)
                entity_type,
                sync_type,
                status,
                records_processed,
                error_message,
                started_at,
                completed_at
            FROM sync_logs
            ORDER BY entity_type, started_at DESC
        )
        SELECT
            sc.entity_type,
            COALESCE(ll.status, 'idle') as status,
            ll.sync_type,
            sc.last_sync_at,
            ll.records_processed,
            ll.error_message
        FROM sync_config sc
        LEFT JOIN latest_logs ll ON sc.entity_type = ll.entity_type
        WHERE sc.enabled = true
        ORDER BY sc.entity_type
        """
    )

    async with engine.begin() as conn:
        result = await conn.execute(query)
        rows = result.fetchall()

    entities = []
    overall_running = False

    for row in rows:
        entity_type = row[0]
        # Check if currently running in background
        is_running = _running_syncs.get(entity_type, False)
        status = "running" if is_running else row[1]
        if is_running:
            overall_running = True

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

    # If no enabled configs, return empty list with all entity types as idle
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
        overall_status="running" if overall_running else "idle",
        entities=entities,
    )


@router.get("/running")
async def get_running_syncs() -> dict:
    """Get list of currently running syncs."""
    return {
        "running_syncs": list(_running_syncs.keys()),
        "count": len(_running_syncs),
    }


@router.get("/validate/{entity}")
async def validate_entity_fields(
    entity: str,
) -> dict:
    """Validate field type conversion for an entity.

    Fetches sample records from Bitrix24 and tests type conversion
    to identify fields that fail validation.
    """
    from decimal import Decimal, InvalidOperation
    from dateutil import parser
    from app.infrastructure.database.dynamic_table import DynamicTableBuilder

    # Validate entity type
    if entity not in EntityType.all():
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity type. Must be one of: {', '.join(EntityType.all())}",
        )

    table_name = EntityType.get_table_name(entity)

    try:
        # Get sample records from Bitrix24
        bitrix = BitrixClient()
        all_records = await bitrix.get_entities(entity)
        # Take only first 10 records
        records = all_records[:10] if len(all_records) > 10 else all_records

        if not records:
            return {
                "entity_type": entity,
                "status": "no_records",
                "message": "No records found in Bitrix24",
                "validation_results": []
            }

        # Get table columns
        columns = await DynamicTableBuilder.get_table_columns(table_name)
        column_set = set(columns)

        # Field type mappings
        decimal_fields = {'opportunity', 'tax_value'}
        int_fields = {'probability'}
        datetime_fields = {
            'begindate', 'closedate', 'date_create', 'date_modify',
            'moved_time', 'last_activity_time', 'last_communication_time'
        }

        # Collect validation results
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

                # Track sample value
                if len(field_results[col_name]["sample_values"]) < 3:
                    field_results[col_name]["sample_values"].append(str(value)[:100])

                # Try conversion
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

        # Convert to list and sort by invalid count (descending)
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
