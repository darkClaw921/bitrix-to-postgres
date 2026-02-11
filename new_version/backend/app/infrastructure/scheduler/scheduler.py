"""APScheduler integration for periodic sync jobs."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import text

from app.core.logging import get_logger

logger = get_logger(__name__)

# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """Get the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(
            timezone="UTC",
            job_defaults={
                "coalesce": True,  # Combine multiple missed runs into one
                "max_instances": 1,  # Only one instance per job at a time
                "misfire_grace_time": 60,  # Allow 60s grace for misfired jobs
            },
        )
    return _scheduler


async def sync_job(entity_type: str) -> None:
    """Job function for incremental sync — enqueues task to SyncQueue.

    Args:
        entity_type: Entity type to sync
    """
    from app.infrastructure.queue import SyncPriority, SyncTask, SyncTaskType, get_sync_queue

    logger.info("Scheduled sync job triggered", entity_type=entity_type)
    try:
        task = SyncTask(
            priority=SyncPriority.SCHEDULED,
            task_type=SyncTaskType.INCREMENTAL,
            entity_type=entity_type,
            sync_type="incremental",
        )
        result = await get_sync_queue().enqueue(task)
        logger.info(
            "Scheduled sync enqueued",
            entity_type=entity_type,
            enqueue_status=result["status"],
            task_id=result["task_id"],
        )
    except Exception as e:
        logger.error(
            "Failed to enqueue scheduled sync",
            entity_type=entity_type,
            error=str(e),
        )


async def load_sync_configs() -> list[dict[str, Any]]:
    """Load enabled sync configurations from database.

    Returns:
        List of sync config dictionaries
    """
    from app.infrastructure.database.connection import get_engine

    engine = get_engine()

    query = text(
        """
        SELECT entity_type, sync_interval_minutes, enabled
        FROM sync_config
        WHERE enabled = true
        """
    )

    async with engine.begin() as conn:
        result = await conn.execute(query)
        rows = result.fetchall()

    configs = []
    for row in rows:
        configs.append({
            "entity_type": row[0],
            "interval_minutes": row[1],
            "enabled": row[2],
        })

    return configs


async def schedule_sync_jobs() -> None:
    """Schedule sync jobs based on database configuration."""
    scheduler = get_scheduler()

    # Remove existing sync jobs
    for job in scheduler.get_jobs():
        if job.id.startswith("sync_"):
            scheduler.remove_job(job.id)

    # Load configs and schedule jobs
    configs = await load_sync_configs()

    for config in configs:
        entity_type = config["entity_type"]
        interval_minutes = config["interval_minutes"]

        job_id = f"sync_{entity_type}"

        scheduler.add_job(
            sync_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=job_id,
            name=f"Sync {entity_type}",
            kwargs={"entity_type": entity_type},
            replace_existing=True,
        )

        logger.info(
            "Scheduled sync job",
            entity_type=entity_type,
            interval_minutes=interval_minutes,
            job_id=job_id,
        )


async def reschedule_entity(entity_type: str, interval_minutes: int) -> None:
    """Reschedule a single entity sync job.

    Args:
        entity_type: Entity type
        interval_minutes: New interval in minutes
    """
    scheduler = get_scheduler()
    job_id = f"sync_{entity_type}"

    # Remove existing job if any
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    if interval_minutes > 0:
        scheduler.add_job(
            sync_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=job_id,
            name=f"Sync {entity_type}",
            kwargs={"entity_type": entity_type},
            replace_existing=True,
        )
        logger.info(
            "Rescheduled sync job",
            entity_type=entity_type,
            interval_minutes=interval_minutes,
        )


async def remove_entity_job(entity_type: str) -> None:
    """Remove a sync job for an entity.

    Args:
        entity_type: Entity type
    """
    scheduler = get_scheduler()
    job_id = f"sync_{entity_type}"

    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info("Removed sync job", entity_type=entity_type)


def start_scheduler() -> None:
    """Start the scheduler."""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler() -> None:
    """Stop the scheduler."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def get_scheduler_status() -> dict[str, Any]:
    """Get current scheduler status.

    Returns:
        Status dictionary with job information
    """
    scheduler = get_scheduler()

    jobs = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": next_run.isoformat() if next_run else None,
            "trigger": str(job.trigger),
        })

    return {
        "running": scheduler.running,
        "jobs": jobs,
        "job_count": len(jobs),
    }


async def trigger_sync_now(entity_type: str) -> None:
    """Manually trigger a sync job immediately.

    Args:
        entity_type: Entity type to sync
    """
    logger.info("Manually triggering sync", entity_type=entity_type)
    await sync_job(entity_type)
