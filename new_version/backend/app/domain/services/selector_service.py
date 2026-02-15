"""Selector service: CRUD, mappings, options, filter building for dashboard selectors."""

import json as json_mod
import re
from typing import Any

from sqlalchemy import text

from app.core.logging import get_logger
from app.infrastructure.database.connection import get_dialect, get_engine

_TABLE_PATTERN = re.compile(
    r"(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.IGNORECASE
)

logger = get_logger(__name__)


class SelectorService:
    """Service for dashboard selector operations."""

    # === CRUD ===

    async def create_selector(
        self,
        dashboard_id: int,
        name: str,
        label: str,
        selector_type: str,
        operator: str = "equals",
        config: dict[str, Any] | None = None,
        sort_order: int = 0,
        is_required: bool = False,
    ) -> dict[str, Any]:
        engine = get_engine()
        dialect = get_dialect()

        params = {
            "dashboard_id": dashboard_id,
            "name": name,
            "label": label,
            "selector_type": selector_type,
            "operator": operator,
            "config": json_mod.dumps(config) if config else None,
            "sort_order": sort_order,
            "is_required": is_required,
        }

        if dialect == "mysql":
            query = text(
                "INSERT INTO dashboard_selectors "
                "(dashboard_id, name, label, selector_type, operator, config, sort_order, is_required) "
                "VALUES (:dashboard_id, :name, :label, :selector_type, :operator, :config, :sort_order, :is_required)"
            )
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
                selector_id = result.lastrowid
        else:
            query = text(
                "INSERT INTO dashboard_selectors "
                "(dashboard_id, name, label, selector_type, operator, config, sort_order, is_required) "
                "VALUES (:dashboard_id, :name, :label, :selector_type, :operator, :config, :sort_order, :is_required) "
                "RETURNING id"
            )
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
                selector_id = result.scalar()

        logger.info("Selector created", id=selector_id, dashboard_id=dashboard_id, name=name)
        return await self.get_selector_by_id(selector_id)

    async def get_selector_by_id(self, selector_id: int) -> dict[str, Any] | None:
        engine = get_engine()

        query = text(
            "SELECT id, dashboard_id, name, label, selector_type, operator, "
            "config, sort_order, is_required, created_at "
            "FROM dashboard_selectors WHERE id = :id"
        )
        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": selector_id})
            row = result.fetchone()

        if not row:
            return None

        selector = dict(zip(list(result.keys()), row))
        if isinstance(selector.get("config"), str):
            selector["config"] = json_mod.loads(selector["config"])
        selector["mappings"] = await self._get_mappings(selector_id)
        return selector

    async def get_selectors_for_dashboard(self, dashboard_id: int) -> list[dict[str, Any]]:
        engine = get_engine()

        query = text(
            "SELECT ds.id, ds.dashboard_id, ds.name, ds.label, ds.selector_type, "
            "ds.operator, ds.config, ds.sort_order, ds.is_required, ds.created_at, "
            "scm.id AS mapping_id, scm.dashboard_chart_id, scm.target_column, "
            "scm.target_table, scm.operator_override, scm.created_at AS mapping_created_at "
            "FROM dashboard_selectors ds "
            "LEFT JOIN selector_chart_mappings scm ON scm.selector_id = ds.id "
            "WHERE ds.dashboard_id = :dashboard_id "
            "ORDER BY ds.sort_order, ds.id, scm.id"
        )
        async with engine.begin() as conn:
            result = await conn.execute(query, {"dashboard_id": dashboard_id})
            raw_rows = result.fetchall()
            columns = list(result.keys())

        selectors_map: dict[int, dict[str, Any]] = {}
        for raw in raw_rows:
            row = dict(zip(columns, raw))
            sid = row["id"]
            if sid not in selectors_map:
                config = row["config"]
                if isinstance(config, str):
                    config = json_mod.loads(config)
                selectors_map[sid] = {
                    "id": sid,
                    "dashboard_id": row["dashboard_id"],
                    "name": row["name"],
                    "label": row["label"],
                    "selector_type": row["selector_type"],
                    "operator": row["operator"],
                    "config": config,
                    "sort_order": row["sort_order"],
                    "is_required": row["is_required"],
                    "created_at": row["created_at"],
                    "mappings": [],
                }
            if row["mapping_id"] is not None:
                selectors_map[sid]["mappings"].append({
                    "id": row["mapping_id"],
                    "selector_id": sid,
                    "dashboard_chart_id": row["dashboard_chart_id"],
                    "target_column": row["target_column"],
                    "target_table": row["target_table"],
                    "operator_override": row["operator_override"],
                    "created_at": row["mapping_created_at"],
                })

        return list(selectors_map.values())

    async def update_selector(
        self,
        selector_id: int,
        name: str | None = None,
        label: str | None = None,
        selector_type: str | None = None,
        operator: str | None = None,
        config: dict[str, Any] | None = None,
        sort_order: int | None = None,
        is_required: bool | None = None,
        mappings: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        engine = get_engine()

        updates: list[str] = []
        params: dict[str, Any] = {"id": selector_id}

        if name is not None:
            updates.append("name = :name")
            params["name"] = name
        if label is not None:
            updates.append("label = :label")
            params["label"] = label
        if selector_type is not None:
            updates.append("selector_type = :selector_type")
            params["selector_type"] = selector_type
        if operator is not None:
            updates.append("operator = :operator")
            params["operator"] = operator
        if config is not None:
            updates.append("config = :config")
            params["config"] = json_mod.dumps(config)
        if sort_order is not None:
            updates.append("sort_order = :sort_order")
            params["sort_order"] = sort_order
        if is_required is not None:
            updates.append("is_required = :is_required")
            params["is_required"] = is_required

        if updates:
            set_clause = ", ".join(updates)
            query = text(f"UPDATE dashboard_selectors SET {set_clause} WHERE id = :id")  # noqa: S608
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
            if result.rowcount == 0:
                return None

        # Full replace of mappings if provided
        if mappings is not None:
            await self._replace_mappings(selector_id, mappings)

        return await self.get_selector_by_id(selector_id)

    async def delete_selector(self, selector_id: int) -> bool:
        engine = get_engine()
        query = text("DELETE FROM dashboard_selectors WHERE id = :id")
        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": selector_id})
        return result.rowcount > 0

    # === Mappings ===

    async def _get_mappings(self, selector_id: int) -> list[dict[str, Any]]:
        engine = get_engine()

        query = text(
            "SELECT id, selector_id, dashboard_chart_id, target_column, "
            "target_table, operator_override, created_at "
            "FROM selector_chart_mappings WHERE selector_id = :selector_id "
            "ORDER BY id"
        )
        async with engine.begin() as conn:
            result = await conn.execute(query, {"selector_id": selector_id})
            columns = list(result.keys())
            return [dict(zip(columns, row)) for row in result.fetchall()]

    async def add_mapping(
        self,
        selector_id: int,
        dashboard_chart_id: int,
        target_column: str,
        target_table: str | None = None,
        operator_override: str | None = None,
    ) -> dict[str, Any]:
        engine = get_engine()
        dialect = get_dialect()

        params = {
            "selector_id": selector_id,
            "dashboard_chart_id": dashboard_chart_id,
            "target_column": target_column,
            "target_table": target_table,
            "operator_override": operator_override,
        }

        if dialect == "mysql":
            query = text(
                "INSERT INTO selector_chart_mappings "
                "(selector_id, dashboard_chart_id, target_column, target_table, operator_override) "
                "VALUES (:selector_id, :dashboard_chart_id, :target_column, :target_table, :operator_override)"
            )
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
                mapping_id = result.lastrowid
        else:
            query = text(
                "INSERT INTO selector_chart_mappings "
                "(selector_id, dashboard_chart_id, target_column, target_table, operator_override) "
                "VALUES (:selector_id, :dashboard_chart_id, :target_column, :target_table, :operator_override) "
                "RETURNING id"
            )
            async with engine.begin() as conn:
                result = await conn.execute(query, params)
                mapping_id = result.scalar()

        return {"id": mapping_id, **params}

    async def remove_mapping(self, mapping_id: int) -> bool:
        engine = get_engine()
        query = text("DELETE FROM selector_chart_mappings WHERE id = :id")
        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": mapping_id})
        return result.rowcount > 0

    async def _replace_mappings(
        self, selector_id: int, mappings: list[dict[str, Any]]
    ) -> None:
        engine = get_engine()

        # Delete existing mappings
        delete_query = text(
            "DELETE FROM selector_chart_mappings WHERE selector_id = :selector_id"
        )
        async with engine.begin() as conn:
            await conn.execute(delete_query, {"selector_id": selector_id})

        # Insert new mappings
        for m in mappings:
            await self.add_mapping(
                selector_id=selector_id,
                dashboard_chart_id=m["dashboard_chart_id"],
                target_column=m["target_column"],
                target_table=m.get("target_table"),
                operator_override=m.get("operator_override"),
            )

    # === Filter Building ===

    async def build_filters_for_chart(
        self,
        dashboard_id: int,
        dc_id: int,
        filter_values: dict[str, Any],
        selectors: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Build filter list compatible with ChartService.apply_filters().

        Args:
            dashboard_id: Dashboard ID.
            dc_id: Dashboard chart ID (dashboard_charts.id).
            filter_values: Dict of {selector_name: value} from the client.
            selectors: Pre-loaded selectors (avoids extra DB query).

        Returns:
            List of filter dicts for apply_filters().
        """
        if not filter_values:
            return []

        if selectors is None:
            selectors = await self.get_selectors_for_dashboard(dashboard_id)
        filters: list[dict[str, Any]] = []
        param_idx = 0

        for selector in selectors:
            value = filter_values.get(selector["name"])
            if value is None:
                continue

            # Find mapping for this chart
            mapping = None
            for m in selector.get("mappings", []):
                if m["dashboard_chart_id"] == dc_id:
                    mapping = m
                    break

            if not mapping:
                continue

            operator = mapping.get("operator_override") or selector["operator"]

            filters.append({
                "column": mapping["target_column"],
                "operator": operator,
                "value": value,
                "table": mapping.get("target_table"),
                "param_prefix": f"sf{param_idx}",
            })
            param_idx += 1

        return filters

    # === Options (for dropdown / multi-select) ===

    async def get_selector_options(
        self, selector_id: int
    ) -> list[dict[str, Any]]:
        """Get distinct values for a selector by ID."""
        selector = await self.get_selector_by_id(selector_id)
        if not selector:
            return []
        return await self._resolve_options(selector)

    async def get_all_selector_options(
        self, dashboard_id: int
    ) -> dict[int, list[dict[str, Any]]]:
        """Get options for all dropdown/multi_select selectors in one call."""
        selectors = await self.get_selectors_for_dashboard(dashboard_id)
        result: dict[int, list[dict[str, Any]]] = {}
        for sel in selectors:
            if sel["selector_type"] in ("dropdown", "multi_select"):
                result[sel["id"]] = await self._resolve_options(sel)
        return result

    async def _resolve_options(
        self, selector: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Resolve options for a selector (static values or DB query)."""
        config = selector.get("config") or {}

        # Static values
        if config.get("static_values"):
            return [
                {"value": v.get("value", v), "label": v.get("label", v.get("value", v))}
                if isinstance(v, dict)
                else {"value": v, "label": str(v)}
                for v in config["static_values"]
            ]

        source_table = config.get("source_table")
        source_column = config.get("source_column")
        if not source_table or not source_column:
            return []

        engine = get_engine()

        label_table = config.get("label_table")
        label_column = config.get("label_column")
        label_value_column = config.get("label_value_column")

        if label_table and label_column and label_value_column:
            sql = (
                f"SELECT DISTINCT s.{source_column} AS value, "  # noqa: S608
                f"l.{label_column} AS label "
                f"FROM {source_table} s "
                f"LEFT JOIN {label_table} l ON l.{label_value_column} = s.{source_column} "
                f"WHERE s.{source_column} IS NOT NULL "
                f"ORDER BY label, value"
            )
        else:
            sql = (
                f"SELECT DISTINCT {source_column} AS value "  # noqa: S608
                f"FROM {source_table} "
                f"WHERE {source_column} IS NOT NULL "
                f"ORDER BY value"
            )

        async with engine.begin() as conn:
            result = await conn.execute(text(sql))
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]

        for row in rows:
            if "label" not in row:
                row["label"] = str(row["value"])

        return rows

    # === Chart Columns ===

    async def _get_chart_sql(self, dc_id: int) -> str | None:
        """Get raw SQL query for a dashboard chart."""
        engine = get_engine()
        query = text(
            "SELECT c.sql_query FROM dashboard_charts dc "
            "JOIN ai_charts c ON c.id = dc.chart_id "
            "WHERE dc.id = :dc_id"
        )
        async with engine.begin() as conn:
            result = await conn.execute(query, {"dc_id": dc_id})
            row = result.fetchone()
        if not row or not row[0]:
            return None
        return row[0].rstrip().rstrip(";")

    async def get_chart_columns(self, dc_id: int) -> list[str]:
        """Get column names from a dashboard chart's SQL query by executing with LIMIT 0."""
        sql = await self._get_chart_sql(dc_id)
        if not sql:
            return []

        engine = get_engine()
        wrapped_sql = f"SELECT * FROM ({sql}) AS _cols LIMIT 0"
        async with engine.begin() as conn:
            result = await conn.execute(text(wrapped_sql))
            return list(result.keys())

    async def preview_filter(
        self,
        dc_id: int,
        target_column: str,
        operator: str = "equals",
        target_table: str | None = None,
        sample_value: str = "example_value",
    ) -> dict[str, str]:
        """Preview how a filter modifies a chart's SQL.

        Returns dict with original_sql, filtered_sql, where_clause.
        """
        from app.domain.services.chart_service import ChartService

        original_sql = await self._get_chart_sql(dc_id)
        if not original_sql:
            return {
                "original_sql": "",
                "filtered_sql": "",
                "where_clause": "",
            }

        col_ref = f"{target_table}.{target_column}" if target_table else target_column

        # Build a human-readable WHERE clause with literal values
        op_map = {
            "equals": f"{col_ref} = '{sample_value}'",
            "in": f"{col_ref} IN ('{sample_value}')",
            "between": f"{col_ref} BETWEEN '{sample_value}' AND '{sample_value}'",
            "like": f"{col_ref} LIKE '%{sample_value}%'",
            "gt": f"{col_ref} > '{sample_value}'",
            "lt": f"{col_ref} < '{sample_value}'",
            "gte": f"{col_ref} >= '{sample_value}'",
            "lte": f"{col_ref} <= '{sample_value}'",
        }
        where_clause = op_map.get(operator, f"{col_ref} = '{sample_value}'")

        # Build filtered SQL using apply_filters and then substitute params
        filters = [{
            "column": target_column,
            "operator": operator,
            "value": sample_value,
            "table": target_table,
            "param_prefix": "pv0",
        }]
        filtered_sql, _ = ChartService.apply_filters(original_sql, filters)
        # Replace bind params with literal sample values for preview
        filtered_sql = filtered_sql.replace(":pv0", f"'{sample_value}'")
        filtered_sql = filtered_sql.replace(":pv0_from", f"'{sample_value}'")
        filtered_sql = filtered_sql.replace(":pv0_to", f"'{sample_value}'")
        filtered_sql = filtered_sql.replace(":pv0_0", f"'{sample_value}'")

        return {
            "original_sql": original_sql,
            "filtered_sql": filtered_sql,
            "where_clause": where_clause,
        }

    async def get_chart_tables(self, dc_id: int) -> list[str]:
        """Extract table names from a chart's SQL (FROM/JOIN clauses)."""
        sql = await self._get_chart_sql(dc_id)
        if not sql:
            return []
        tables = _TABLE_PATTERN.findall(sql)
        # Deduplicate while preserving order
        seen: set[str] = set()
        result: list[str] = []
        for t in tables:
            lower = t.lower()
            if lower not in seen:
                seen.add(lower)
                result.append(t)
        return result
