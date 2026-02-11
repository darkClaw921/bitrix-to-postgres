"""Reference data synchronization endpoints."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.core.logging import get_logger
from app.domain.entities.reference import get_all_reference_types, get_reference_type
from app.infrastructure.database.connection import get_dialect, get_engine
from app.infrastructure.database.dynamic_table import DynamicTableBuilder
from app.infrastructure.queue import SyncPriority, SyncTask, SyncTaskType, get_sync_queue

logger = get_logger(__name__)

router = APIRouter()


@router.get("/types")
async def list_reference_types() -> dict:
    """List all available reference types."""
    ref_types = get_all_reference_types()
    return {
        "reference_types": [
            {
                "name": rt.name,
                "table_name": rt.table_name,
                "api_method": rt.api_method,
                "unique_key": rt.unique_key,
                "fields_count": len(rt.fields),
                "auto_only": not bool(rt.api_method),
            }
            for rt in ref_types.values()
        ]
    }


@router.get("/status")
async def get_reference_status() -> dict:
    """Get sync status for all reference types."""
    engine = get_engine()
    dialect = get_dialect()
    ref_types = get_all_reference_types()
    statuses = []

    # Use a single connection for all queries
    async with engine.begin() as conn:
        for name, rt in ref_types.items():
            entity_type = f"ref:{name}"

            # Get last sync log
            if dialect == "mysql":
                log_query = text(
                    "SELECT status, sync_type, records_processed, error_message, "
                    "       started_at, completed_at "
                    "FROM sync_logs "
                    "WHERE entity_type = :entity_type "
                    "ORDER BY started_at DESC LIMIT 1"
                )
            else:
                log_query = text(
                    "SELECT status, sync_type, records_processed, error_message, "
                    "       started_at, completed_at "
                    "FROM sync_logs "
                    "WHERE entity_type = :entity_type "
                    "ORDER BY started_at DESC NULLS LAST LIMIT 1"
                )

            result = await conn.execute(log_query, {"entity_type": entity_type})
            log_row = result.fetchone()

            # Get record count from actual table
            record_count = 0
            table_exists = await DynamicTableBuilder.table_exists(rt.table_name)
            if table_exists:
                try:
                    count_query = text(f"SELECT COUNT(*) FROM {rt.table_name}")
                    result = await conn.execute(count_query)
                    record_count = result.scalar() or 0
                except Exception:
                    pass

            sync_queue = get_sync_queue()
            ref_entity = f"ref:{name}"
            is_running = sync_queue.is_entity_running(ref_entity) or sync_queue.is_entity_running("__all_refs__")

            status_info = {
                "name": name,
                "table_name": rt.table_name,
                "table_exists": table_exists,
                "record_count": record_count,
                "status": "running" if is_running else (log_row[0] if log_row else "idle"),
                "last_sync_type": log_row[1] if log_row else None,
                "records_synced": log_row[2] if log_row else None,
                "error_message": log_row[3] if log_row and log_row[0] == "failed" else None,
                "last_sync_at": log_row[4].isoformat() if log_row and log_row[4] else None,
                "completed_at": log_row[5].isoformat() if log_row and log_row[5] else None,
                "auto_only": not bool(rt.api_method),
            }

            statuses.append(status_info)

    return {"references": statuses}


@router.post("/sync/{ref_name}")
async def sync_reference(ref_name: str) -> dict:
    """Start synchronization of a specific reference type."""
    ref_type = get_reference_type(ref_name)
    if ref_type is None:
        available = list(get_all_reference_types().keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown reference type: {ref_name}. Available: {available}",
        )

    if not ref_type.api_method:
        raise HTTPException(
            status_code=400,
            detail=f"Reference type '{ref_name}' is auto-only and syncs automatically during full_sync",
        )

    task = SyncTask(
        priority=SyncPriority.REFERENCE,
        task_type=SyncTaskType.REFERENCE,
        entity_type=ref_name,
        sync_type="reference",
    )

    result = await get_sync_queue().enqueue(task)

    status_map = {
        "queued": "started",
        "already_running": "already_running",
        "duplicate": "already_queued",
    }
    status = status_map.get(result["status"], result["status"])

    logger.info("Reference sync enqueued", ref_name=ref_name, status=status)

    return {
        "status": status,
        "ref_name": ref_name,
        "task_id": result["task_id"],
        "message": f"Reference sync for {ref_name}: {status}",
    }


@router.post("/sync-all")
async def sync_all_references() -> dict:
    """Start synchronization of all reference types."""
    task = SyncTask(
        priority=SyncPriority.REFERENCE,
        task_type=SyncTaskType.REFERENCE_ALL,
        entity_type="__all_refs__",
        sync_type="reference",
    )

    result = await get_sync_queue().enqueue(task)

    status_map = {
        "queued": "started",
        "already_running": "already_running",
        "duplicate": "already_queued",
    }
    status = status_map.get(result["status"], result["status"])

    logger.info("All references sync enqueued", status=status)

    return {
        "status": status,
        "task_id": result["task_id"],
        "message": f"Sync all references: {status}",
        "reference_types": list(get_all_reference_types().keys()),
    }
