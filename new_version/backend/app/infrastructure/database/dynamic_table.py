"""Dynamic table builder for Bitrix24 entity tables."""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    MetaData,
    String,
    Table,
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

        for field in fields:
            col_name = field.column_name
            if col_name in cls.RESERVED_COLUMNS or col_name == "id":
                continue

            description = field.description
            if description in seen_descriptions:
                description = f"{description}_{col_name}"
            seen_descriptions.add(description)

            col = Column(
                col_name,
                field.sqlalchemy_type,
                comment=description,
            )
            columns.append(col)

        table = Table(table_name, metadata, *columns)

        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)

        logger.info(
            "Created dynamic table",
            table_name=table_name,
            column_count=len(columns),
        )

        return table

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
