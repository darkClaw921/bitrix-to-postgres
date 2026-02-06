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


class ChartService:
    """Service for chart generation, validation, and persistence."""

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
        self, table_filter: list[str] | None = None
    ) -> str:
        """Collect schema info from information_schema for CRM tables.

        Returns a formatted string describing tables and columns.
        """
        engine = get_engine()
        dialect = get_dialect()

        if dialect == "mysql":
            query = text(
                "SELECT table_name, column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name LIKE 'crm_%' "
                "ORDER BY table_name, ordinal_position"
            )
        else:
            query = text(
                "SELECT table_name, column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name LIKE 'crm_%' "
                "ORDER BY table_name, ordinal_position"
            )

        async with engine.begin() as conn:
            result = await conn.execute(query)
            rows = result.fetchall()

        # Group by table
        tables: dict[str, list[tuple[str, str, str]]] = {}
        for row in rows:
            tbl, col, dtype, nullable = row[0], row[1], row[2], row[3]
            if table_filter and tbl not in table_filter:
                continue
            tables.setdefault(tbl, []).append((col, dtype, nullable))

        # Format as text
        lines: list[str] = []
        for tbl, columns in tables.items():
            lines.append(f"Table: {tbl}")
            lines.append("  Columns:")
            for col, dtype, nullable in columns:
                null_str = "NULL" if nullable == "YES" else "NOT NULL"
                lines.append(f"    - {col} ({dtype}, {null_str})")
            lines.append("")

        context = "\n".join(lines)
        logger.info("Schema context collected", tables=len(tables))
        return context

    async def get_allowed_tables(self) -> list[str]:
        """Get list of CRM table names from information_schema."""
        engine = get_engine()
        dialect = get_dialect()

        if dialect == "mysql":
            query = text(
                "SELECT DISTINCT table_name "
                "FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name LIKE 'crm_%'"
            )
        else:
            query = text(
                "SELECT DISTINCT table_name "
                "FROM information_schema.columns "
                "WHERE table_name LIKE 'crm_%'"
            )

        async with engine.begin() as conn:
            result = await conn.execute(query)
            rows = result.fetchall()

        return [row[0] for row in rows]

    async def get_tables_info(self) -> list[dict[str, Any]]:
        """Get table structure for /schema/tables endpoint.

        Returns list of dicts with table_name, columns, and row_count.
        """
        engine = get_engine()
        dialect = get_dialect()

        if dialect == "mysql":
            query = text(
                "SELECT table_name, column_name, data_type, is_nullable, column_default "
                "FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name LIKE 'crm_%' "
                "ORDER BY table_name, ordinal_position"
            )
        else:
            query = text(
                "SELECT table_name, column_name, data_type, is_nullable, column_default "
                "FROM information_schema.columns "
                "WHERE table_name LIKE 'crm_%' "
                "ORDER BY table_name, ordinal_position"
            )

        async with engine.begin() as conn:
            result = await conn.execute(query)
            rows = result.fetchall()

        # Group by table
        tables: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            tbl = row[0]
            tables.setdefault(tbl, []).append(
                {
                    "name": row[1],
                    "data_type": row[2],
                    "is_nullable": row[3] == "YES",
                    "column_default": row[4],
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
