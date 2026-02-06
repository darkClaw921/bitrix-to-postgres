"""Chart service: SQL validation, query execution, CRUD for saved charts."""

import asyncio
import re
import time
from typing import Any

from sqlalchemy import text

from app.config import get_settings
from app.core.exceptions import ChartServiceError
from app.core.logging import get_logger
from app.infrastructure.database.connection import get_dialect, get_engine

logger = get_logger(__name__)

# Forbidden SQL keywords (case-insensitive)
_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)

# Extract table names from FROM and JOIN clauses
_TABLE_PATTERN = re.compile(
    r"(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.IGNORECASE
)

# Detect existing LIMIT clause
_LIMIT_PATTERN = re.compile(r"\bLIMIT\s+(\d+)", re.IGNORECASE)

# Mapping of entity tables to their related reference tables
_ENTITY_RELATED_TABLES = {
    "crm_deals": [
        "ref_crm_statuses",       # Statuses & Stages
        "ref_crm_deal_categories", # Deal Pipelines
        "ref_crm_currencies",      # Currencies
        "ref_enum_values",         # Enum Field Values
    ],
    "crm_contacts": [
        "ref_crm_statuses",
        "ref_enum_values",
    ],
    "crm_leads": [
        "ref_crm_statuses",
        "ref_enum_values",
    ],
    "crm_companies": [
        "ref_crm_statuses",
        "ref_enum_values",
    ],
}


