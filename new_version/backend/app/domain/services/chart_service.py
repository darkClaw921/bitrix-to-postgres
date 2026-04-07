"""Chart service: SQL validation, query execution, CRUD for saved charts."""

import asyncio
import re
import time
from typing import Any

from sqlalchemy import text

from app.config import get_settings
from app.core.exceptions import ChartServiceError
from app.core.logging import get_logger
from app.domain.services.date_tokens import extend_to_end_of_day, is_date_only
from app.infrastructure.database.connection import get_dialect, get_engine

logger = get_logger(__name__)

# Validates SQL identifiers (table/column names) used in places where bind
# params are not possible — e.g. inside post_filter subqueries and label
# resolvers. Anything that fails this regex is rejected.
_IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

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

# Pattern to find WHERE clause or insertion point for WHERE
_WHERE_PATTERN = re.compile(r"\bWHERE\b", re.IGNORECASE)
_INSERT_BEFORE_PATTERN = re.compile(
    r"\b(GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|OFFSET|UNION|INTERSECT|EXCEPT)\b",
    re.IGNORECASE,
)

# SQL keywords that can never be a valid table alias (they show up after a
# table name in JOIN/FROM constructs and would otherwise be picked up as
# alias by a naive regex).
_NOT_ALIAS_KEYWORDS = frozenset({
    "ON", "WHERE", "GROUP", "ORDER", "HAVING", "LIMIT", "OFFSET",
    "LEFT", "RIGHT", "INNER", "OUTER", "CROSS", "JOIN", "FULL",
    "USING", "UNION", "INTERSECT", "EXCEPT",
})


def _scan_top_level(sql: str, keywords: tuple[str, ...]) -> int | None:
    """Find the start index of the first ``keywords`` token at depth 0.

    Walks the SQL string char-by-char, tracking parenthesis depth and string
    literals so that ``WHERE`` / ``GROUP BY`` etc. inside subqueries or string
    constants are ignored. Returns ``None`` if no top-level match is found.
    """
    n = len(sql)
    depth = 0
    i = 0
    upper = sql.upper()
    upper_keywords = tuple(k.upper() for k in keywords)

    while i < n:
        c = sql[i]

        if c == "'" or c == '"':
            quote = c
            i += 1
            while i < n:
                if sql[i] == "\\":
                    i += 2
                    continue
                if sql[i] == quote:
                    i += 1
                    break
                i += 1
            continue

        if c == "(":
            depth += 1
            i += 1
            continue
        if c == ")":
            depth -= 1
            i += 1
            continue

        if depth == 0 and (i == 0 or not (sql[i - 1].isalnum() or sql[i - 1] == "_")):
            for kw in upper_keywords:
                klen = len(kw)
                if upper[i:i + klen] == kw:
                    end = i + klen
                    if end >= n or not (sql[end].isalnum() or sql[end] == "_"):
                        # GROUP BY / ORDER BY have a space inside; the regex
                        # form normalizes this. We require an exact match here
                        # so single-space variants are fine; if the user wrote
                        # multiple spaces or a tab, we still match because we
                        # only check the first word and the next char is space.
                        return i

        i += 1

    return None


def _resolve_alias(sql: str, table_name: str) -> str:
    """Find the alias used for ``table_name`` in the SQL's FROM/JOIN clauses.

    Returns the alias if found (e.g. ``cd`` for ``crm_deals cd``), otherwise
    returns the original table name. This lets ``apply_filters`` qualify
    columns with the actual identifier the SQL uses.
    """
    # Match "FROM crm_deals AS cd" / "FROM crm_deals cd" / "JOIN crm_deals cd"
    pattern = re.compile(
        r"\b(?:FROM|JOIN)\s+" + re.escape(table_name)
        + r"\b(?:\s+(?:AS\s+)?(\w+))?",
        re.IGNORECASE,
    )
    m = pattern.search(sql)
    if not m:
        return table_name
    alias = m.group(1)
    if not alias:
        return table_name
    if alias.upper() in _NOT_ALIAS_KEYWORDS:
        return table_name
    return alias


