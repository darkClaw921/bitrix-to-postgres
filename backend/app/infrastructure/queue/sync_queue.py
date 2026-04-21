"""Sync queue for sequential heavy task execution and parallel webhook processing."""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum, Enum
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class SyncPriority(IntEnum):
    """Priority levels for sync tasks. Lower value = higher priority."""

    WEBHOOK = 0
    MANUAL = 10
    REFERENCE = 20
    SCHEDULED = 30


class SyncTaskType(str, Enum):
    """Types of sync tasks."""

    FULL = "full"
    INCREMENTAL = "incremental"
    WEBHOOK = "webhook"
    WEBHOOK_DELETE = "webhook_delete"
    REFERENCE = "reference"
    REFERENCE_ALL = "reference_all"


@dataclass(order=True)
class SyncTask:
    """A sync task to be queued for execution."""

    priority: int
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()), compare=False)
    task_type: SyncTaskType = field(default=SyncTaskType.FULL, compare=False)
    entity_type: str = field(default="", compare=False)
    sync_type: str = field(default="full", compare=False)
    payload: dict[str, Any] = field(default_factory=dict, compare=False)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc), compare=False
    )

    @property
    def dedup_key(self) -> str:
        """Key for deduplication. Same key = duplicate task."""
        return f"{self.task_type.value}:{self.entity_type}"

    @property
    def is_webhook(self) -> bool:
        return self.task_type in (SyncTaskType.WEBHOOK, SyncTaskType.WEBHOOK_DELETE)


