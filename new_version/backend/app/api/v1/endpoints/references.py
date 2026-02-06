"""Reference data synchronization endpoints."""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy import text

from app.core.logging import get_logger
from app.domain.entities.reference import get_all_reference_types, get_reference_type
from app.domain.services.reference_sync_service import ReferenceSyncService
from app.infrastructure.bitrix.client import BitrixClient
from app.infrastructure.database.connection import get_dialect, get_engine
from app.infrastructure.database.dynamic_table import DynamicTableBuilder

logger = get_logger(__name__)

router = APIRouter()

_running_ref_syncs: dict[str, bool] = {}


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

        async with engine.begin() as conn:
            result = await conn.execute(log_query, {"entity_type": entity_type})
            log_row = result.fetchone()

        # Get record count from actual table
        record_count = 0
        table_exists = await DynamicTableBuilder.table_exists(rt.table_name)
        if table_exists:
            try:
                count_query = text(f"SELECT COUNT(*) FROM {rt.table_name}")
                async with engine.begin() as conn:
                    result = await conn.execute(count_query)
                    record_count = result.scalar() or 0
            except Exception:
                pass

        is_running = _running_ref_syncs.get(name, False) or _running_ref_syncs.get("__all__", False)

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
        }

        statuses.append(status_info)

    return {"references": statuses}


async def _run_ref_sync(ref_name: str) -> None:
    """Background task to sync a single reference."""
    try:
        _running_ref_syncs[ref_name] = True
        service = ReferenceSyncService(bitrix_client=BitrixClient())
        await service.sync_reference(ref_name)
    finally:
        _running_ref_syncs.pop(ref_name, None)


async def _run_all_ref_sync() -> None:
    """Background task to sync all references."""
    try:
        _running_ref_syncs["__all__"] = True
        service = ReferenceSyncService(bitrix_client=BitrixClient())
        await service.sync_all_references()
    finally:
        _running_ref_syncs.pop("__all__", None)


@router.post("/sync/{ref_name}")
async def sync_reference(ref_name: str, background_tasks: BackgroundTasks) -> dict:
    """Start synchronization of a specific reference type."""
    if get_reference_type(ref_name) is None:
        available = list(get_all_reference_types().keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown reference type: {ref_name}. Available: {available}",
        )

    if _running_ref_syncs.get(ref_name):
        return {
            "status": "already_running",
            "ref_name": ref_name,
            "message": f"Sync for {ref_name} is already running",
        }

    background_tasks.add_task(_run_ref_sync, ref_name)

    logger.info("Reference sync started", ref_name=ref_name)

    return {
        "status": "started",
        "ref_name": ref_name,
        "message": f"Started sync for reference {ref_name}",
    }


@router.post("/sync-all")
async def sync_all_references(background_tasks: BackgroundTasks) -> dict:
    """Start synchronization of all reference types."""
    if _running_ref_syncs.get("__all__"):
        return {
            "status": "already_running",
            "message": "Reference sync-all is already running",
        }

    background_tasks.add_task(_run_all_ref_sync)

    logger.info("All references sync started")

    return {
        "status": "started",
        "message": "Started sync for all reference types",
        "reference_types": list(get_all_reference_types().keys()),
    }
