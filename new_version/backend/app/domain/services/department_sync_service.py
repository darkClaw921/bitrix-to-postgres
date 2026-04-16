"""Service for synchronizing Bitrix24 department hierarchy.

Синхронизирует отделы из Bitrix24 (``department.get``) в таблицу
``bitrix_departments``. Таблица-справочник уже создана миграцией
``023_create_bitrix_departments_table.py`` — сервис только читает из
Bitrix24 и делает UPSERT по уникальному ключу ``bitrix_id``.

Поддерживает оба диалекта БД: UPSERT через ``ON CONFLICT DO UPDATE`` (PG)
и ``ON DUPLICATE KEY UPDATE`` (MySQL). Логирует в ``sync_logs`` с
``entity_type='ref:department'`` (тот же паттерн, что и у
``ReferenceSyncService``, чтобы эндпоинты ``/sync/status`` и
``/references/status`` видели состояние синхронизации).

Дедупликация одновременных sync-триггеров обеспечивается классовым
словарём ``_running_syncs`` (entity_type → task_id). При дубликате
возвращается статус ``already_running`` без запуска второго full_sync.
"""

from typing import Any

from sqlalchemy import text

from app.core.exceptions import SyncError
from app.core.logging import get_logger
from app.infrastructure.bitrix.client import BitrixClient
from app.infrastructure.database.connection import get_dialect, get_engine

logger = get_logger(__name__)


