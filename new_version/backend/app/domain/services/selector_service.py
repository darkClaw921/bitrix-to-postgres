"""Selector service: CRUD for dashboard selectors and chart mappings, filter building."""

import json as json_mod
from typing import Any

from sqlalchemy import text

from app.core.exceptions import DashboardServiceError
from app.core.logging import get_logger
from app.infrastructure.database.connection import get_dialect, get_engine

logger = get_logger(__name__)


class SelectorService:
    """Service for dashboard selector operations."""

    # === Selector CRUD ===

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
        mappings: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        engine = get_engine()
        dialect = get_dialect()

        config_json = json_mod.dumps(config, ensure_ascii=False) if config else None

        params = {
            "dashboard_id": dashboard_id,
            "name": name,
            "label": label,
            "selector_type": selector_type,
            "operator": operator,
            "config": config_json,
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

        # Create mappings if provided
        if mappings:
            for m in mappings:
                await self.add_mapping(
                    selector_id=selector_id,
                    dashboard_chart_id=m["dashboard_chart_id"],
                    target_column=m["target_column"],
                    target_table=m.get("target_table"),
                    operator_override=m.get("operator_override"),
                )

        logger.info("Selector created", id=selector_id, dashboard_id=dashboard_id, name=name)
        return await self.get_selector_by_id(selector_id)

    async def get_selector_by_id(self, selector_id: int) -> dict[str, Any]:
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
            raise DashboardServiceError(f"Селектор с id={selector_id} не найден")

        selector = dict(zip(list(result.keys()), row))

        # Parse config JSON
        if isinstance(selector.get("config"), str):
            selector["config"] = json_mod.loads(selector["config"])

        # Load mappings
        selector["mappings"] = await self._get_mappings(selector_id)
        return selector

    async def get_selectors_for_dashboard(
        self, dashboard_id: int
    ) -> list[dict[str, Any]]:
        engine = get_engine()

        query = text(
            "SELECT id, dashboard_id, name, label, selector_type, operator, "
            "config, sort_order, is_required, created_at "
            "FROM dashboard_selectors "
            "WHERE dashboard_id = :dashboard_id "
            "ORDER BY sort_order, id"
        )
        async with engine.begin() as conn:
            result = await conn.execute(query, {"dashboard_id": dashboard_id})
            columns = list(result.keys())
            selectors = [dict(zip(columns, row)) for row in result.fetchall()]

        # Parse config JSON and load mappings
        for s in selectors:
            if isinstance(s.get("config"), str):
                s["config"] = json_mod.loads(s["config"])
            s["mappings"] = await self._get_mappings(s["id"])

        return selectors

    async def update_selector(
        self,
        selector_id: int,
        **kwargs: Any,
    ) -> dict[str, Any]:
        engine = get_engine()

        updates: list[str] = []
        params: dict[str, Any] = {"id": selector_id}

        for field in ("name", "label", "selector_type", "operator", "sort_order", "is_required"):
            if field in kwargs and kwargs[field] is not None:
                updates.append(f"{field} = :{field}")
                params[field] = kwargs[field]

        if "config" in kwargs:
            updates.append("config = :config")
            params["config"] = (
                json_mod.dumps(kwargs["config"], ensure_ascii=False)
                if kwargs["config"] is not None
                else None
            )

        if not updates:
            raise DashboardServiceError("Нет полей для обновления")

        set_clause = ", ".join(updates)
        query = text(f"UPDATE dashboard_selectors SET {set_clause} WHERE id = :id")  # noqa: S608

        async with engine.begin() as conn:
            result = await conn.execute(query, params)

        if result.rowcount == 0:
            raise DashboardServiceError(f"Селектор с id={selector_id} не найден")

        logger.info("Selector updated", id=selector_id)
        return await self.get_selector_by_id(selector_id)

    async def delete_selector(self, selector_id: int) -> bool:
        engine = get_engine()
        query = text("DELETE FROM dashboard_selectors WHERE id = :id")

        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": selector_id})

        return result.rowcount > 0

    # === Mapping CRUD ===

    async def _get_mappings(self, selector_id: int) -> list[dict[str, Any]]:
        engine = get_engine()

        query = text(
            "SELECT m.id, m.selector_id, m.dashboard_chart_id, m.target_column, "
            "m.target_table, m.operator_override, m.created_at "
            "FROM selector_chart_mappings m "
            "WHERE m.selector_id = :selector_id "
            "ORDER BY m.id"
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

        logger.info(
            "Selector mapping added",
            mapping_id=mapping_id,
            selector_id=selector_id,
            dc_id=dashboard_chart_id,
        )

        # Return the created mapping
        select_q = text(
            "SELECT id, selector_id, dashboard_chart_id, target_column, "
            "target_table, operator_override, created_at "
            "FROM selector_chart_mappings WHERE id = :id"
        )
        async with engine.begin() as conn:
            res = await conn.execute(select_q, {"id": mapping_id})
            row = res.fetchone()
        if not row:
            return {"id": mapping_id, **params}
        return dict(zip(list(res.keys()), row))

    async def remove_mapping(self, mapping_id: int) -> bool:
        engine = get_engine()
        query = text("DELETE FROM selector_chart_mappings WHERE id = :id")

        async with engine.begin() as conn:
            result = await conn.execute(query, {"id": mapping_id})

        return result.rowcount > 0

    # === Filter Building ===

    async def build_filters_for_chart(
        self,
        dashboard_id: int,
        dc_id: int,
        filter_values: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Build filter dicts for ChartService.apply_filters().

        Args:
            dashboard_id: The dashboard ID
            dc_id: The dashboard_chart ID
            filter_values: Dict of selector_name -> value from the client

        Returns:
            List of filter dicts ready for apply_filters()
        """
        if not filter_values:
            return []

        selectors = await self.get_selectors_for_dashboard(dashboard_id)

        filters: list[dict[str, Any]] = []
        param_idx = 0

        for selector in selectors:
            value = filter_values.get(selector["name"])
            if value is None or value == "" or value == []:
                if selector["is_required"]:
                    raise DashboardServiceError(
                        f"Обязательный фильтр '{selector['label']}' не заполнен"
                    )
                continue

            # Find mapping for this chart
            mapping = None
            for m in selector["mappings"]:
                if m["dashboard_chart_id"] == dc_id:
                    mapping = m
                    break

            if not mapping:
                # No mapping for this chart — skip
                continue

            operator = mapping.get("operator_override") or selector["operator"]

            filters.append({
                "column": mapping["target_column"],
                "operator": operator,
                "value": value,
                "table": mapping.get("target_table"),
                "param_prefix": f"p{param_idx}",
            })
            param_idx += 1

        return filters

    # === Dropdown Options ===

    async def get_selector_options(self, selector_id: int) -> list[Any]:
        """Get dropdown options for a selector by running SELECT DISTINCT on its source."""
        selector = await self.get_selector_by_id(selector_id)
        config = selector.get("config") or {}

        # Static options
        static_options = config.get("static_options")
        if static_options:
            return static_options

        # Dynamic options from source_table/source_column
        source_table = config.get("source_table")
        source_column = config.get("source_column")

        if not source_table or not source_column:
            return []

        # Validate table/column names (alphanumeric + underscore only)
        import re
        ident_re = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

        if not ident_re.match(source_table):
            raise DashboardServiceError(f"Невалидное имя таблицы: {source_table}")
        if not ident_re.match(source_column):
            raise DashboardServiceError(f"Невалидное имя колонки: {source_column}")

        # Optional label join config
        label_table = config.get("label_table")
        label_column = config.get("label_column")
        label_value_column = config.get("label_value_column")

        use_labels = bool(label_table and label_column and label_value_column)

        if use_labels:
            if not ident_re.match(label_table):
                raise DashboardServiceError(f"Невалидное имя таблицы: {label_table}")
            if not ident_re.match(label_column):
                raise DashboardServiceError(f"Невалидное имя колонки: {label_column}")
            if not ident_re.match(label_value_column):
                raise DashboardServiceError(f"Невалидное имя колонки: {label_value_column}")

        engine = get_engine()
        dialect = get_dialect()
        cast_type = "CHAR" if dialect == "mysql" else "TEXT"

        if use_labels:
            query = text(
                f"SELECT DISTINCT s.{source_column} AS value, l.{label_column} AS label "  # noqa: S608
                f"FROM {source_table} s "
                f"LEFT JOIN {label_table} l "
                f"ON CAST(s.{source_column} AS {cast_type}) = CAST(l.{label_value_column} AS {cast_type}) "
                f"WHERE s.{source_column} IS NOT NULL "
                f"ORDER BY l.{label_column}, s.{source_column} "
                f"LIMIT 500"
            )
        else:
            query = text(
                f"SELECT DISTINCT {source_column} FROM {source_table} "  # noqa: S608
                f"WHERE {source_column} IS NOT NULL "
                f"ORDER BY {source_column} LIMIT 500"
            )

        try:
            async with engine.begin() as conn:
                result = await conn.execute(query)
                rows = result.fetchall()
            if use_labels:
                return [
                    {"value": row[0], "label": row[1] if row[1] is not None else str(row[0])}
                    for row in rows
                ]
            return [row[0] for row in rows]
        except Exception as e:
            logger.warning(
                "Failed to get selector options",
                selector_id=selector_id,
                error=str(e),
            )
            return []
