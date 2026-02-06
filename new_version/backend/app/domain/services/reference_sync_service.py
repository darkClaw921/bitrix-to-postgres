"""Service for synchronizing Bitrix24 reference/dictionary data."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from app.core.exceptions import SyncError
from app.core.logging import get_logger
from app.domain.entities.reference import (
    ReferenceType,
    get_all_reference_types,
    get_reference_type,
)
from app.infrastructure.bitrix.client import BitrixClient
from app.infrastructure.database.connection import get_dialect, get_engine

logger = get_logger(__name__)


class ReferenceSyncService:
    """Service for synchronizing Bitrix24 reference/dictionary tables."""

    def __init__(self, bitrix_client: BitrixClient | None = None):
        self._bitrix = bitrix_client or BitrixClient()

    async def sync_reference(self, ref_name: str) -> dict[str, Any]:
        """Synchronize a single reference type."""
        ref_type = get_reference_type(ref_name)
        if ref_type is None:
            raise SyncError(f"Unknown reference type: {ref_name}")

        logger.info("Starting reference sync", ref_name=ref_name)
        sync_log_id = await self._create_sync_log(ref_type)

        try:
            await self._ensure_table(ref_type)

            records = await self._fetch_records(ref_type)
            logger.info(
                "Reference records fetched",
                ref_name=ref_name,
                count=len(records),
            )

            upserted = await self._upsert_reference_records(ref_type, records)
            logger.info(
                "Reference records upserted",
                ref_name=ref_name,
                upserted=upserted,
            )

            await self._complete_sync_log(sync_log_id, "completed", upserted)

            return {
                "status": "completed",
                "ref_name": ref_name,
                "records_processed": upserted,
            }

        except Exception as e:
            logger.error(
                "Reference sync failed", ref_name=ref_name, error=str(e)
            )
            await self._complete_sync_log(sync_log_id, "failed", 0, str(e))
            raise SyncError(
                f"Reference sync failed for {ref_name}: {str(e)}"
            ) from e

    async def sync_all_references(self) -> dict[str, Any]:
        """Synchronize all reference types."""
        logger.info("Starting sync of all references")
        results: dict[str, Any] = {}

        for name, ref_type in get_all_reference_types().items():
            try:
                result = await self.sync_reference(name)
                results[name] = result
            except Exception as e:
                logger.error(
                    "Reference sync failed, continuing with others",
                    ref_name=name,
                    error=str(e),
                )
                results[name] = {"status": "failed", "error": str(e)}

        return {
            "status": "completed",
            "references": results,
        }

    async def _ensure_table(self, ref_type: ReferenceType) -> None:
        """Create reference table if it doesn't exist."""
        engine = get_engine()
        dialect = get_dialect()
        table_name = ref_type.table_name

        check_query = text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = :table_name"
        )

        async with engine.begin() as conn:
            result = await conn.execute(check_query, {"table_name": table_name})
            exists = result.scalar() > 0

        if exists:
            logger.debug("Reference table already exists", table_name=table_name)
            return

        columns_sql = []
        for f in ref_type.fields:
            null_clause = "" if f.nullable else " NOT NULL"
            col_type = self._map_sql_type(f.sql_type, dialect)
            columns_sql.append(f"    {f.column_name} {col_type}{null_clause}")

        columns_sql.append("    created_at TIMESTAMP DEFAULT NOW()")
        columns_sql.append("    updated_at TIMESTAMP DEFAULT NOW()")

        unique_cols = ", ".join(ref_type.unique_key)

        if dialect == "mysql":
            # MySQL: use UNIQUE KEY inline
            create_sql = (
                f"CREATE TABLE {table_name} (\n"
                f"    record_id BIGINT AUTO_INCREMENT PRIMARY KEY,\n"
                + ",\n".join(columns_sql)
                + f",\n    UNIQUE KEY uq_{table_name} ({unique_cols})"
                + "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            )
        else:
            # PostgreSQL
            create_sql = (
                f"CREATE TABLE {table_name} (\n"
                f"    record_id BIGSERIAL PRIMARY KEY,\n"
                + ",\n".join(columns_sql)
                + f",\n    UNIQUE ({unique_cols})"
                + "\n)"
            )

        async with engine.begin() as conn:
            await conn.execute(text(create_sql))

        logger.info("Created reference table", table_name=table_name)

    @staticmethod
    def _map_sql_type(sql_type: str, dialect: str) -> str:
        """Map generic SQL type to dialect-specific type."""
        upper = sql_type.upper()
        if dialect == "mysql":
            if upper == "TIMESTAMP":
                return "DATETIME"
            if upper.startswith("VARCHAR"):
                return sql_type
            if upper == "INTEGER":
                return "INT"
            if upper == "TEXT":
                return "TEXT"
        return sql_type

    async def _fetch_records(self, ref_type: ReferenceType) -> list[dict[str, Any]]:
        """Fetch reference records from Bitrix24 API."""
        if ref_type.requires_category_iteration:
            return await self._fetch_statuses_with_categories()

        result = await self._bitrix._call(ref_type.api_method)
        raw_records = self._normalize_result(result)

        # crm.dealcategory.list doesn't return the default pipeline (ID=0),
        # fetch it separately via crm.dealcategory.default.get
        if ref_type.name == "crm_deal_category":
            default_cat = await self._bitrix._call(
                "crm.dealcategory.default.get"
            )
            if isinstance(default_cat, dict):
                raw_records.insert(0, {
                    "ID": str(default_cat.get("ID", 0)),
                    "NAME": default_cat.get("NAME", ""),
                    "SORT": 0,
                    "IS_LOCKED": "N",
                    "CREATED_DATE": None,
                })

        # Bitrix API returns UPPERCASE keys; normalize to lowercase column names
        return [
            {k.lower(): v for k, v in record.items()}
            for record in raw_records
        ]

    async def _fetch_statuses_with_categories(self) -> list[dict[str, Any]]:
        """Fetch all statuses including deal stages from all pipelines.

        1. Get all statuses via crm.status.list (leads, sources, etc.)
        2. Get all deal categories (pipelines)
        3. For each category, get deal stages via crm.dealcategory.stage.list
        4. Deduplicate by (status_id, entity_id, category_id)
        """
        # Step 1: Get all general statuses
        all_statuses_raw = await self._bitrix._call("crm.status.list")
        all_statuses = self._normalize_result(all_statuses_raw)

        records: dict[str, dict[str, Any]] = {}

        for status in all_statuses:
            status_id = status.get("STATUS_ID", "")
            entity_id = status.get("ENTITY_ID", "")
            category_id = str(status.get("CATEGORY_ID") or "0")

            key = f"{status_id}|{entity_id}|{category_id}"
            if key not in records:
                records[key] = self._build_status_record(
                    status, category_id
                )

        # Step 2: Get all deal categories (pipelines)
        categories_raw = await self._bitrix._call("crm.dealcategory.list")
        categories = self._normalize_result(categories_raw)

        # Include default pipeline (id=0) plus all custom ones
        category_ids = ["0"] + [
            str(c.get("ID", "")) for c in categories if c.get("ID")
        ]

        # Step 3: Fetch stages for each category in parallel
        async def fetch_category_stages(cat_id: str) -> list[dict[str, Any]]:
            try:
                result = await self._bitrix._call(
                    "crm.dealcategory.stage.list",
                    items={"id": int(cat_id)},
                )
                return self._normalize_result(result)
            except Exception as e:
                logger.warning(
                    "Failed to fetch stages for category",
                    category_id=cat_id,
                    error=str(e),
                )
                return []

        stage_results = await asyncio.gather(
            *[fetch_category_stages(cid) for cid in category_ids]
        )

        for cat_id, stages in zip(category_ids, stage_results):
            for stage in stages:
                status_id = stage.get("STATUS_ID", "")
                entity_id = stage.get("ENTITY_ID", f"DEAL_STAGE_{cat_id}" if cat_id != "0" else "DEAL_STAGE")
                category_id = cat_id

                key = f"{status_id}|{entity_id}|{category_id}"
                if key not in records:
                    records[key] = self._build_status_record(
                        stage, category_id
                    )

        return list(records.values())

    @staticmethod
    def _build_status_record(
        raw: dict[str, Any], category_id: str
    ) -> dict[str, Any]:
        """Build a normalized status record from raw Bitrix data."""
        extra = raw.get("EXTRA", {}) or {}
        return {
            "status_id": raw.get("STATUS_ID", ""),
            "entity_id": raw.get("ENTITY_ID", ""),
            "category_id": category_id,
            "name": raw.get("NAME", ""),
            "name_init": raw.get("NAME_INIT", ""),
            "sort": _safe_int(raw.get("SORT")),
            "system": raw.get("SYSTEM", ""),
            "color": extra.get("COLOR", ""),
            "semantics": extra.get("SEMANTICS", ""),
            "extra_color": extra.get("COLOR", ""),
            "extra_semantics": extra.get("SEMANTICS", ""),
        }

    @staticmethod
    def _normalize_result(result: Any) -> list[dict[str, Any]]:
        """Normalize Bitrix API result to a list of dicts."""
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            # Some methods return {0: {...}, 1: {...}, ...}
            if all(k.isdigit() for k in result.keys()):
                return list(result.values())
            return [result]
        return []

    async def _upsert_reference_records(
        self, ref_type: ReferenceType, records: list[dict[str, Any]]
    ) -> int:
        """Upsert reference records using composite unique keys."""
        if not records:
            return 0

        engine = get_engine()
        dialect = get_dialect()
        table_name = ref_type.table_name

        field_names = [f.column_name for f in ref_type.fields]
        unique_key_cols = ref_type.unique_key
        update_cols = [c for c in field_names if c not in unique_key_cols]

        processed = 0

        async with engine.begin() as conn:
            for record in records:
                data = self._prepare_record(record, field_names)

                cols = list(data.keys())
                placeholders = [f":{c}" for c in cols]

                if dialect == "mysql":
                    update_parts = [
                        f"{c} = VALUES({c})" for c in cols
                        if c not in unique_key_cols
                    ]
                    update_parts.append("updated_at = NOW()")
                    query = text(
                        f"INSERT INTO {table_name} ({', '.join(cols)}) "
                        f"VALUES ({', '.join(placeholders)}) "
                        f"ON DUPLICATE KEY UPDATE "
                        f"{', '.join(update_parts)}"
                    )
                else:
                    update_parts = [
                        f"{c} = EXCLUDED.{c}" for c in cols
                        if c not in unique_key_cols
                    ]
                    update_parts.append("updated_at = NOW()")
                    conflict_cols = ", ".join(unique_key_cols)
                    query = text(
                        f"INSERT INTO {table_name} ({', '.join(cols)}) "
                        f"VALUES ({', '.join(placeholders)}) "
                        f"ON CONFLICT ({conflict_cols}) DO UPDATE SET "
                        f"{', '.join(update_parts)}"
                    )

                await conn.execute(query, data)
                processed += 1

        return processed

    @staticmethod
    def _prepare_record(
        record: dict[str, Any], field_names: list[str]
    ) -> dict[str, Any]:
        """Prepare a record for database insertion."""
        data: dict[str, Any] = {}
        for col in field_names:
            value = record.get(col)
            if isinstance(value, (list, dict)):
                data[col] = json.dumps(value, ensure_ascii=False)
            elif value == "" or value is None:
                data[col] = None
            else:
                data[col] = value
        return data

    async def _create_sync_log(self, ref_type: ReferenceType) -> int:
        """Create a sync log entry for reference sync."""
        engine = get_engine()
        dialect = get_dialect()
        entity_type = f"ref:{ref_type.name}"

        if dialect == "mysql":
            query = text(
                "INSERT INTO sync_logs (entity_type, sync_type, status, started_at) "
                "VALUES (:entity_type, 'full', 'running', NOW())"
            )
            async with engine.begin() as conn:
                result = await conn.execute(
                    query, {"entity_type": entity_type}
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
                    query, {"entity_type": entity_type}
                )
                return result.scalar()

    async def _complete_sync_log(
        self,
        log_id: int,
        status: str,
        records_processed: int,
        error_message: str | None = None,
    ) -> None:
        """Complete a sync log entry."""
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


def _safe_int(value: Any) -> int | None:
    """Safely convert a value to int, returning None on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