class ChartService:
    """Service for chart generation, validation, and persistence."""

    # === Helper Methods ===

    @staticmethod
    def get_related_tables(entity_table: str) -> list[str]:
        """Get related reference tables for a given entity table.

        Args:
            entity_table: Main entity table name (e.g., 'crm_deals')

        Returns:
            List of related reference table names
        """
        return _ENTITY_RELATED_TABLES.get(entity_table, [])

    @staticmethod
    def expand_tables_with_related(tables: list[str]) -> list[str]:
        """Expand a list of tables to include related reference tables.

        Args:
            tables: List of main entity table names

        Returns:
            Expanded list including all related reference tables (deduplicated)
        """
        expanded = set(tables)
        for table in tables:
            related = ChartService.get_related_tables(table)
            expanded.update(related)
        return sorted(expanded)

    # === Helper Methods for Metadata ===

    async def _get_enum_values_map(
        self,
    ) -> dict[str, dict[str, list[str]]]:
        """Get enum values for userfields grouped by table and field_name.

        Returns:
            Dict[table_name, Dict[field_name, List[values]]]
        """
        engine = get_engine()
        query = text(
            "SELECT entity_type, field_name, value "
            "FROM ref_enum_values "
            "ORDER BY entity_type, field_name, sort"
        )

        try:
            async with engine.begin() as conn:
                result = await conn.execute(query)
                rows = result.fetchall()
        except Exception as e:
            logger.warning("Failed to get enum values", error=str(e))
            return {}

        # Group by entity_type (maps to table name) and field_name
        enum_map: dict[str, dict[str, list[str]]] = {}
        for row in rows:
            entity_type, field_name, value = row[0], row[1], row[2]
            # entity_type maps to table name (e.g., "DEAL" -> "crm_deals")
            table_name = f"crm_{entity_type.lower()}s"
            enum_map.setdefault(table_name, {}).setdefault(field_name, []).append(
                value
            )

        return enum_map

    # === SQL Validation ===

    @staticmethod
    def validate_sql_query(sql: str) -> None:
        """Validate that the SQL query is safe to execute.

        Only SELECT queries are allowed. DDL/DML keywords and multiple
        statements are prohibited.
        """
        cleaned = sql.strip()

        if not cleaned.upper().startswith("SELECT"):
            raise ChartServiceError("Разрешены только SELECT-запросы")

        if ";" in cleaned:
            raise ChartServiceError("Множественные SQL-statements запрещены")

        match = _FORBIDDEN_KEYWORDS.search(cleaned)
        if match:
            raise ChartServiceError(
                f"Запрещённый SQL-оператор: {match.group(0).upper()}"
            )

    @staticmethod
    def validate_table_names(sql: str, allowed_tables: list[str]) -> None:
        """Ensure the query only references allowed tables."""
        tables_in_query = _TABLE_PATTERN.findall(sql)

        for table in tables_in_query:
            if table.lower() not in [t.lower() for t in allowed_tables]:
                raise ChartServiceError(
                    f"Таблица '{table}' не входит в список разрешённых. "
                    f"Разрешены: {', '.join(allowed_tables)}"
                )

    @staticmethod
    def ensure_limit(sql: str, max_rows: int) -> str:
        """Add or cap LIMIT clause in the SQL query."""
        limit_match = _LIMIT_PATTERN.search(sql)

        if limit_match:
            current_limit = int(limit_match.group(1))
            if current_limit > max_rows:
                sql = _LIMIT_PATTERN.sub(f"LIMIT {max_rows}", sql)
        else:
            sql = sql.rstrip().rstrip(";")
            sql = f"{sql} LIMIT {max_rows}"

        return sql

    # === Schema context ===

    async def get_schema_context(
        self, table_filter: list[str] | None = None, include_related: bool = True
    ) -> str:
        """Collect schema info from information_schema for CRM tables.

        Args:
            table_filter: Optional list of specific tables to include
            include_related: If True, automatically include related reference tables
                           for filtered entity tables (default: True)

        Returns a formatted string describing tables and columns.
        """
        engine = get_engine()
        dialect = get_dialect()

        # Expand table filter to include related tables if requested
        effective_filter = table_filter
        if table_filter and include_related:
            effective_filter = self.expand_tables_with_related(table_filter)
            logger.info(
                "Expanded table filter with related tables",
                original=table_filter,
                expanded=effective_filter,
            )

        # Query for CRM and reference tables with comments
        if dialect == "mysql":
            query = text(
                "SELECT table_name, column_name, data_type, is_nullable, column_comment "
                "FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND (table_name LIKE 'crm_%' OR table_name LIKE 'ref_%') "
                "ORDER BY table_name, ordinal_position"
            )
        else:
            # PostgreSQL: get comments from pg_description (optimized)
            query = text(
                """
                SELECT
                    c.table_name,
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    col_description((quote_ident(c.table_schema)||'.'||quote_ident(c.table_name))::regclass::oid, c.ordinal_position) as column_comment
                FROM information_schema.columns c
                WHERE c.table_schema = current_schema()
                  AND (c.table_name LIKE 'crm_%' OR c.table_name LIKE 'ref_%')
                ORDER BY c.table_name, c.ordinal_position
                """
            )

        async with engine.begin() as conn:
            result = await conn.execute(query)
            rows = result.fetchall()

        # Get enum values for userfields
        enum_values_map = await self._get_enum_values_map()

        # Group by table
        tables: dict[str, list[tuple[str, str, str, str | None]]] = {}
        for row in rows:
            tbl, col, dtype, nullable, comment = row[0], row[1], row[2], row[3], row[4]
            if effective_filter and tbl not in effective_filter:
                continue
            tables.setdefault(tbl, []).append((col, dtype, nullable, comment))

        # Format as text
        lines: list[str] = []
        for tbl, columns in tables.items():
            lines.append(f"Table: {tbl}")
            lines.append("  Columns:")
            for col, dtype, nullable, comment in columns:
                null_str = "NULL" if nullable == "YES" else "NOT NULL"

                # Build description
                description_parts = [f"{dtype}", null_str]
                if comment:
                    description_parts.append(f"- {comment}")

                # Add enum values if available
                if col.startswith("uf_crm_") and tbl in enum_values_map:
                    enum_vals = enum_values_map[tbl].get(col, [])
                    if enum_vals:
                        enum_str = ", ".join(enum_vals[:5])  # Show first 5 values
                        if len(enum_vals) > 5:
                            enum_str += f", ... (+{len(enum_vals) - 5} more)"
                        description_parts.append(f"(enum: {enum_str})")

                description = " ".join(description_parts)
                lines.append(f"    - {col}: {description}")
            lines.append("")

        context = "\n".join(lines)
        logger.info("Schema context collected", tables=len(tables))
        return context

    async def get_allowed_tables(self) -> list[str]:
        """Get list of CRM and reference table names from information_schema."""
        engine = get_engine()
        dialect = get_dialect()

        if dialect == "mysql":
            query = text(
                "SELECT DISTINCT table_name "
                "FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND (table_name LIKE 'crm_%' OR table_name LIKE 'ref_%')"
            )
        else:
            query = text(
                "SELECT DISTINCT table_name "
                "FROM information_schema.columns "
                "WHERE (table_name LIKE 'crm_%' OR table_name LIKE 'ref_%')"
            )

        async with engine.begin() as conn:
            result = await conn.execute(query)
            rows = result.fetchall()

        return [row[0] for row in rows]

    async def get_tables_info(
        self, table_filter: list[str] | None = None, include_related: bool = True
    ) -> list[dict[str, Any]]:
        """Get table structure for /schema/tables endpoint.

        Args:
            table_filter: Optional list of specific tables to include
            include_related: If True, automatically include related reference tables
                           for filtered entity tables (default: True)

        Returns list of dicts with table_name, columns, and row_count.
        """
        engine = get_engine()
        dialect = get_dialect()

        # Expand table filter to include related tables if requested
        effective_filter = table_filter
        if table_filter and include_related:
            effective_filter = self.expand_tables_with_related(table_filter)
            logger.info(
                "Expanded table filter with related tables",
                original=table_filter,
                expanded=effective_filter,
            )

        # Query for CRM and reference tables with comments
        if dialect == "mysql":
            query = text(
                "SELECT table_name, column_name, data_type, is_nullable, column_default, column_comment "
                "FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND (table_name LIKE 'crm_%' OR table_name LIKE 'ref_%') "
                "ORDER BY table_name, ordinal_position"
            )
        else:
            # PostgreSQL: get comments from pg_description (optimized)
            query = text(
                """
                SELECT
                    c.table_name,
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    c.column_default,
                    col_description((quote_ident(c.table_schema)||'.'||quote_ident(c.table_name))::regclass::oid, c.ordinal_position) as column_comment
                FROM information_schema.columns c
                WHERE c.table_schema = current_schema()
                  AND (c.table_name LIKE 'crm_%' OR c.table_name LIKE 'ref_%')
                ORDER BY c.table_name, c.ordinal_position
                """
            )

        async with engine.begin() as conn:
            result = await conn.execute(query)
            rows = result.fetchall()

        # Get enum values for userfields
        enum_values_map = await self._get_enum_values_map()

        # Group by table
        tables: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            tbl = row[0]
            col_name = row[1]
            # Apply filter if specified
            if effective_filter and tbl not in effective_filter:
                continue

            # Build column description with comment and enum values
            comment = row[5] if len(row) > 5 else None
            description = comment or ""

            # Add enum values if available
            if col_name.startswith("uf_crm_") and tbl in enum_values_map:
                enum_vals = enum_values_map[tbl].get(col_name, [])
                if enum_vals:
                    enum_str = ", ".join(enum_vals[:10])  # Show first 10 values
                    if len(enum_vals) > 10:
                        enum_str += f" (+ еще {len(enum_vals) - 10})"
                    if description:
                        description += f" (enum: {enum_str})"
                    else:
                        description = f"Enumeration: {enum_str}"

            tables.setdefault(tbl, []).append(
                {
                    "name": col_name,
                    "data_type": row[2],
                    "is_nullable": row[3] == "YES",
                    "column_default": row[4],
                    "description": description,
                }
            )

        # Get row counts
        result_list: list[dict[str, Any]] = []
        for tbl, columns in tables.items():
            try:
                count_query = text(f"SELECT COUNT(*) FROM {tbl}")  # noqa: S608
                async with engine.begin() as conn:
                    count_result = await conn.execute(count_query)
                    row_count = count_result.scalar()
            except Exception:
                row_count = None

            result_list.append(
                {
                    "table_name": tbl,
                    "columns": columns,
                    "row_count": row_count,
                }
            )

        return result_list

    # === Query Execution ===

    async def execute_chart_query(self, sql: str) -> tuple[list[dict[str, Any]], float]:
        """Execute a validated SQL query with timeout protection.

        Returns (rows_as_dicts, execution_time_ms).
        """
        engine = get_engine()
        dialect = get_dialect()
        settings = get_settings()
        timeout = settings.chart_query_timeout_seconds

        start = time.monotonic()

        try:
            if dialect == "postgresql":
                async with engine.begin() as conn:
                    await conn.execute(
                        text(f"SET LOCAL statement_timeout = '{timeout * 1000}'")
                    )
                    result = await conn.execute(text(sql))
                    columns = list(result.keys())
                    rows = [dict(zip(columns, row)) for row in result.fetchall()]
            else:
                # MySQL: use asyncio timeout
                async with engine.begin() as conn:
                    result = await asyncio.wait_for(
                        conn.execute(text(sql)),
                        timeout=timeout,
                    )
                    columns = list(result.keys())
                    rows = [dict(zip(columns, row)) for row in result.fetchall()]
        except asyncio.TimeoutError as e:
            raise ChartServiceError(
                f"Запрос превысил таймаут ({timeout}с)"
            ) from e
        except Exception as e:
            logger.error("Chart query execution failed", error=str(e), sql=sql)
            raise ChartServiceError(f"Ошибка выполнения запроса: {str(e)}") from e

        elapsed_ms = (time.monotonic() - start) * 1000
        logger.info("Chart query executed", rows=len(rows), time_ms=round(elapsed_ms, 2))
        return rows, elapsed_ms

    # === CRUD ===

    async def save_chart(self, data: dict[str, Any]) -> dict[str, Any]:
        """Insert a new chart into ai_charts and return the created record."""
        engine = get_engine()
        dialect = get_dialect()

        import json as json_mod

        config_json = (
            json_mod.dumps(data["chart_config"], ensure_ascii=False)
            if isinstance(data["chart_config"], dict)
            else data["chart_config"]
        )

        params = {
            "title": data["title"],
            "description": data.get("description"),
            "user_prompt": data["user_prompt"],
            "chart_type": data["chart_type"],
            "chart_config": config_json,
            "sql_query": data["sql_query"],
        }

        if dialect == "mysql":
            query = text(
                "INSERT INTO ai_charts (title, description, user_prompt, chart_type, chart_config, sql_query) "
                "VALUES (:title, :description, :user_prompt, :chart_type, :chart_config, :sql_query)"
            )
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
                chart_id = result.lastrowid
        else:
            query = text(
                "INSERT INTO ai_charts (title, description, user_prompt, chart_type, chart_config, sql_query) "
                "VALUES (:title, :description, :user_prompt, :chart_type, :chart_config, :sql_query) "
                "RETURNING id"
            )
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
                chart_id = result.scalar()

        return await self.get_chart_by_id(chart_id)  # type: ignore[return-value]

    async def get_charts(
        self, page: int = 1, per_page: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        """Get paginated list of saved charts ordered by pinned first, then newest."""
        engine = get_engine()
        offset = (page - 1) * per_page

        count_query = text("SELECT COUNT(*) FROM ai_charts")
        list_query = text(
            "SELECT id, title, description, user_prompt, chart_type, chart_config, "
            "sql_query, is_pinned, created_by, created_at, updated_at "
            "FROM ai_charts "
            "ORDER BY is_pinned DESC, created_at DESC "
            "LIMIT :limit OFFSET :offset"
        )

        async with engine.begin() as conn:
            total = (await conn.execute(count_query)).scalar() or 0
            result = await conn.execute(
                list_query, {"limit": per_page, "offset": offset}
            )
            columns = list(result.keys())
            charts = [dict(zip(columns, row)) for row in result.fetchall()]

        return charts, total

    async def get_chart_by_id(self, chart_id: int) -> dict[str, Any] | None:
        """Get a single chart by ID."""
        engine = get_engine()
        query = text(
            "SELECT id, title, description, user_prompt, chart_type, chart_config, "
            "sql_query, is_pinned, created_by, created_at, updated_at "
            "FROM ai_charts WHERE id = :id"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": chart_id})
            row = result.fetchone()

        if not row:
            return None

        columns = list(result.keys())
        return dict(zip(columns, row))

    async def delete_chart(self, chart_id: int) -> bool:
        """Delete a chart by ID. Returns True if deleted."""
        engine = get_engine()
        query = text("DELETE FROM ai_charts WHERE id = :id")

        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": chart_id})

        return result.rowcount > 0

    async def toggle_pin(self, chart_id: int) -> dict[str, Any]:
        """Toggle the is_pinned flag on a chart."""
        engine = get_engine()
        dialect = get_dialect()

        if dialect == "mysql":
            update_query = text(
                "UPDATE ai_charts SET is_pinned = NOT is_pinned, updated_at = NOW() "
                "WHERE id = :id"
            )
        else:
            update_query = text(
                "UPDATE ai_charts SET is_pinned = NOT is_pinned, updated_at = NOW() "
                "WHERE id = :id"
            )

        async with engine.begin() as conn:
            await conn.execute(update_query, {"id": chart_id})

        chart = await self.get_chart_by_id(chart_id)
        if not chart:
            raise ChartServiceError(f"Чарт с id={chart_id} не найден")
        return chart

    # === Schema Descriptions CRUD ===

    async def get_any_latest_schema_description(self) -> dict[str, Any] | None:
        """Get the most recent schema description regardless of filters."""
        engine = get_engine()
        query = text(
            "SELECT id, markdown, entity_filter, include_related, created_at, updated_at "
            "FROM schema_descriptions "
            "ORDER BY created_at DESC LIMIT 1"
        )
        async with engine.begin() as conn:
            result = await conn.execute(query)
            row = result.fetchone()

        if not row:
            return None

        columns = list(result.keys())
        return dict(zip(columns, row))

    async def save_schema_description(
        self,
        markdown: str,
        entity_filter: list[str] | None = None,
        include_related: bool = True,
    ) -> dict[str, Any]:
        """Save a schema description to the database.

        Args:
            markdown: The generated markdown documentation
            entity_filter: Optional list of filtered tables
            include_related: Whether related tables were included

        Returns:
            The created schema description record
        """
        engine = get_engine()
        dialect = get_dialect()

        entity_filter_str = ",".join(entity_filter) if entity_filter else None

        params = {
            "markdown": markdown,
            "entity_filter": entity_filter_str,
            "include_related": include_related,
        }

        if dialect == "mysql":
            query = text(
                "INSERT INTO schema_descriptions (markdown, entity_filter, include_related) "
                "VALUES (:markdown, :entity_filter, :include_related)"
            )
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
                desc_id = result.lastrowid
        else:
            query = text(
                "INSERT INTO schema_descriptions (markdown, entity_filter, include_related) "
                "VALUES (:markdown, :entity_filter, :include_related) "
                "RETURNING id"
            )
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
                desc_id = result.scalar()

        logger.info("Schema description saved", id=desc_id)
        return await self.get_schema_description_by_id(desc_id)  # type: ignore[return-value]

    async def get_latest_schema_description(
        self,
        entity_filter: list[str] | None = None,
        include_related: bool = True,
    ) -> dict[str, Any] | None:
        """Get the latest schema description matching the filter.

        Args:
            entity_filter: Optional list of filtered tables
            include_related: Whether related tables were included

        Returns:
            The latest matching schema description or None
        """
        engine = get_engine()
        entity_filter_str = ",".join(entity_filter) if entity_filter else None

        if entity_filter_str:
            query = text(
                "SELECT id, markdown, entity_filter, include_related, created_at, updated_at "
                "FROM schema_descriptions "
                "WHERE entity_filter = :entity_filter AND include_related = :include_related "
                "ORDER BY created_at DESC LIMIT 1"
            )
            params = {
                "entity_filter": entity_filter_str,
                "include_related": include_related,
            }
        else:
            query = text(
                "SELECT id, markdown, entity_filter, include_related, created_at, updated_at "
                "FROM schema_descriptions "
                "WHERE entity_filter IS NULL AND include_related = :include_related "
                "ORDER BY created_at DESC LIMIT 1"
            )
            params = {"include_related": include_related}

        async with engine.begin() as conn:
            result = await conn.execute(query, params)
            row = result.fetchone()

        if not row:
            return None

        columns = list(result.keys())
        return dict(zip(columns, row))

    async def get_schema_description_by_id(
        self, desc_id: int
    ) -> dict[str, Any] | None:
        """Get a schema description by ID.

        Args:
            desc_id: Schema description ID

        Returns:
            The schema description record or None
        """
        engine = get_engine()
        query = text(
            "SELECT id, markdown, entity_filter, include_related, created_at, updated_at "
            "FROM schema_descriptions WHERE id = :id"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": desc_id})
            row = result.fetchone()

        if not row:
            return None

        columns = list(result.keys())
        return dict(zip(columns, row))

    async def update_schema_description(
        self, desc_id: int, markdown: str
    ) -> dict[str, Any]:
        """Update the markdown of a schema description.

        Args:
            desc_id: Schema description ID
            markdown: New markdown content

        Returns:
            The updated schema description record
        """
        engine = get_engine()
        dialect = get_dialect()

        if dialect == "mysql":
            query = text(
                "UPDATE schema_descriptions SET markdown = :markdown, updated_at = NOW() "
                "WHERE id = :id"
            )
        else:
            query = text(
                "UPDATE schema_descriptions SET markdown = :markdown, updated_at = NOW() "
                "WHERE id = :id"
            )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": desc_id, "markdown": markdown})

        if result.rowcount == 0:
            raise ChartServiceError(f"Описание схемы с id={desc_id} не найдено")

        logger.info("Schema description updated", id=desc_id)
        desc = await self.get_schema_description_by_id(desc_id)
        if not desc:
            raise ChartServiceError(f"Описание схемы с id={desc_id} не найдено")
        return desc
