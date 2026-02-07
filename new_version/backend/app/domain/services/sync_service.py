"""Synchronization service for Bitrix24 data."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SyncError
from app.core.logging import get_logger
from app.domain.entities.base import EntityType
from app.domain.services.field_mapper import FieldMapper
from app.infrastructure.bitrix.client import BitrixClient
from app.infrastructure.database.connection import get_dialect, get_session
from app.infrastructure.database.dynamic_table import DynamicTableBuilder
from app.infrastructure.database.models import SyncConfig, SyncLog, SyncState

logger = get_logger(__name__)


def _now_func() -> str:
    """Return NOW() function — works for both PostgreSQL and MySQL."""
    return "NOW()"


class SyncService:
    """Service for synchronizing Bitrix24 data to the database."""

    def __init__(
        self,
        bitrix_client: BitrixClient | None = None,
        session: AsyncSession | None = None,
    ):
        self._bitrix = bitrix_client or BitrixClient()
        self._session = session

    async def full_sync(self, entity_type: str) -> dict[str, Any]:
        """Perform full synchronization for an entity type."""
        logger.info("Starting full sync", entity_type=entity_type)
        table_name = EntityType.get_table_name(entity_type)

        sync_log = await self._create_sync_log(entity_type, "full")

        try:
            # Step 1: Get field definitions
            logger.info("Fetching field definitions", entity_type=entity_type)
            standard_fields = await self._bitrix.get_entity_fields(entity_type)
            user_fields = await self._bitrix.get_userfields(entity_type)

            mapped_std_fields = FieldMapper.prepare_fields_to_postgres(
                standard_fields, entity_type
            )
            mapped_user_fields = FieldMapper.prepare_userfields_to_postgres(
                user_fields, entity_type
            )

            all_fields = FieldMapper.merge_fields(mapped_std_fields, mapped_user_fields)
            logger.info(
                "Field definitions fetched",
                entity_type=entity_type,
                standard_count=len(mapped_std_fields),
                user_count=len(mapped_user_fields),
                total=len(all_fields),
            )

            # Step 2: Create/update table
            if await DynamicTableBuilder.table_exists(table_name):
                added = await DynamicTableBuilder.ensure_columns_exist(
                    table_name, all_fields
                )
                logger.info("Updated table columns", table_name=table_name, added=added)
            else:
                await DynamicTableBuilder.create_table_from_fields(
                    table_name, all_fields
                )
                logger.info("Created new table", table_name=table_name)

            # Step 3: Fetch all records from Bitrix
            logger.info("Fetching all records", entity_type=entity_type)
            records = await self._bitrix.get_entities(entity_type)
            logger.info(
                "Records fetched",
                entity_type=entity_type,
                count=len(records),
            )

            # Step 4: UPSERT to database
            records_processed = await self._upsert_records(table_name, records)
            logger.info(
                "Records upserted",
                table_name=table_name,
                processed=records_processed,
            )

            # Step 5: Update sync state
            await self._update_sync_state(entity_type, len(records))

            await self._complete_sync_log(sync_log.id, "completed", records_processed)

            # Step 6: Best-effort sync of related reference tables
            await self._sync_related_references(entity_type)

            # Step 7: Best-effort sync of enumeration field values
            await self._sync_enum_userfields(entity_type, user_fields)

            return {
                "status": "completed",
                "entity_type": entity_type,
                "records_processed": records_processed,
                "fields_count": len(all_fields),
            }

        except Exception as e:
            logger.error("Full sync failed", entity_type=entity_type, error=str(e))
            await self._complete_sync_log(sync_log.id, "failed", 0, str(e))
            raise SyncError(f"Full sync failed for {entity_type}: {str(e)}") from e

    async def _upsert_records(
        self,
        table_name: str,
        records: list[dict[str, Any]],
    ) -> int:
        """UPSERT records to the database table.

        Uses ON CONFLICT DO UPDATE (PostgreSQL) or
        INSERT ... ON DUPLICATE KEY UPDATE (MySQL).
        """
        if not records:
            return 0

        from app.infrastructure.database.connection import get_engine

        engine = get_engine()
        dialect = get_dialect()
        processed = 0

        columns = await DynamicTableBuilder.get_table_columns(table_name)
        column_set = set(columns)
        column_types = await self._get_column_types(table_name)

        async with engine.begin() as conn:
            for record in records:
                data = self._prepare_record_data(record, column_set, column_types)

                if not data.get("bitrix_id"):
                    continue

                cols = list(data.keys())
                placeholders = [f":{c}" for c in cols]

                if dialect == "mysql":
                    update_cols = [
                        f"{c} = VALUES({c})" for c in cols if c != "bitrix_id"
                    ]
                    query = text(
                        f"INSERT INTO {table_name} ({', '.join(cols)}) "
                        f"VALUES ({', '.join(placeholders)}) "
                        f"ON DUPLICATE KEY UPDATE "
                        f"{', '.join(update_cols)}, "
                        f"updated_at = NOW()"
                    )
                else:
                    update_cols = [
                        f"{c} = EXCLUDED.{c}" for c in cols if c != "bitrix_id"
                    ]
                    query = text(
                        f"INSERT INTO {table_name} ({', '.join(cols)}) "
                        f"VALUES ({', '.join(placeholders)}) "
                        f"ON CONFLICT (bitrix_id) DO UPDATE SET "
                        f"{', '.join(update_cols)}, "
                        f"updated_at = NOW()"
                    )

                await conn.execute(query, data)
                processed += 1

        return processed

    async def _get_column_types(self, table_name: str) -> dict[str, str]:
        """Get column types from database."""
        from app.infrastructure.database.connection import get_engine

        engine = get_engine()
        query = text(
            "SELECT column_name, data_type "
            "FROM information_schema.columns "
            "WHERE table_name = :table_name"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"table_name": table_name})
            rows = result.fetchall()

        column_types = {row[0]: row[1] for row in rows}
        logger.debug("Column types fetched", table_name=table_name, types=column_types)
        return column_types

    def _prepare_record_data(
        self,
        record: dict[str, Any],
        valid_columns: set[str],
        column_types: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Prepare record data for database insertion."""
        from decimal import Decimal, InvalidOperation
        from dateutil import parser

        data: dict[str, Any] = {}
        column_types = column_types or {}

        for key, value in record.items():
            col_name = key.lower()

            if col_name == "id":
                data["bitrix_id"] = str(value) if value else None
                continue

            if col_name not in valid_columns:
                continue

            if isinstance(value, (list, dict)):
                import json
                data[col_name] = json.dumps(value, ensure_ascii=False)
            elif value == "" or value is None:
                data[col_name] = None
            else:
                col_type = column_types.get(col_name, '').lower()

                if col_type in ('numeric', 'decimal', 'double precision', 'real', 'double', 'float'):
                    if isinstance(value, str):
                        try:
                            if col_type in ('double precision', 'real', 'double', 'float'):
                                data[col_name] = float(value)
                            else:
                                data[col_name] = Decimal(value)
                        except (InvalidOperation, ValueError):
                            data[col_name] = None
                    else:
                        data[col_name] = value
                elif col_type in ('integer', 'bigint', 'smallint', 'int', 'tinyint', 'mediumint'):
                    if isinstance(value, str):
                        try:
                            data[col_name] = int(value)
                        except (ValueError, TypeError):
                            data[col_name] = None
                    else:
                        data[col_name] = value
                elif col_type in ('timestamp', 'timestamp without time zone', 'date', 'datetime'):
                    if isinstance(value, str):
                        try:
                            dt = parser.parse(value)
                            if dt.tzinfo is not None:
                                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                            data[col_name] = dt
                        except (ValueError, TypeError, parser.ParserError):
                            data[col_name] = None
                    else:
                        data[col_name] = value
                else:
                    data[col_name] = value

        return data

    async def _create_sync_log(
        self,
        entity_type: str,
        sync_type: str,
    ) -> SyncLog:
        """Create a new sync log entry."""
        from app.infrastructure.database.connection import get_engine

        engine = get_engine()
        dialect = get_dialect()

        if dialect == "mysql":
            query = text(
                "INSERT INTO sync_logs (entity_type, sync_type, status, started_at) "
                "VALUES (:entity_type, :sync_type, 'running', NOW())"
            )
            async with engine.begin() as conn:
                result = await conn.execute(
                    query,
                    {"entity_type": entity_type, "sync_type": sync_type},
                )
                log_id = result.lastrowid
        else:
            query = text(
                "INSERT INTO sync_logs (entity_type, sync_type, status, started_at) "
                "VALUES (:entity_type, :sync_type, 'running', NOW()) "
                "RETURNING id"
            )
            async with engine.begin() as conn:
                result = await conn.execute(
                    query,
                    {"entity_type": entity_type, "sync_type": sync_type},
                )
                log_id = result.scalar()

        log = SyncLog()
        log.id = log_id
        return log

    async def _complete_sync_log(
        self,
        log_id: int,
        status: str,
        records_processed: int,
        error_message: str | None = None,
    ) -> None:
        """Complete a sync log entry."""
        from app.infrastructure.database.connection import get_engine

        engine = get_engine()

        query = text(
            "UPDATE sync_logs "
            "SET status = :status, "
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
                    "records_processed": records_processed,
                    "error_message": error_message,
                },
            )

    async def _update_sync_state(
        self,
        entity_type: str,
        records_count: int,
        incremental: bool = False,
    ) -> None:
        """Update sync state after successful sync."""
        from app.infrastructure.database.connection import get_engine

        engine = get_engine()
        dialect = get_dialect()

        if incremental:
            query = text(
                "UPDATE sync_state "
                "SET last_modified_date = NOW(), "
                "    updated_at = NOW() "
                "WHERE entity_type = :entity_type"
            )
            async with engine.begin() as conn:
                await conn.execute(query, {"entity_type": entity_type})
        else:
            if dialect == "mysql":
                query = text(
                    "INSERT INTO sync_state (entity_type, last_modified_date, total_records, updated_at) "
                    "VALUES (:entity_type, NOW(), :total_records, NOW()) "
                    "ON DUPLICATE KEY UPDATE "
                    "    last_modified_date = NOW(), "
                    "    total_records = VALUES(total_records), "
                    "    updated_at = NOW()"
                )
            else:
                query = text(
                    "INSERT INTO sync_state (entity_type, last_modified_date, total_records, updated_at) "
                    "VALUES (:entity_type, NOW(), :total_records, NOW()) "
                    "ON CONFLICT (entity_type) DO UPDATE SET "
                    "    last_modified_date = NOW(), "
                    "    total_records = :total_records, "
                    "    updated_at = NOW()"
                )
            async with engine.begin() as conn:
                await conn.execute(
                    query,
                    {"entity_type": entity_type, "total_records": records_count},
                )

        config_query = text(
            "UPDATE sync_config "
            "SET last_sync_at = NOW(), updated_at = NOW() "
            "WHERE entity_type = :entity_type"
        )

        async with engine.begin() as conn:
            await conn.execute(config_query, {"entity_type": entity_type})

    async def incremental_sync(self, entity_type: str) -> dict[str, Any]:
        """Perform incremental synchronization for an entity type."""
        logger.info("Starting incremental sync", entity_type=entity_type)
        table_name = EntityType.get_table_name(entity_type)

        if not await DynamicTableBuilder.table_exists(table_name):
            logger.warning(
                "Table does not exist, running full sync instead",
                entity_type=entity_type,
            )
            return await self.full_sync(entity_type)

        last_modified = await self._get_last_modified_date(entity_type)
        if last_modified is None:
            logger.info(
                "No previous sync state found, running full sync",
                entity_type=entity_type,
            )
            return await self.full_sync(entity_type)

        sync_log = await self._create_sync_log(entity_type, "incremental")

        try:
            date_filter = last_modified.strftime("%Y-%m-%dT%H:%M:%S")
            date_field = self._DATE_MODIFY_FIELD.get(entity_type, "DATE_MODIFY")
            filter_params = {f">{date_field}": date_filter}

            logger.info(
                "Fetching modified records",
                entity_type=entity_type,
                since=date_filter,
            )

            records = await self._bitrix.get_entities(
                entity_type, filter_params=filter_params
            )
            logger.info(
                "Modified records fetched",
                entity_type=entity_type,
                count=len(records),
            )

            if not records:
                logger.info("No modified records found", entity_type=entity_type)
                await self._complete_sync_log(sync_log.id, "completed", 0)
                return {
                    "status": "completed",
                    "entity_type": entity_type,
                    "records_processed": 0,
                    "sync_type": "incremental",
                }

            await self._ensure_schema_updated(entity_type, table_name)

            records_processed = await self._upsert_records(table_name, records)
            logger.info(
                "Records upserted",
                table_name=table_name,
                processed=records_processed,
            )

            await self._update_sync_state(entity_type, records_processed, incremental=True)
            await self._complete_sync_log(sync_log.id, "completed", records_processed)

            return {
                "status": "completed",
                "entity_type": entity_type,
                "records_processed": records_processed,
                "sync_type": "incremental",
            }

        except Exception as e:
            logger.error("Incremental sync failed", entity_type=entity_type, error=str(e))
            await self._complete_sync_log(sync_log.id, "failed", 0, str(e))
            raise SyncError(f"Incremental sync failed for {entity_type}: {str(e)}") from e

    async def sync_entity_by_id(
        self, entity_type: str, entity_id: str
    ) -> dict[str, Any]:
        """Sync a single entity by ID (used for webhook events)."""
        logger.info(
            "Syncing single entity",
            entity_type=entity_type,
            entity_id=entity_id,
        )
        table_name = EntityType.get_table_name(entity_type)

        if not await DynamicTableBuilder.table_exists(table_name):
            logger.warning(
                "Table does not exist, skipping webhook sync",
                entity_type=entity_type,
            )
            return {"status": "skipped", "reason": "table_not_exists"}

        sync_log = await self._create_sync_log(entity_type, "webhook")

        try:
            entity_data = await self._bitrix.get_entity(entity_type, entity_id)

            if not entity_data:
                logger.warning(
                    "Entity not found in Bitrix",
                    entity_type=entity_type,
                    entity_id=entity_id,
                )
                await self._complete_sync_log(sync_log.id, "completed", 0)
                return {"status": "not_found", "entity_id": entity_id}

            records_processed = await self._upsert_records(table_name, [entity_data])
            await self._complete_sync_log(sync_log.id, "completed", records_processed)

            return {
                "status": "completed",
                "entity_type": entity_type,
                "entity_id": entity_id,
                "records_processed": records_processed,
            }

        except Exception as e:
            logger.error(
                "Webhook sync failed",
                entity_type=entity_type,
                entity_id=entity_id,
                error=str(e),
            )
            await self._complete_sync_log(sync_log.id, "failed", 0, str(e))
            raise SyncError(f"Webhook sync failed for {entity_type}/{entity_id}") from e

    async def delete_entity_by_id(
        self, entity_type: str, entity_id: str
    ) -> dict[str, Any]:
        """Delete a single entity by ID (used for webhook delete events)."""
        logger.info(
            "Deleting entity",
            entity_type=entity_type,
            entity_id=entity_id,
        )
        table_name = EntityType.get_table_name(entity_type)

        if not await DynamicTableBuilder.table_exists(table_name):
            return {"status": "skipped", "reason": "table_not_exists"}

        from app.infrastructure.database.connection import get_engine

        engine = get_engine()

        query = text(
            f"DELETE FROM {table_name} WHERE bitrix_id = :bitrix_id"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"bitrix_id": str(entity_id)})
            deleted = result.rowcount

        logger.info(
            "Entity deleted",
            entity_type=entity_type,
            entity_id=entity_id,
            deleted=deleted,
        )

        return {
            "status": "completed",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "records_deleted": deleted,
        }

    async def _get_last_modified_date(self, entity_type: str) -> datetime | None:
        """Get last modified date from sync state."""
        from app.infrastructure.database.connection import get_engine

        engine = get_engine()

        query = text(
            "SELECT last_modified_date "
            "FROM sync_state "
            "WHERE entity_type = :entity_type"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"entity_type": entity_type})
            row = result.fetchone()

        if row and row[0]:
            return row[0]
        return None

    # Mapping of entity types to related reference types
    _ENTITY_REFERENCE_MAP: dict[str, list[str]] = {
        "deal": ["crm_status", "crm_deal_category", "crm_currency"],
        "lead": ["crm_status", "crm_currency"],
        "contact": ["crm_currency"],
        "company": ["crm_currency"],
        "user": [],
        "task": [],
        "call": [],
    }

    # Date field used for incremental sync filtering per entity type
    _DATE_MODIFY_FIELD: dict[str, str] = {
        "user": "TIMESTAMP_X",
        "task": "CHANGED_DATE",
        "call": "CALL_START_DATE",
    }

    async def _sync_related_references(self, entity_type: str) -> None:
        """Best-effort sync of reference tables related to this entity type."""
        ref_names = self._ENTITY_REFERENCE_MAP.get(entity_type, [])
        if not ref_names:
            return

        try:
            from app.domain.services.reference_sync_service import ReferenceSyncService

            ref_service = ReferenceSyncService(bitrix_client=self._bitrix)
            for ref_name in ref_names:
                try:
                    await ref_service.sync_reference(ref_name)
                    logger.info(
                        "Related reference synced",
                        entity_type=entity_type,
                        ref_name=ref_name,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to sync related reference, skipping",
                        entity_type=entity_type,
                        ref_name=ref_name,
                        error=str(e),
                    )
        except Exception as e:
            logger.warning(
                "Failed to sync related references",
                entity_type=entity_type,
                error=str(e),
            )

    async def _sync_enum_userfields(
        self, entity_type: str, user_fields: list[dict[str, Any]]
    ) -> None:
        """Best-effort sync of enumeration userfield values to ref_enum_values."""
        try:
            from app.domain.services.reference_sync_service import ReferenceSyncService

            ref_service = ReferenceSyncService(bitrix_client=self._bitrix)
            result = await ref_service.sync_enum_userfields(entity_type, user_fields)
            logger.info(
                "Enum userfields synced",
                entity_type=entity_type,
                records_processed=result.get("records_processed", 0),
            )
        except Exception as e:
            logger.warning(
                "Failed to sync enum userfields, skipping",
                entity_type=entity_type,
                error=str(e),
            )

    async def _ensure_schema_updated(self, entity_type: str, table_name: str) -> None:
        """Ensure table schema is up to date with Bitrix fields."""
        standard_fields = await self._bitrix.get_entity_fields(entity_type)
        user_fields = await self._bitrix.get_userfields(entity_type)

        mapped_std_fields = FieldMapper.prepare_fields_to_postgres(
            standard_fields, entity_type
        )
        mapped_user_fields = FieldMapper.prepare_userfields_to_postgres(
            user_fields, entity_type
        )

        all_fields = FieldMapper.merge_fields(mapped_std_fields, mapped_user_fields)

        added = await DynamicTableBuilder.ensure_columns_exist(table_name, all_fields)
        if added:
            logger.info(
                "Added new columns during incremental sync",
                table_name=table_name,
                added=added,
            )
