"""Dynamic table builder for Bitrix24 entity tables."""

from datetime import datetime
from typing import Any, Type

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
from sqlalchemy.orm import DeclarativeBase

from app.core.logging import get_logger
from app.domain.services.field_mapper import FieldInfo, FieldMapper
from app.infrastructure.database.connection import Base, get_engine

logger = get_logger(__name__)


class DynamicTableBuilder:
    """Builder for creating dynamic database tables from Bitrix field definitions."""

    # Reserved column names that are always present
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
        """Create a database table from Bitrix field definitions.

        The table includes:
        - record_id: BigInteger primary key (auto-increment)
        - bitrix_id: String unique (maps from Bitrix ID field)
        - created_at: DateTime (record creation time)
        - updated_at: DateTime (last update time)
        - All fields from the fields list

        Args:
            table_name: Name of the table to create (e.g., 'crm_deals')
            fields: List of FieldInfo objects from FieldMapper

        Returns:
            SQLAlchemy Table object
        """
        engine = get_engine()
        metadata = MetaData()

        # Build column list
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

        # Track unique descriptions for comments
        seen_descriptions: set[str] = set()

        for field in fields:
            col_name = field.column_name

            # Skip reserved columns and ID (maps to bitrix_id)
            if col_name in cls.RESERVED_COLUMNS:
                continue
            if col_name == "id":
                continue

            # Handle duplicate descriptions
            description = field.description
            if description in seen_descriptions:
                description = f"{description}_{col_name}"
            seen_descriptions.add(description)

            # Create column with appropriate type
            col = Column(
                col_name,
                field.sqlalchemy_type,
                comment=description,
            )
            columns.append(col)

        # Create table object
        table = Table(table_name, metadata, *columns)

        # Create in database
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
        """Add a new column to an existing table.

        Uses ALTER TABLE to add the column if it doesn't exist.

        Args:
            table_name: Name of the table
            field: FieldInfo object for the new column

        Returns:
            True if column was added or already exists
        """
        engine = get_engine()
        col_name = field.column_name
        sql_type = field.sql_type_name

        # Check if column already exists and add if not
        alter_query = text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = :table_name AND column_name = :col_name
                ) THEN
                    ALTER TABLE {table_name} ADD COLUMN {col_name} {sql_type};
                END IF;
            END $$;
            """
        )

        try:
            async with engine.begin() as conn:
                await conn.execute(
                    alter_query,
                    {"table_name": table_name, "col_name": col_name},
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
    async def ensure_columns_exist(
        cls,
        table_name: str,
        fields: list[FieldInfo],
    ) -> int:
        """Ensure all specified columns exist in the table.

        Adds any missing columns without affecting existing ones.

        Args:
            table_name: Name of the table
            fields: List of FieldInfo objects

        Returns:
            Number of columns added
        """
        engine = get_engine()
        added = 0

        # Get existing columns
        existing_query = text(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = :table_name
            """
        )

        async with engine.begin() as conn:
            result = await conn.execute(existing_query, {"table_name": table_name})
            existing_columns = {row[0] for row in result.fetchall()}

        # Add missing columns
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
        """Check if a table exists in the database.

        Args:
            table_name: Name of the table

        Returns:
            True if table exists
        """
        engine = get_engine()
        query = text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = :table_name
            )
            """
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"table_name": table_name})
            return result.scalar()

    @classmethod
    async def get_table_columns(cls, table_name: str) -> list[str]:
        """Get list of column names for a table.

        Args:
            table_name: Name of the table

        Returns:
            List of column names
        """
        engine = get_engine()
        query = text(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = :table_name
            ORDER BY ordinal_position
            """
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"table_name": table_name})
            return [row[0] for row in result.fetchall()]

    @classmethod
    async def drop_table(cls, table_name: str) -> bool:
        """Drop a table from the database.

        Args:
            table_name: Name of the table to drop

        Returns:
            True if table was dropped
        """
        engine = get_engine()
        query = text(f"DROP TABLE IF EXISTS {table_name} CASCADE")

        try:
            async with engine.begin() as conn:
                await conn.execute(query)
            logger.info("Dropped table", table_name=table_name)
            return True
        except Exception as e:
            logger.error("Failed to drop table", table_name=table_name, error=str(e))
            return False