class SyncQueue:
    """Central sync queue with two channels: heavy (sequential) and webhook (parallel)."""

    def __init__(self) -> None:
        self._heavy_queue: asyncio.PriorityQueue[SyncTask] = asyncio.PriorityQueue()
        self._webhook_queue: asyncio.Queue[SyncTask] = asyncio.Queue()

        self._current_heavy_task: SyncTask | None = None
        self._pending_heavy_keys: dict[str, str] = {}  # dedup_key -> task_id

        self._heavy_worker_task: asyncio.Task | None = None
        self._webhook_worker_task: asyncio.Task | None = None
        self._running = False

        self._webhook_semaphore = asyncio.Semaphore(3)

    async def start(self) -> None:
        """Start queue workers."""
        if self._running:
            return
        self._running = True
        self._heavy_worker_task = asyncio.create_task(
            self._heavy_worker(), name="sync_queue_heavy_worker"
        )
        self._webhook_worker_task = asyncio.create_task(
            self._webhook_worker(), name="sync_queue_webhook_worker"
        )
        logger.info("SyncQueue started")

    async def stop(self) -> None:
        """Stop queue workers gracefully."""
        if not self._running:
            return
        self._running = False

        if self._heavy_worker_task:
            self._heavy_worker_task.cancel()
            try:
                await self._heavy_worker_task
            except asyncio.CancelledError:
                pass
            self._heavy_worker_task = None

        if self._webhook_worker_task:
            self._webhook_worker_task.cancel()
            try:
                await self._webhook_worker_task
            except asyncio.CancelledError:
                pass
            self._webhook_worker_task = None

        logger.info("SyncQueue stopped")

    async def enqueue(self, task: SyncTask) -> dict[str, Any]:
        """Add a task to the appropriate queue.

        Returns:
            Dict with status and task_id.
        """
        if task.is_webhook:
            await self._webhook_queue.put(task)
            logger.info(
                "Webhook task queued",
                task_id=task.task_id,
                task_type=task.task_type.value,
                entity_type=task.entity_type,
            )
            return {"status": "queued", "task_id": task.task_id}

        # Heavy task: check deduplication
        dedup_key = task.dedup_key

        # Check if same task is currently running
        if self._current_heavy_task and self._current_heavy_task.dedup_key == dedup_key:
            logger.info(
                "Task already running",
                task_type=task.task_type.value,
                entity_type=task.entity_type,
            )
            return {
                "status": "already_running",
                "task_id": self._current_heavy_task.task_id,
            }

        # Check if same task is already in queue
        if dedup_key in self._pending_heavy_keys:
            logger.info(
                "Duplicate task already in queue",
                task_type=task.task_type.value,
                entity_type=task.entity_type,
            )
            return {
                "status": "duplicate",
                "task_id": self._pending_heavy_keys[dedup_key],
            }

        self._pending_heavy_keys[dedup_key] = task.task_id
        await self._heavy_queue.put(task)

        logger.info(
            "Heavy task queued",
            task_id=task.task_id,
            task_type=task.task_type.value,
            entity_type=task.entity_type,
            queue_size=self._heavy_queue.qsize(),
        )

        return {"status": "queued", "task_id": task.task_id}

    def get_status(self) -> dict[str, Any]:
        """Get current queue status."""
        return {
            "running": self._running,
            "heavy_queue_size": self._heavy_queue.qsize(),
            "webhook_queue_size": self._webhook_queue.qsize(),
            "current_heavy_task": (
                {
                    "task_id": self._current_heavy_task.task_id,
                    "task_type": self._current_heavy_task.task_type.value,
                    "entity_type": self._current_heavy_task.entity_type,
                    "started_at": self._current_heavy_task.created_at.isoformat(),
                }
                if self._current_heavy_task
                else None
            ),
            "pending_heavy_keys": list(self._pending_heavy_keys.keys()),
        }

    def is_entity_running(self, entity_type: str) -> bool:
        """Check if a heavy sync is currently running for the given entity type."""
        if self._current_heavy_task and self._current_heavy_task.entity_type == entity_type:
            return True
        return False

    def is_entity_queued(self, entity_type: str) -> bool:
        """Check if a heavy sync is queued for the given entity type."""
        for key in self._pending_heavy_keys:
            if key.endswith(f":{entity_type}"):
                return True
        return False

    def get_running_entities(self) -> list[str]:
        """Get list of entity types with running or queued heavy tasks."""
        entities = set()
        if self._current_heavy_task:
            entities.add(self._current_heavy_task.entity_type)
        for key in self._pending_heavy_keys:
            parts = key.split(":", 1)
            if len(parts) == 2:
                entities.add(parts[1])
        return list(entities)

    async def _heavy_worker(self) -> None:
        """Worker that processes heavy tasks one at a time."""
        logger.info("Heavy worker started")
        while self._running:
            try:
                task = await asyncio.wait_for(
                    self._heavy_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            # Remove from pending keys
            self._pending_heavy_keys.pop(task.dedup_key, None)
            self._current_heavy_task = task

            logger.info(
                "Heavy worker executing task",
                task_id=task.task_id,
                task_type=task.task_type.value,
                entity_type=task.entity_type,
            )

            try:
                await self._execute_task(task)
            except Exception as e:
                logger.error(
                    "Heavy task failed",
                    task_id=task.task_id,
                    task_type=task.task_type.value,
                    entity_type=task.entity_type,
                    error=str(e),
                )
            finally:
                self._current_heavy_task = None
                self._heavy_queue.task_done()

        logger.info("Heavy worker stopped")

    async def _webhook_worker(self) -> None:
        """Worker that processes webhooks with limited parallelism."""
        logger.info("Webhook worker started")
        tasks: set[asyncio.Task] = set()

        while self._running:
            try:
                task = await asyncio.wait_for(
                    self._webhook_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            await self._webhook_semaphore.acquire()
            t = asyncio.create_task(self._run_webhook_task(task))
            tasks.add(t)
            t.add_done_callback(tasks.discard)

        # Wait for remaining tasks
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Webhook worker stopped")

    async def _run_webhook_task(self, task: SyncTask) -> None:
        """Execute a single webhook task with semaphore release."""
        try:
            await self._execute_task(task)
        except Exception as e:
            logger.error(
                "Webhook task failed",
                task_id=task.task_id,
                entity_type=task.entity_type,
                error=str(e),
            )
        finally:
            self._webhook_semaphore.release()
            self._webhook_queue.task_done()

    async def _execute_task(self, task: SyncTask) -> None:
        """Execute a sync task by dispatching to the appropriate service."""
        from app.domain.services.sync_service import SyncService
        from app.domain.services.reference_sync_service import ReferenceSyncService
        from app.infrastructure.bitrix.client import BitrixClient

        if task.task_type == SyncTaskType.FULL:
            bitrix_client = BitrixClient()
            sync_service = SyncService(bitrix_client=bitrix_client)
            # Extract filter from payload if present
            filter_params = None
            if task.payload.get("filter"):
                f = task.payload["filter"]
                filter_params = {f"{f['operator']}{f['field']}": f["value"]}
            await sync_service.full_sync(task.entity_type, filter_params=filter_params)

        elif task.task_type == SyncTaskType.INCREMENTAL:
            bitrix_client = BitrixClient()
            sync_service = SyncService(bitrix_client=bitrix_client)
            await sync_service.incremental_sync(task.entity_type)

        elif task.task_type == SyncTaskType.WEBHOOK:
            from app.api.v1.endpoints.webhooks import process_webhook_event

            await process_webhook_event(task.payload)

        elif task.task_type == SyncTaskType.WEBHOOK_DELETE:
            from app.api.v1.endpoints.webhooks import process_webhook_event

            await process_webhook_event(task.payload)

        elif task.task_type == SyncTaskType.REFERENCE:
            bitrix_client = BitrixClient()
            ref_service = ReferenceSyncService(bitrix_client=bitrix_client)
            await ref_service.sync_reference(task.entity_type)

        elif task.task_type == SyncTaskType.REFERENCE_ALL:
            bitrix_client = BitrixClient()
            ref_service = ReferenceSyncService(bitrix_client=bitrix_client)
            await ref_service.sync_all_references()

        logger.info(
            "Task completed",
            task_id=task.task_id,
            task_type=task.task_type.value,
            entity_type=task.entity_type,
        )


# Singleton
_sync_queue: SyncQueue | None = None


def get_sync_queue() -> SyncQueue:
    """Get the singleton SyncQueue instance."""
    global _sync_queue
    if _sync_queue is None:
        _sync_queue = SyncQueue()
    return _sync_queue