class DepartmentSyncService:
    """Service for synchronizing Bitrix24 departments to bitrix_departments table."""

    # Entity type marker for sync_logs
    ENTITY_TYPE: str = "ref:department"

    # Class-level tracking of in-flight syncs (entity_type → arbitrary token).
    # Used by API endpoints to short-circuit concurrent triggers without
    # relying on the global SyncQueue (keeps department sync self-contained).
    _running_syncs: dict[str, bool] = {}

    def __init__(self, bitrix_client: BitrixClient | None = None):
        self._bitrix = bitrix_client or BitrixClient()

    @classmethod
    def is_running(cls) -> bool:
        """Return True if a department sync is currently in progress."""
        return cls._running_syncs.get(cls.ENTITY_TYPE, False)

    async def full_sync(self) -> dict[str, Any]:
        """Fetch all departments from Bitrix24 and UPSERT into bitrix_departments.

        Returns a summary dict with status, records_fetched, records_processed.
        Raises SyncError on failure (sync_log is already marked 'failed' in that case).
        """
        if self._running_syncs.get(self.ENTITY_TYPE, False):
            logger.info("Department sync already running, skipping duplicate")
            return {"status": "already_running", "entity_type": self.ENTITY_TYPE}

        self._running_syncs[self.ENTITY_TYPE] = True
        logger.info("Starting department full sync")

        sync_log_id = await self._create_sync_log()

        try:
            records = await self._fetch_departments()
            logger.info("Departments fetched", count=len(records))

            processed = await self._upsert_departments(records)
            logger.info("Departments upserted", processed=processed)

            await self._complete_sync_log(
                sync_log_id, "completed", processed, records_fetched=len(records)
            )

            return {
                "status": "completed",
                "entity_type": self.ENTITY_TYPE,
                "records_fetched": len(records),
                "records_processed": processed,
            }

        except Exception as e:
            logger.error("Department sync failed", error=str(e))
            await self._complete_sync_log(
                sync_log_id, "failed", 0, error_message=str(e), records_fetched=0
            )
            raise SyncError(f"Department sync failed: {str(e)}") from e

        finally:
            self._running_syncs.pop(self.ENTITY_TYPE, None)

    async def _fetch_departments(self) -> list[dict[str, Any]]:
        """Fetch all departments via Bitrix24 department.get (with pagination)."""
        # department.get supports pagination via fast-bitrix24 get_all.
        # No FILTER required — we pull the full list every sync.
        return await self._bitrix.get_all("department.get", params={})

    async def _upsert_departments(
        self, records: list[dict[str, Any]]
    ) -> int:
        """UPSERT each department row by bitrix_id (dialect-aware)."""
        if not records:
            return 0

        engine = get_engine()
        dialect = get_dialect()
        processed = 0

        async with engine.begin() as conn:
            for record in records:
                data = self._normalize_record(record)
                if data["bitrix_id"] is None:
                    continue

                if dialect == "mysql":
                    query = text(
                        "INSERT INTO bitrix_departments "
                        "(bitrix_id, name, parent_id, sort, uf_head) "
                        "VALUES (:bitrix_id, :name, :parent_id, :sort, :uf_head) "
                        "ON DUPLICATE KEY UPDATE "
                        "    name = VALUES(name), "
                        "    parent_id = VALUES(parent_id), "
                        "    sort = VALUES(sort), "
                        "    uf_head = VALUES(uf_head), "
                        "    updated_at = NOW()"
                    )
                else:
                    query = text(
                        "INSERT INTO bitrix_departments "
                        "(bitrix_id, name, parent_id, sort, uf_head) "
                        "VALUES (:bitrix_id, :name, :parent_id, :sort, :uf_head) "
                        "ON CONFLICT (bitrix_id) DO UPDATE SET "
                        "    name = EXCLUDED.name, "
                        "    parent_id = EXCLUDED.parent_id, "
                        "    sort = EXCLUDED.sort, "
                        "    uf_head = EXCLUDED.uf_head, "
                        "    updated_at = NOW()"
                    )

                await conn.execute(query, data)
                processed += 1

        return processed

    @staticmethod
    def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
        """Map Bitrix24 department dict → column-level dict.

        Empty strings / None / 0 "parent" / empty UF_HEAD are normalized to None.
        ``bitrix_id`` is always stored as ``str(int)``.
        """
        raw_id = record.get("ID")
        bitrix_id = str(raw_id) if raw_id not in (None, "") else None

        name_raw = record.get("NAME")
        name = name_raw if name_raw not in (None, "") else None

        parent_raw = record.get("PARENT")
        # Bitrix24 может вернуть пустую строку у корневого отдела — нормализуем в NULL
        parent_id = (
            str(parent_raw) if parent_raw not in (None, "", 0, "0") else None
        )

        sort_raw = record.get("SORT")
        try:
            sort = int(sort_raw) if sort_raw not in (None, "") else 500
        except (TypeError, ValueError):
            sort = 500

        head_raw = record.get("UF_HEAD")
        uf_head = str(head_raw) if head_raw not in (None, "", 0, "0") else None

        return {
            "bitrix_id": bitrix_id,
            "name": name,
            "parent_id": parent_id,
            "sort": sort,
            "uf_head": uf_head,
        }

    async def _create_sync_log(self) -> int:
        """Insert a 'running' row into sync_logs and return its id (dialect-aware)."""
        engine = get_engine()
        dialect = get_dialect()

        if dialect == "mysql":
            query = text(
                "INSERT INTO sync_logs (entity_type, sync_type, status, started_at) "
                "VALUES (:entity_type, 'full', 'running', NOW())"
            )
            async with engine.begin() as conn:
                result = await conn.execute(
                    query, {"entity_type": self.ENTITY_TYPE}
                )
                return result.lastrowid
        else:
            query = text(
                "INSERT INTO sync_logs (entity_type, sync_type, status, started_at) "
                "VALUES (:entity_type, 'full', 'running', NOW()) "
                "RETURNING id"
            )
            async with engine.begin() as conn:
                result = await conn.execute(
                    query, {"entity_type": self.ENTITY_TYPE}
                )
                return result.scalar()

    async def _complete_sync_log(
        self,
        log_id: int,
        status: str,
        records_processed: int,
        error_message: str | None = None,
        records_fetched: int | None = None,
    ) -> None:
        """Mark a sync_log row as completed/failed with counters."""
        engine = get_engine()
        query = text(
            "UPDATE sync_logs "
            "SET status = :status, "
            "    records_fetched = :records_fetched, "
            "    records_processed = :records_processed, "
            "    error_message = :error_message, "
            "    completed_at = NOW() "
            "WHERE id = :log_id"
        )
        async with engine.begin() as conn:
            await conn.execute(
                query,
                {
                    "log_id": log_id,
                    "status": status,
                    "records_fetched": records_fetched,
                    "records_processed": records_processed,
                    "error_message": error_message,
                },
            )
