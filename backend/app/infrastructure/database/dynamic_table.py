"""Dynamic table builder for Bitrix24 entity tables."""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    Text,
    func,
    text,
)
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.logging import get_logger
from app.domain.services.field_mapper import FieldInfo
from app.infrastructure.database.connection import get_dialect, get_engine

logger = get_logger(__name__)


class DynamicTableBuilder:
    """Builder for creating dynamic database tables from Bitrix field definitions."""

    RESERVED_COLUMNS = {
        "record_id",
        "bitrix_id",
        "bitrix_id_int",
        "created_at",
        "updated_at",
    }

    @classmethod
    async def create_table_from_fields(
        cls,
        table_name: str,
        fields: list[FieldInfo],
    ) -> Table:
        """Create a database table from Bitrix field definitions."""
        engine = get_engine()
        metadata = MetaData()

        columns = [
            Column("record_id", BigInteger, primary_key=True, autoincrement=True),
            Column("bitrix_id", String(50), unique=True, nullable=False, index=True),
            Column("bitrix_id_int", BigInteger, nullable=True, index=True),
            Column("created_at", DateTime, server_default=func.now(), nullable=False),
            Column(
                "updated_at",
                DateTime,
                server_default=func.now(),
                onupdate=func.now(),
                nullable=False,
            ),
        ]

        seen_descriptions: set[str] = set()
        dialect = get_dialect()

        for field in fields:
            col_name = field.column_name
            if col_name in cls.RESERVED_COLUMNS or col_name == "id":
                continue

            description = field.description
            if description in seen_descriptions:
                description = f"{description}_{col_name}"
            seen_descriptions.add(description)

            col_type = field.sqlalchemy_type
            # In MySQL, VARCHAR(255) columns count toward the 65535-byte DDL row size limit
            # (255 chars × 4 bytes utf8mb4 = 1020 bytes each). TEXT columns are stored
            # off-page and are excluded from this check, so we use TEXT for string fields.
            if dialect == "mysql" and isinstance(col_type, String) and not isinstance(col_type, Text):
                col_type = Text()

            col = Column(col_name, col_type, comment=description)
            columns.append(col)

        if dialect == "mysql":
            table = Table(table_name, metadata, *columns, mysql_row_format="DYNAMIC")
        else:
            table = Table(table_name, metadata, *columns)

        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)

        # If the table already existed, create_all is a no-op and won't add
        # newly-declared system columns such as bitrix_id_int. Ensure the
        # column and its backfill run for legacy tables as well.
        await cls._ensure_bitrix_id_int_column(table_name)

        logger.info(
            "Created dynamic table",
            table_name=table_name,
            column_count=len(columns),
        )

        return table

    @classmethod
    async def _ensure_bitrix_id_int_column(cls, table_name: str) -> None:
        """Guarantee that <table>.bitrix_id_int exists, is indexed, and is
        backfilled from bitrix_id for rows where it is still NULL.

        Idempotent: safe to call on every sync. Acts as a runtime safety net
        for tables that were created before migration 021 or that skipped
        alembic entirely.
        """
        engine = get_engine()
        dialect = get_dialect()

        async with engine.begin() as conn:
            existing = await cls._get_existing_columns(conn)
            table_cols = existing.get(table_name, set())

            if "bitrix_id" not in table_cols:
                # Nothing to do — this isn't a Bitrix entity table.
                return

            # 1) Add the column if missing.
            if "bitrix_id_int" not in table_cols:
                try:
                    if dialect == "mysql":
                        await conn.execute(
                            text(
                                f"ALTER TABLE `{table_name}` "
                                f"ADD COLUMN bitrix_id_int BIGINT NULL"
                            )
                        )
                    else:
                        await conn.execute(
                            text(
                                f'ALTER TABLE "{table_name}" '
                                f"ADD COLUMN IF NOT EXISTS bitrix_id_int BIGINT"
                            )
                        )
                    logger.info(
                        "Added bitrix_id_int column", table_name=table_name
                    )
                except Exception as e:
                    logger.error(
                        "Failed to add bitrix_id_int column",
                        table_name=table_name,
                        error=str(e),
                    )
                    return

            # 2) Backfill rows where bitrix_id_int IS NULL but bitrix_id is numeric.
            try:
                if dialect == "mysql":
                    backfill_sql = (
                        f"UPDATE `{table_name}` "
                        f"SET bitrix_id_int = CAST(bitrix_id AS SIGNED) "
                        f"WHERE bitrix_id_int IS NULL "
                        f"  AND bitrix_id IS NOT NULL "
                        f"  AND bitrix_id REGEXP '^[0-9]+$'"
                    )
                else:
                    backfill_sql = (
                        f'UPDATE "{table_name}" '
                        f"SET bitrix_id_int = CAST(bitrix_id AS BIGINT) "
                        f"WHERE bitrix_id_int IS NULL "
                        f"  AND bitrix_id IS NOT NULL "
                        f"  AND bitrix_id ~ '^[0-9]+$'"
                    )
                result = await conn.execute(text(backfill_sql))
                affected = result.rowcount if result.rowcount is not None else 0
                if affected > 0:
                    logger.info(
                        "Backfilled bitrix_id_int",
                        table_name=table_name,
                        rows=affected,
                    )
            except Exception as e:
                logger.warning(
                    "bitrix_id_int backfill failed",
                    table_name=table_name,
                    error=str(e),
                )

            # 3) Ensure an index exists on bitrix_id_int.
            idx_name = f"ix_{table_name}_bitrix_id_int"[:63]
            try:
                if dialect == "mysql":
                    # MySQL has no CREATE INDEX IF NOT EXISTS before 8.0 —
                    # check via information_schema.statistics first.
                    check = await conn.execute(
                        text(
                            "SELECT 1 FROM information_schema.statistics "
                            "WHERE table_schema = DATABASE() "
                            "  AND table_name = :tbl AND index_name = :idx "
                            "LIMIT 1"
                        ),
                        {"tbl": table_name, "idx": idx_name},
                    )
                    if check.first() is None:
                        await conn.execute(
                            text(
                                f"CREATE INDEX `{idx_name}` "
                                f"ON `{table_name}` (bitrix_id_int)"
                            )
                        )
                else:
                    await conn.execute(
                        text(
                            f'CREATE INDEX IF NOT EXISTS "{idx_name}" '
                            f'ON "{table_name}" (bitrix_id_int)'
                        )
                    )
            except Exception as e:
                logger.warning(
                    "Failed to create bitrix_id_int index",
                    table_name=table_name,
                    error=str(e),
                )

    @classmethod
    async def add_column_to_table(
        cls,
        table_name: str,
        field: FieldInfo,
    ) -> bool:
        """Add a new column to an existing table."""
        engine = get_engine()
        col_name = field.column_name
        sql_type = field.sql_type_name
        # Mirror the same VARCHAR→TEXT conversion used in create_table_from_fields
        if get_dialect() == "mysql" and sql_type == "VARCHAR(255)":
            sql_type = "TEXT"

        try:
            async with engine.begin() as conn:
                # Check if column exists using SQLAlchemy inspect
                existing = await cls._get_existing_columns(conn)
                table_cols = existing.get(table_name, set())
                if col_name not in table_cols:
                    await conn.execute(
                        text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {sql_type}")
                    )
            logger.info(
                "Added column to table",
                table_name=table_name,
                column_name=col_name,
                sql_type=sql_type,
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to add column",
                table_name=table_name,
                column_name=col_name,
                error=str(e),
            )
            return False

    @classmethod
    async def _get_existing_columns(cls, conn: AsyncConnection) -> dict[str, set[str]]:
        """Get existing columns grouped by table name using information_schema."""
        query = text(
            "SELECT table_name, column_name FROM information_schema.columns"
        )
        result = await conn.execute(query)
        columns: dict[str, set[str]] = {}
        for row in result.fetchall():
            columns.setdefault(row[0], set()).add(row[1])
        return columns

    @classmethod
    async def ensure_columns_exist(
        cls,
        table_name: str,
        fields: list[FieldInfo],
    ) -> int:
        """Ensure all specified columns exist in the table."""
        engine = get_engine()
        added = 0

        query = text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :table_name"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"table_name": table_name})
            existing_columns = {row[0] for row in result.fetchall()}

        for field in fields:
            col_name = field.column_name

            if col_name in cls.RESERVED_COLUMNS or col_name == "id":
                continue

            if col_name not in existing_columns:
                if await cls.add_column_to_table(table_name, field):
                    added += 1

        logger.info(
            "Ensured columns exist",
            table_name=table_name,
            added_count=added,
            total_fields=len(fields),
        )

        return added

    @classmethod
    async def table_exists(cls, table_name: str) -> bool:
        """Check if a table exists in the database."""
        engine = get_engine()
        query = text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = :table_name"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"table_name": table_name})
            count = result.scalar()
            return count is not None and count > 0

    @classmethod
    async def get_table_columns(cls, table_name: str) -> list[str]:
        """Get list of column names for a table."""
        engine = get_engine()
        query = text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :table_name "
            "ORDER BY ordinal_position"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"table_name": table_name})
            return [row[0] for row in result.fetchall()]

    @classmethod
    async def drop_table(cls, table_name: str) -> bool:
        """Drop a table from the database."""
        engine = get_engine()
        dialect = get_dialect()

        if dialect == "mysql":
            query = text(f"DROP TABLE IF EXISTS {table_name}")
        else:
            query = text(f"DROP TABLE IF EXISTS {table_name} CASCADE")

        try:
            async with engine.begin() as conn:
                await conn.execute(query)
            logger.info("Dropped table", table_name=table_name)
            return True
        except Exception as e:
            logger.error("Failed to drop table", table_name=table_name, error=str(e))
            return False