def _infer_qualifier_for_column(sql: str, column: str) -> str | None:
    """Guess a safe alias prefix for an unqualified column.

    When ``target_table`` is missing on a selector mapping, ``apply_filters``
    has no idea which table the column belongs to. If the same column name
    exists in multiple JOINed tables (e.g. ``stage_history_deals sh`` joined
    with ``stage_history_deals sh2``), MySQL raises "ambiguous column".

    Strategy (in order of preference):
        1. The first ``FROM <table> [alias]`` token — that's the chart's
           primary entity, the one most semantic filters target. If the SQL
           also references ``{alias}.{column}`` somewhere, we know the column
           is valid on that alias and use it.
        2. Otherwise, reuse whatever alias the SQL already pairs with this
           column name (e.g. ``sh2.created_time``), so at least the query
           runs without an ambiguous-column error.
        3. As a last resort, return the first FROM alias (or table name) even
           without a confirmed match.
    """
    from_match = re.search(
        r"\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)\b(?:\s+(?:AS\s+)?([a-zA-Z_][a-zA-Z0-9_]*))?",
        sql,
        re.IGNORECASE,
    )
    primary_alias: str | None = None
    if from_match:
        table = from_match.group(1)
        alias = from_match.group(2)
        if alias and alias.upper() not in _NOT_ALIAS_KEYWORDS:
            primary_alias = alias
        else:
            primary_alias = table

    # 1) Prefer the primary FROM alias when it actually owns this column.
    if primary_alias:
        owns = re.search(
            r"\b" + re.escape(primary_alias) + r"\." + re.escape(column) + r"\b",
            sql,
        )
        if owns:
            return primary_alias

    # 2) Fall back to the first existing qualified usage.
    qualified = re.search(
        r"\b([a-zA-Z_][a-zA-Z0-9_]*)\." + re.escape(column) + r"\b",
        sql,
    )
    if qualified:
        candidate = qualified.group(1)
        if candidate.upper() not in _NOT_ALIAS_KEYWORDS:
            return candidate

    # 3) Last resort: use the primary FROM alias even without a confirmed match.
    return primary_alias

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
    "bitrix_users": [],
    "bitrix_tasks": [
        "bitrix_users",  # Tasks reference users (RESPONSIBLE_ID, CREATED_BY, etc.)
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
                "WHERE table_schema = DATABASE() AND (table_name LIKE 'crm_%' OR table_name LIKE 'ref_%' OR table_name LIKE 'bitrix_%') "
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
                  AND (c.table_name LIKE 'crm_%' OR c.table_name LIKE 'ref_%' OR c.table_name LIKE 'bitrix_%')
                ORDER BY c.table_name, c.ordinal_position
                """
            )

        async with engine.begin() as conn:
            result = await conn.execute(query)
            rows = result.fetchall()

        # Get enum values for userfields
        enum_values_map = await self._get_enum_values_map()

        # System columns present in every table — excluded from AI context
        _SYSTEM_COLS = {"record_id", "bitrix_id", "created_at", "updated_at"}

        # Group by table
        tables: dict[str, list[tuple[str, str, str, str | None]]] = {}
        for row in rows:
            tbl, col, dtype, nullable, comment = row[0], row[1], row[2], row[3], row[4]
            if effective_filter and tbl not in effective_filter:
                continue
            if col in _SYSTEM_COLS:
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
                "WHERE table_schema = DATABASE() AND (table_name LIKE 'crm_%' OR table_name LIKE 'ref_%' OR table_name LIKE 'bitrix_%' OR table_name LIKE 'stage_history_%')"
            )
        else:
            query = text(
                "SELECT DISTINCT table_name "
                "FROM information_schema.columns "
                "WHERE (table_name LIKE 'crm_%' OR table_name LIKE 'ref_%' OR table_name LIKE 'bitrix_%' OR table_name LIKE 'stage_history_%')"
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
                "WHERE table_schema = DATABASE() AND (table_name LIKE 'crm_%' OR table_name LIKE 'ref_%' OR table_name LIKE 'bitrix_%') "
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
                  AND (c.table_name LIKE 'crm_%' OR c.table_name LIKE 'ref_%' OR c.table_name LIKE 'bitrix_%')
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

        # Get row counts in a single batch query (fast estimate for PG, exact for MySQL)
        row_counts: dict[str, int | None] = {}
        table_names = list(tables.keys())
        if table_names:
            try:
                if dialect == "mysql":
                    # MySQL: TABLE_ROWS from information_schema (approximate)
                    placeholders = ", ".join([f":t{i}" for i in range(len(table_names))])
                    count_query = text(
                        f"SELECT table_name, table_rows FROM information_schema.tables "
                        f"WHERE table_schema = DATABASE() AND table_name IN ({placeholders})"
                    )
                    params = {f"t{i}": name for i, name in enumerate(table_names)}
                else:
                    # PostgreSQL: fast estimate from pg_class
                    placeholders = ", ".join([f":t{i}" for i in range(len(table_names))])
                    count_query = text(
                        f"SELECT relname, reltuples::bigint FROM pg_class "
                        f"WHERE relname IN ({placeholders})"
                    )
                    params = {f"t{i}": name for i, name in enumerate(table_names)}

                async with engine.begin() as conn:
                    count_result = await conn.execute(count_query, params)
                    for row in count_result.fetchall():
                        count_val = row[1]
                        row_counts[row[0]] = max(0, count_val) if count_val is not None else None
            except Exception:
                pass

        result_list: list[dict[str, Any]] = []
        for tbl, columns in tables.items():
            result_list.append(
                {
                    "table_name": tbl,
                    "columns": columns,
                    "row_count": row_counts.get(tbl),
                }
            )

        return result_list

    # === Filter Application ===

    @staticmethod
    def _build_condition(
        col_ref: str,
        op: str,
        value: Any,
        prefix: str,
        bind_params: dict[str, Any],
    ) -> str | None:
        """Build a single SQL condition and populate bind_params.

        Returns the condition string, or ``None`` if the value is not usable
        (e.g. an empty IN list).
        """
        if op == "equals":
            bind_params[prefix] = value
            return f"{col_ref} = :{prefix}"
        if op == "not_equals":
            bind_params[prefix] = value
            return f"{col_ref} != :{prefix}"
        if op in ("in", "not_in"):
            if not isinstance(value, list) or not value:
                return None
            placeholders = ", ".join(f":{prefix}_{i}" for i in range(len(value)))
            for i, v in enumerate(value):
                bind_params[f"{prefix}_{i}"] = v
            keyword = "IN" if op == "in" else "NOT IN"
            return f"{col_ref} {keyword} ({placeholders})"
        if op == "between":
            if not isinstance(value, dict):
                return None
            from_val = value.get("from")
            to_val = value.get("to")
            # Auto-extend date-only "to" to end of day so the range covers it.
            if is_date_only(to_val):
                to_val = extend_to_end_of_day(to_val)
            bind_params[f"{prefix}_from"] = from_val
            bind_params[f"{prefix}_to"] = to_val
            return f"{col_ref} BETWEEN :{prefix}_from AND :{prefix}_to"
        if op == "gt":
            bind_params[prefix] = value
            return f"{col_ref} > :{prefix}"
        if op == "lt":
            bind_params[prefix] = value
            return f"{col_ref} < :{prefix}"
        if op == "gte":
            bind_params[prefix] = value
            return f"{col_ref} >= :{prefix}"
        if op == "lte":
            # Auto-extend date-only value to end of day for inclusive comparison.
            bind_params[prefix] = extend_to_end_of_day(value) if is_date_only(value) else value
            return f"{col_ref} <= :{prefix}"
        if op == "like":
            bind_params[prefix] = f"%{value}%"
            return f"{col_ref} LIKE :{prefix}"
        if op == "not_like":
            bind_params[prefix] = f"%{value}%"
            return f"{col_ref} NOT LIKE :{prefix}"
        return None

    @staticmethod
    def apply_filters(
        sql: str,
        filters: list[dict[str, Any]],
    ) -> tuple[str, dict[str, Any]]:
        """Inject WHERE/AND conditions into SQL based on filter definitions.

        Each filter dict has:
            - column: str — target column name
            - operator: str — equals|not_equals|in|not_in|between|gt|lt|gte|lte|like|not_like
            - value: Any — the filter value(s)
            - table: str|None — optional table qualifier for disambiguation
            - param_prefix: str — unique prefix for bind params (e.g. "p0")
            - post_filter: dict|None — optional two-step filter:
                {resolve_table, resolve_column, resolve_id_column}.
                When set, the condition becomes
                ``col IN (SELECT id_col FROM resolve_table WHERE resolve_col <op> :prefix)``
                instead of a direct comparison. Used when ``column`` is in the
                chart's table but the selector value semantically belongs to a
                different (related) table.

        Returns (modified_sql, bind_params).
        """
        if not filters:
            return sql, {}

        conditions: list[str] = []
        bind_params: dict[str, Any] = {}

        for f in filters:
            col = f["column"]
            op = f["operator"]
            value = f["value"]
            table = f.get("table")
            prefix = f["param_prefix"]

            # Strip any pre-existing qualifier from the column name. The user (or
            # AI) sometimes saves target_column as "d.date_create" or
            # "crm_deals.date_create"; without this we'd end up with
            # "d.d.date_create" once the alias is prepended below.
            if "." in col:
                col = col.rsplit(".", 1)[-1]

            # Column reference: if a table qualifier was supplied, prefer the
            # alias actually used in the chart's SQL (so a mapping with
            # table="crm_deals" against a query "FROM crm_deals cd" produces
            # "cd.col", not the broken "crm_deals.cd.col").
            if table:
                qualifier = _resolve_alias(sql, table)
                col_ref = f"{qualifier}.{col}"
            else:
                # No explicit table — try to infer a qualifier so the column
                # doesn't collide with the same name in another JOINed alias.
                inferred = _infer_qualifier_for_column(sql, col)
                col_ref = f"{inferred}.{col}" if inferred else col

            pf = f.get("post_filter")
            if pf:
                resolve_table = pf.get("resolve_table")
                resolve_column = pf.get("resolve_column")
                resolve_id_column = pf.get("resolve_id_column") or "id"

                # Identifier validation — these go directly into SQL text.
                if not (
                    resolve_table
                    and resolve_column
                    and _IDENT_RE.match(resolve_table)
                    and _IDENT_RE.match(resolve_column)
                    and _IDENT_RE.match(resolve_id_column)
                ):
                    raise ChartServiceError(
                        "Невалидное имя таблицы/колонки в post_filter"
                    )

                # Build the inner WHERE for the subquery — same operator semantics,
                # just applied to (resolve_table.resolve_column).
                inner_clause = ChartService._build_condition(
                    resolve_column, op, value, prefix, bind_params
                )
                if inner_clause is None:
                    continue
                conditions.append(
                    f"{col_ref} IN (SELECT {resolve_id_column} FROM {resolve_table} WHERE {inner_clause})"
                )
                continue

            clause = ChartService._build_condition(col_ref, op, value, prefix, bind_params)
            if clause is not None:
                conditions.append(clause)

        if not conditions:
            return sql, {}

        where_clause = " AND ".join(conditions)

        # Find the boundary keywords at the *top level* of the SQL — anything
        # inside parentheses (subqueries, function calls) is ignored. This
        # prevents inserting filter conditions into a subquery's WHERE or
        # accidentally turning a JOIN's ON into a filter.
        top_where = _scan_top_level(sql, ("WHERE",))
        top_insert_before = _scan_top_level(
            sql,
            (
                "GROUP BY",
                "ORDER BY",
                "HAVING",
                "LIMIT",
                "OFFSET",
                "UNION",
                "INTERSECT",
                "EXCEPT",
            ),
        )

        if top_where is not None:
            # Append the new conditions to the existing top-level WHERE, but
            # WRAP THE EXISTING CONDITIONS IN PARENTHESES FIRST. SQL operator
            # precedence puts AND above OR, so appending " AND new_cond" to a
            # WHERE that contains a top-level OR (e.g. "WHERE a = 1 OR b = 2")
            # would parse as "a = 1 OR (b = 2 AND new_cond)" — the new filter
            # silently wouldn't apply to the first branch of the OR. Wrapping
            # the original conditions in parens preserves the intended
            # semantics regardless of how they're composed.
            if top_insert_before is not None and top_insert_before > top_where:
                where_end = top_insert_before
                suffix = sql[where_end:]
            else:
                stripped = sql.rstrip().rstrip(";")
                where_end = len(stripped)
                suffix = sql[where_end:]

            # sql[top_where:top_where+5] is "WHERE" (case-insensitive); strip
            # the keyword and whitespace to get just the existing conditions.
            existing_conditions = sql[top_where + 5:where_end].strip()
            prefix = sql[:top_where].rstrip()
            new_where = (
                f"WHERE ({existing_conditions}) AND {where_clause}"
                if existing_conditions
                else f"WHERE {where_clause}"
            )
            modified_sql = f"{prefix} {new_where}"
            if suffix:
                modified_sql += f" {suffix.lstrip()}"
        else:
            # No top-level WHERE — insert one before the next boundary keyword.
            if top_insert_before is not None:
                insert_pos = top_insert_before
                modified_sql = (
                    sql[:insert_pos].rstrip()
                    + f" WHERE {where_clause} "
                    + sql[insert_pos:]
                )
            else:
                modified_sql = sql.rstrip().rstrip(";") + f" WHERE {where_clause}"

        return modified_sql, bind_params

    # === Label Resolvers (post-processing chart data) ===

    async def resolve_labels_in_data(
        self,
        rows: list[dict[str, Any]],
        resolvers: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        """Replace raw IDs in chart rows with display labels.

        Each resolver describes how to look up a column's display label::

            {
                "column": "assigned_by_id",
                "resolve_table": "crm_users",
                "resolve_value_column": "id",
                "resolve_label_column": "name"
            }

        For each resolver this loads the entire ``SELECT value, label FROM table``
        once and rewrites every matching cell in ``rows``. Identifiers are
        validated against ``_IDENT_RE`` to prevent SQL injection (the values are
        spliced into SQL text, not bound).

        Unknown values pass through unchanged. Resolvers with invalid identifiers
        are silently skipped (logged as warning).
        """
        if not rows or not resolvers:
            return rows

        engine = get_engine()
        for r in resolvers:
            col = r.get("column")
            tbl = r.get("resolve_table")
            val_col = r.get("resolve_value_column") or "id"
            lbl_col = r.get("resolve_label_column")

            if not col or not tbl or not lbl_col:
                continue
            if not (
                _IDENT_RE.match(col)
                and _IDENT_RE.match(tbl)
                and _IDENT_RE.match(val_col)
                and _IDENT_RE.match(lbl_col)
            ):
                logger.warning(
                    "Skipping label resolver with invalid identifiers",
                    column=col, table=tbl, value_col=val_col, label_col=lbl_col,
                )
                continue

            # Skip if no row actually contains this column.
            if not any(col in row for row in rows):
                continue

            sql = (
                f"SELECT {val_col} AS v, {lbl_col} AS l FROM {tbl}"  # noqa: S608
            )
            try:
                async with engine.begin() as conn:
                    result = await conn.execute(text(sql))
                    mapping = {
                        str(row[0]): row[1] for row in result.fetchall() if row[0] is not None
                    }
            except Exception as e:
                logger.warning("Label resolver query failed", table=tbl, error=str(e))
                continue

            for row in rows:
                if col not in row:
                    continue
                raw = row[col]
                if raw is None:
                    continue
                key = str(raw)
                if key in mapping:
                    row[col] = mapping[key]

        return rows

    # === MySQL SQL Compatibility ===

    @staticmethod
    def fix_sql_for_mysql(sql: str) -> str:
        """Fix common MySQL incompatibilities in AI-generated SQL.

        Handles two known issues:
        1. CAST(... AS varchar) → CAST(... AS CHAR)
           MySQL does not support 'varchar' as a type in CAST expressions.
        2. Double-quoted identifiers "alias" → `alias`
           AI models trained on PostgreSQL/ANSI SQL use double quotes for identifiers.
           MySQL (without ANSI_QUOTES mode) treats double quotes as string literals,
           which breaks ORDER BY "alias" and AS "alias" patterns.

        Note: assumes string literals in WHERE/HAVING use single quotes (standard practice).
        """
        # Fix CAST AS varchar → CHAR (MySQL-specific CAST type)
        sql = re.sub(r"\bAS\s+varchar\b", "AS CHAR", sql, flags=re.IGNORECASE)

        # Fix double-quoted identifiers → backtick identifiers
        # Replaces all "text" patterns; safe because AI SQL uses single quotes for string literals
        sql = re.sub(r'"([^"]+)"', r"`\1`", sql)

        return sql

    # === Query Execution ===

    async def execute_chart_query(
        self, sql: str, bind_params: dict[str, Any] | None = None
    ) -> tuple[list[dict[str, Any]], float]:
        """Execute a validated SQL query with timeout protection.

        Args:
            sql: The SQL query to execute
            bind_params: Optional bind parameters for parameterized queries

        Returns (rows_as_dicts, execution_time_ms).
        """
        engine = get_engine()
        dialect = get_dialect()
        settings = get_settings()
        timeout = settings.chart_query_timeout_seconds

        # Apply MySQL-specific fixes for AI-generated SQL incompatibilities
        if dialect == "mysql":
            sql = self.fix_sql_for_mysql(sql)

        start = time.monotonic()

        stmt = text(sql)
        if bind_params:
            stmt = stmt.bindparams(**bind_params)

        try:
            if dialect == "postgresql":
                async with engine.begin() as conn:
                    await conn.execute(
                        text(f"SET LOCAL statement_timeout = '{timeout * 1000}'")
                    )
                    result = await conn.execute(stmt)
                    columns = list(result.keys())
                    rows = [dict(zip(columns, row)) for row in result.fetchall()]
            else:
                # MySQL: use asyncio timeout
                async with engine.begin() as conn:
                    result = await asyncio.wait_for(
                        conn.execute(stmt),
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

    async def update_chart_config(
        self, chart_id: int, config_patch: dict[str, Any]
    ) -> dict[str, Any]:
        """Deep-merge config_patch into existing chart_config and persist.

        Returns the updated chart record.
        """
        import json as json_mod

        chart = await self.get_chart_by_id(chart_id)
        if not chart:
            raise ChartServiceError(f"Чарт с id={chart_id} не найден")

        existing_config = chart["chart_config"]
        if isinstance(existing_config, str):
            existing_config = json_mod.loads(existing_config)

        # Deep merge: update nested dicts, replace scalars
        for key, value in config_patch.items():
            if (
                isinstance(value, dict)
                and key in existing_config
                and isinstance(existing_config[key], dict)
            ):
                existing_config[key].update(value)
            else:
                existing_config[key] = value

        config_json = json_mod.dumps(existing_config, ensure_ascii=False)

        engine = get_engine()
        update_query = text(
            "UPDATE ai_charts SET chart_config = :config, updated_at = NOW() "
            "WHERE id = :id"
        )

        async with engine.begin() as conn:
            await conn.execute(
                update_query, {"id": chart_id, "config": config_json}
            )

        updated = await self.get_chart_by_id(chart_id)
        if not updated:
            raise ChartServiceError(f"Чарт с id={chart_id} не найден после обновления")
        logger.info("Chart config updated", chart_id=chart_id)
        return updated

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

    # === Chart Column Extraction ===

    async def get_chart_columns(self, sql: str) -> list[str]:
        """Extract column names from a chart's SQL by executing with LIMIT 0.

        Args:
            sql: The chart's SQL query.

        Returns:
            List of column names from the query result.
        """
        engine = get_engine()
        dialect = get_dialect()

        # Strip LIMIT and add LIMIT 0
        stripped = _LIMIT_PATTERN.sub("", sql).rstrip().rstrip(";")
        probe_sql = f"{stripped} LIMIT 0"

        try:
            stmt = text(probe_sql)
            if dialect == "postgresql":
                async with engine.begin() as conn:
                    await conn.execute(text("SET LOCAL statement_timeout = '5000'"))
                    result = await conn.execute(stmt)
                    return list(result.keys())
            else:
                async with engine.begin() as conn:
                    result = await conn.execute(stmt)
                    return list(result.keys())
        except Exception as e:
            logger.warning("Failed to extract chart columns", error=str(e))
            return []

    # === Schema Markdown Generation (no AI) ===

    async def generate_schema_markdown(
        self,
        table_filter: list[str] | None = None,
        include_related: bool = True,
    ) -> str:
        """Generate markdown documentation from DB metadata without AI.

        Builds a markdown string with a table of fields, types, and descriptions
        for each CRM/reference table found in the database.

        Args:
            table_filter: Optional list of specific tables to include
            include_related: If True, automatically include related reference tables

        Returns:
            Markdown string with schema documentation
        """
        tables_raw = await self.get_tables_info(
            table_filter=table_filter, include_related=include_related
        )

        if not tables_raw:
            return ""

        lines: list[str] = ["# Схема базы данных\n"]

        for table in tables_raw:
            table_name = table["table_name"]
            columns = table["columns"]
            row_count = table.get("row_count")

            row_count_str = f" (~{row_count} строк)" if row_count else ""
            lines.append(f"## {table_name}{row_count_str}\n")
            lines.append("| Поле | Тип | Описание |")
            lines.append("|------|-----|----------|")

            for col in columns:
                name = col["name"]
                data_type = col["data_type"]
                description = col.get("description") or ""
                # Escape pipe characters in description for markdown table
                description = description.replace("|", "\\|")
                lines.append(f"| {name} | {data_type} | {description} |")

            lines.append("")

        return "\n".join(lines)

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

    # === Chart Prompt Templates ===

    async def get_chart_prompt_template(self, name: str = "bitrix_context") -> dict[str, Any] | None:
        """Get chart prompt template by name.

        Args:
            name: Template name (default: bitrix_context)

        Returns:
            Template record or None if not found
        """
        engine = get_engine()
        query = text(
            "SELECT id, name, content, is_active, created_at, updated_at "
            "FROM chart_prompt_templates WHERE name = :name"
        )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"name": name})
            row = result.fetchone()

        if not row:
            return None

        columns = list(result.keys())
        return dict(zip(columns, row))

    async def update_chart_prompt_template(
        self, name: str, content: str
    ) -> dict[str, Any]:
        """Update chart prompt template content.

        Args:
            name: Template name
            content: New template content

        Returns:
            Updated template record
        """
        engine = get_engine()
        dialect = get_dialect()

        if dialect == "mysql":
            query = text(
                "UPDATE chart_prompt_templates SET content = :content, updated_at = NOW() "
                "WHERE name = :name"
            )
        else:
            query = text(
                "UPDATE chart_prompt_templates SET content = :content, updated_at = NOW() "
                "WHERE name = :name"
            )

        async with engine.begin() as conn:
            result = await conn.execute(query, {"name": name, "content": content})

        if result.rowcount == 0:
            raise ChartServiceError(f"Промпт с именем '{name}' не найден")

        logger.info("Chart prompt template updated", name=name)
        template = await self.get_chart_prompt_template(name)
        if not template:
            raise ChartServiceError(f"Промпт с именем '{name}' не найден")
        return template
