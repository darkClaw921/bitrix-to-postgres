"""Domain service for managing user-defined plan/target values (``plans`` table).

Handles CRUD, period-mode validation, factual value computation and markdown
context generation for the LLM system prompt.

Implemented on top of raw ``text()`` queries via ``get_engine().begin()``
(the same pattern as ``reference_sync_service.py``), because the target
columns/tables for plan values are dynamic and are validated against
``information_schema`` at runtime.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import text

from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.infrastructure.database.connection import get_dialect, get_engine

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PlanServiceError(AppException):
    """Base class for PlanService errors."""


class PlanValidationError(PlanServiceError):
    """Payload failed validation (bad column, bad period mode, etc)."""


class PlanConflictError(PlanServiceError):
    """Logical duplicate of an existing plan (same unique key)."""


class PlanNotFoundError(PlanServiceError):
    """Plan with the requested id does not exist."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


NUMERIC_DATA_TYPES: frozenset[str] = frozenset(
    {
        "numeric",
        "integer",
        "int",
        "bigint",
        "smallint",
        "mediumint",
        "tinyint",
        "double precision",
        "double",
        "float",
        "real",
        "decimal",
    }
)

FIXED_PERIOD_TYPES: frozenset[str] = frozenset({"month", "quarter", "year"})
ALL_PERIOD_TYPES: frozenset[str] = FIXED_PERIOD_TYPES | {"custom"}

# Default date column used by ``compute_actual`` when nothing is provided.
# ``crm_deals`` uses ``begindate``; everything else falls back to ``date_create``.
DEFAULT_DATE_COLUMNS: dict[str, str] = {
    "crm_deals": "begindate",
}
FALLBACK_DATE_COLUMN = "date_create"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class PlanService:
    """CRUD and analytics over the ``plans`` table."""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _dialect() -> str:
        return get_dialect()

    async def _column_info(
        self, table_name: str, column_name: Optional[str] = None
    ) -> list[dict[str, str]]:
        """Return ``information_schema.columns`` rows for a given table.

        If ``column_name`` is passed, filters to that single column.
        Works for both PostgreSQL and MySQL — ``information_schema`` is
        dialect-neutral for the subset we read.
        """
        engine = get_engine()
        dialect = self._dialect()

        if dialect == "postgresql":
            schema_filter = "table_schema = ANY (current_schemas(false))"
        elif dialect == "mysql":
            schema_filter = "table_schema = DATABASE()"
        else:
            schema_filter = "1=1"

        sql = (
            "SELECT column_name, data_type "
            "FROM information_schema.columns "
            f"WHERE {schema_filter} AND table_name = :tbl"
        )
        params: dict[str, Any] = {"tbl": table_name}
        if column_name is not None:
            sql += " AND column_name = :col"
            params["col"] = column_name

        async with engine.begin() as conn:
            rows = (await conn.execute(text(sql), params)).fetchall()

        return [
            {"column_name": r[0], "data_type": (r[1] or "").lower()}
            for r in rows
        ]

    async def _validate_numeric_column(
        self, table_name: str, field_name: str
    ) -> None:
        """Ensure ``table_name.field_name`` exists and has a numeric data_type."""
        if not table_name or not field_name:
            raise PlanValidationError("table_name and field_name are required")

        columns = await self._column_info(table_name, field_name)
        if not columns:
            raise PlanValidationError(
                f"Column {table_name}.{field_name} does not exist"
            )
        data_type = columns[0]["data_type"]
        if data_type not in NUMERIC_DATA_TYPES:
            raise PlanValidationError(
                f"Column {table_name}.{field_name} has non-numeric type "
                f"'{data_type}'; plan values are supported only for numeric columns"
            )

    @staticmethod
    def _validate_period(payload: dict[str, Any]) -> None:
        """Ensure exactly one of {fixed, custom} period mode is provided.

        Fixed:  period_type in {month, quarter, year} + period_value.
        Custom: period_type == 'custom' + date_from + date_to.
        """
        period_type = payload.get("period_type")
        period_value = payload.get("period_value")
        date_from = payload.get("date_from")
        date_to = payload.get("date_to")

        if period_type is None:
            raise PlanValidationError("period_type is required")
        if period_type not in ALL_PERIOD_TYPES:
            raise PlanValidationError(
                f"period_type must be one of {sorted(ALL_PERIOD_TYPES)}, "
                f"got '{period_type}'"
            )

        if period_type in FIXED_PERIOD_TYPES:
            if not period_value:
                raise PlanValidationError(
                    f"period_value is required for period_type='{period_type}'"
                )
            if date_from or date_to:
                raise PlanValidationError(
                    "date_from/date_to must be NULL for fixed period_type "
                    f"'{period_type}'"
                )
        else:  # custom
            if not date_from or not date_to:
                raise PlanValidationError(
                    "date_from and date_to are required for period_type='custom'"
                )
            if period_value:
                raise PlanValidationError(
                    "period_value must be NULL for period_type='custom'"
                )

    async def _find_duplicate(
        self, payload: dict[str, Any], exclude_id: Optional[int] = None
    ) -> Optional[int]:
        """Return id of a logically identical plan, if any."""
        engine = get_engine()

        # Use IS NOT DISTINCT FROM semantics manually — it works in both
        # dialects when expressed as ``(a = b OR (a IS NULL AND b IS NULL))``.
        clauses = [
            "table_name = :table_name",
            "field_name = :field_name",
            "((assigned_by_id = :assigned_by_id) OR "
            " (assigned_by_id IS NULL AND :assigned_by_id IS NULL))",
            "((period_type = :period_type) OR "
            " (period_type IS NULL AND :period_type IS NULL))",
            "((period_value = :period_value) OR "
            " (period_value IS NULL AND :period_value IS NULL))",
            "((date_from = :date_from) OR "
            " (date_from IS NULL AND :date_from IS NULL))",
            "((date_to = :date_to) OR "
            " (date_to IS NULL AND :date_to IS NULL))",
        ]
        params: dict[str, Any] = {
            "table_name": payload["table_name"],
            "field_name": payload["field_name"],
            "assigned_by_id": payload.get("assigned_by_id"),
            "period_type": payload.get("period_type"),
            "period_value": payload.get("period_value"),
            "date_from": payload.get("date_from"),
            "date_to": payload.get("date_to"),
        }
        if exclude_id is not None:
            clauses.append("id <> :exclude_id")
            params["exclude_id"] = exclude_id

        sql = f"SELECT id FROM plans WHERE {' AND '.join(clauses)} LIMIT 1"

        async with engine.begin() as conn:
            row = (await conn.execute(text(sql), params)).first()
        return int(row[0]) if row else None

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        """Convert a SQLAlchemy Row into a plain dict."""
        mapping = getattr(row, "_mapping", None)
        if mapping is None:
            return dict(row)
        return {k: v for k, v in mapping.items()}

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a new plan row.

        Validates the referenced numeric column via information_schema,
        validates the period-mode, checks for a logical duplicate, and
        inserts the record. Returns the freshly created row as a dict.
        """
        table_name = payload.get("table_name")
        field_name = payload.get("field_name")
        plan_value = payload.get("plan_value")

        if plan_value is None:
            raise PlanValidationError("plan_value is required")

        await self._validate_numeric_column(table_name, field_name)
        self._validate_period(payload)

        existing_id = await self._find_duplicate(payload)
        if existing_id is not None:
            raise PlanConflictError(
                f"Plan with the same logical key already exists (id={existing_id})"
            )

        engine = get_engine()
        dialect = self._dialect()

        insert_cols = [
            "table_name",
            "field_name",
            "assigned_by_id",
            "period_type",
            "period_value",
            "date_from",
            "date_to",
            "plan_value",
            "description",
            "created_by_id",
        ]
        placeholders = ", ".join(f":{c}" for c in insert_cols)
        col_list = ", ".join(insert_cols)

        params: dict[str, Any] = {
            "table_name": table_name,
            "field_name": field_name,
            "assigned_by_id": payload.get("assigned_by_id"),
            "period_type": payload.get("period_type"),
            "period_value": payload.get("period_value"),
            "date_from": payload.get("date_from"),
            "date_to": payload.get("date_to"),
            "plan_value": plan_value,
            "description": payload.get("description"),
            "created_by_id": payload.get("created_by_id"),
        }

        async with engine.begin() as conn:
            if dialect == "postgresql":
                sql = (
                    f"INSERT INTO plans ({col_list}) VALUES ({placeholders}) "
                    f"RETURNING id"
                )
                result = await conn.execute(text(sql), params)
                new_id = int(result.scalar())
            else:  # mysql / mariadb
                sql = f"INSERT INTO plans ({col_list}) VALUES ({placeholders})"
                result = await conn.execute(text(sql), params)
                new_id = int(result.lastrowid)

        logger.info(
            "Plan created",
            plan_id=new_id,
            table_name=table_name,
            field_name=field_name,
            period_type=payload.get("period_type"),
        )

        created = await self.get_plan(new_id)
        if created is None:
            raise PlanServiceError(
                f"Plan {new_id} was created but could not be re-read"
            )
        return created

    async def list_plans(
        self, filters: Optional[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        """Return plans filtered by an optional set of columns."""
        filters = filters or {}
        allowed = {"table_name", "field_name", "assigned_by_id", "period_type"}

        where_parts: list[str] = []
        params: dict[str, Any] = {}
        for key, value in filters.items():
            if key not in allowed or value is None:
                continue
            where_parts.append(f"{key} = :{key}")
            params[key] = value

        sql = "SELECT * FROM plans"
        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)
        sql += " ORDER BY id DESC"

        engine = get_engine()
        async with engine.begin() as conn:
            rows = (await conn.execute(text(sql), params)).fetchall()
        return [self._row_to_dict(r) for r in rows]

    async def get_plan(self, plan_id: int) -> Optional[dict[str, Any]]:
        """Return a single plan by id, or ``None`` if not found."""
        engine = get_engine()
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text("SELECT * FROM plans WHERE id = :id"),
                    {"id": plan_id},
                )
            ).first()
        return self._row_to_dict(row) if row else None

    async def update_plan(
        self, plan_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing plan.

        Supports two modes:

        * **Partial update** — if the payload contains only ``plan_value``
          and/or ``description``, only those columns are updated (the logical
          key stays intact).
        * **Full update** — if the payload also contains any key field
          (``table_name``, ``field_name``, ``assigned_by_id``, ``period_type``,
          ``period_value``, ``date_from``, ``date_to``), the record is fully
          re-validated (numeric column + period mode + duplicate check
          excluding ``plan_id``) and rewritten.
        """
        existing = await self.get_plan(plan_id)
        if existing is None:
            raise PlanNotFoundError(f"Plan {plan_id} not found")

        key_fields = {
            "table_name",
            "field_name",
            "assigned_by_id",
            "period_type",
            "period_value",
            "date_from",
            "date_to",
        }
        touches_key = any(k in payload for k in key_fields)

        engine = get_engine()

        if touches_key:
            # Full update — merge payload on top of the existing row, then
            # re-run all create-level validations.
            merged: dict[str, Any] = dict(existing)
            for k in (
                "table_name",
                "field_name",
                "assigned_by_id",
                "period_type",
                "period_value",
                "date_from",
                "date_to",
                "plan_value",
                "description",
            ):
                if k in payload:
                    merged[k] = payload[k]

            if merged.get("plan_value") is None:
                raise PlanValidationError("plan_value is required")

            await self._validate_numeric_column(
                merged["table_name"], merged["field_name"]
            )
            self._validate_period(merged)

            duplicate_id = await self._find_duplicate(merged, exclude_id=plan_id)
            if duplicate_id is not None:
                raise PlanConflictError(
                    f"Plan with the same logical key already exists "
                    f"(id={duplicate_id})"
                )

            sql = (
                "UPDATE plans SET "
                "table_name = :table_name, "
                "field_name = :field_name, "
                "assigned_by_id = :assigned_by_id, "
                "period_type = :period_type, "
                "period_value = :period_value, "
                "date_from = :date_from, "
                "date_to = :date_to, "
                "plan_value = :plan_value, "
                "description = :description, "
                "updated_at = NOW() "
                "WHERE id = :id"
            )
            params = {
                "id": plan_id,
                "table_name": merged["table_name"],
                "field_name": merged["field_name"],
                "assigned_by_id": merged.get("assigned_by_id"),
                "period_type": merged.get("period_type"),
                "period_value": merged.get("period_value"),
                "date_from": merged.get("date_from"),
                "date_to": merged.get("date_to"),
                "plan_value": merged["plan_value"],
                "description": merged.get("description"),
            }

            async with engine.begin() as conn:
                await conn.execute(text(sql), params)

            logger.info("Plan fully updated", plan_id=plan_id)
        else:
            # Partial update — mutate only plan_value / description.
            updates: dict[str, Any] = {}
            if "plan_value" in payload and payload["plan_value"] is not None:
                updates["plan_value"] = payload["plan_value"]
            if "description" in payload:
                updates["description"] = payload["description"]

            if not updates:
                return existing

            set_parts = [f"{col} = :{col}" for col in updates]
            set_parts.append("updated_at = NOW()")
            params = dict(updates)
            params["id"] = plan_id

            sql = f"UPDATE plans SET {', '.join(set_parts)} WHERE id = :id"

            async with engine.begin() as conn:
                await conn.execute(text(sql), params)

            logger.info(
                "Plan updated", plan_id=plan_id, fields=list(updates.keys())
            )

        updated = await self.get_plan(plan_id)
        if updated is None:
            raise PlanServiceError(
                f"Plan {plan_id} was updated but could not be re-read"
            )
        return updated

    async def delete_plan(self, plan_id: int) -> bool:
        """Delete a plan. Returns True on success, False if not found."""
        engine = get_engine()
        async with engine.begin() as conn:
            result = await conn.execute(
                text("DELETE FROM plans WHERE id = :id"),
                {"id": plan_id},
            )
            deleted = (result.rowcount or 0) > 0

        if deleted:
            logger.info("Plan deleted", plan_id=plan_id)
        return deleted

    # ------------------------------------------------------------------
    # Analytics — actual value + plan vs actual
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_date_column(table_name: str) -> str:
        """Return the default date column to use for ``compute_actual``.

        ``crm_deals`` uses ``begindate``, everything else falls back to
        ``date_create`` — the same convention as ``date_tokens`` / the rest
        of the codebase.
        """
        return DEFAULT_DATE_COLUMNS.get(table_name, FALLBACK_DATE_COLUMN)

    async def _assert_column_exists(
        self, table_name: str, column_name: str
    ) -> None:
        """Verify a column exists against ``information_schema``.

        Used as an anti-SQL-injection whitelist step before interpolating
        identifiers into a raw query. Raises ``PlanValidationError`` on
        missing columns.
        """
        columns = await self._column_info(table_name, column_name)
        if not columns:
            raise PlanValidationError(
                f"Column {table_name}.{column_name} does not exist"
            )

    async def compute_actual(
        self,
        table_name: str,
        field_name: str,
        assigned_by_id: Optional[str],
        date_from: date,
        date_to: date,
        date_column: Optional[str] = None,
    ) -> Decimal:
        """Return ``COALESCE(SUM(field_name), 0)`` over ``[date_from, date_to)``.

        All identifiers (``table_name``, ``field_name``, ``date_column``) are
        whitelisted against ``information_schema`` before being interpolated —
        this keeps the query SQL-injection-safe even though they cannot be
        passed as bind params.
        """
        if date_column is None:
            date_column = self._resolve_date_column(table_name)

        # Whitelist every identifier we interpolate.
        await self._validate_numeric_column(table_name, field_name)
        await self._assert_column_exists(table_name, date_column)

        dialect = self._dialect()
        if dialect == "postgresql":
            ident_l, ident_r = '"', '"'
        else:
            ident_l, ident_r = "`", "`"

        tbl = f"{ident_l}{table_name}{ident_r}"
        fld = f"{ident_l}{field_name}{ident_r}"
        dcol = f"{ident_l}{date_column}{ident_r}"

        where_parts = [f"{dcol} >= :d_from", f"{dcol} < :d_to"]
        params: dict[str, Any] = {"d_from": date_from, "d_to": date_to}
        if assigned_by_id is not None:
            where_parts.append(
                f"{ident_l}assigned_by_id{ident_r} = :assigned_by_id"
            )
            params["assigned_by_id"] = assigned_by_id

        sql = (
            f"SELECT COALESCE(SUM({fld}), 0) AS actual "
            f"FROM {tbl} "
            f"WHERE {' AND '.join(where_parts)}"
        )

        engine = get_engine()
        async with engine.begin() as conn:
            value = (await conn.execute(text(sql), params)).scalar()

        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    @staticmethod
    def _resolve_period_bounds(
        period_type: Optional[str],
        period_value: Optional[str],
        date_from: Optional[date],
        date_to: Optional[date],
    ) -> tuple[date, date]:
        """Convert a plan's period fields to a concrete ``[from, to)`` range.

        * ``month``: ``2026-04`` → ``2026-04-01`` .. ``2026-05-01``
        * ``quarter``: ``2026-Q2`` → ``2026-04-01`` .. ``2026-07-01``
        * ``year``: ``2026`` → ``2026-01-01`` .. ``2027-01-01``
        * ``custom``: returned as-is (``date_to`` is treated as exclusive
                       by convention of this method; the endpoint/caller is
                       responsible for aligning the semantics).
        """
        if period_type == "month":
            if not period_value:
                raise PlanValidationError("period_value is required for month")
            year_s, month_s = period_value.split("-", 1)
            year, month = int(year_s), int(month_s)
            start = date(year, month, 1)
            if month == 12:
                end = date(year + 1, 1, 1)
            else:
                end = date(year, month + 1, 1)
            return start, end

        if period_type == "quarter":
            if not period_value:
                raise PlanValidationError("period_value is required for quarter")
            year_s, q_s = period_value.split("-Q", 1)
            year, q = int(year_s), int(q_s)
            if q < 1 or q > 4:
                raise PlanValidationError(f"Invalid quarter number: {q}")
            start_month = (q - 1) * 3 + 1
            start = date(year, start_month, 1)
            if q == 4:
                end = date(year + 1, 1, 1)
            else:
                end = date(year, start_month + 3, 1)
            return start, end

        if period_type == "year":
            if not period_value:
                raise PlanValidationError("period_value is required for year")
            year = int(period_value)
            return date(year, 1, 1), date(year + 1, 1, 1)

        if period_type == "custom":
            if not date_from or not date_to:
                raise PlanValidationError(
                    "date_from and date_to are required for custom period"
                )
            return date_from, date_to

        raise PlanValidationError(f"Unknown period_type: {period_type}")

    async def get_plan_vs_actual(self, plan_id: int) -> dict[str, Any]:
        """Return plan/actual/variance snapshot for a single plan.

        Shape:
            {
              "plan_id": int,
              "plan_value": Decimal,
              "actual_value": Decimal,
              "variance": Decimal,          # actual - plan
              "variance_pct": float | None, # None when plan_value == 0
              "date_from": date,
              "date_to": date,
            }
        """
        plan = await self.get_plan(plan_id)
        if plan is None:
            raise PlanNotFoundError(f"Plan {plan_id} not found")

        period_from, period_to = self._resolve_period_bounds(
            plan.get("period_type"),
            plan.get("period_value"),
            plan.get("date_from"),
            plan.get("date_to"),
        )

        actual = await self.compute_actual(
            table_name=plan["table_name"],
            field_name=plan["field_name"],
            assigned_by_id=plan.get("assigned_by_id"),
            date_from=period_from,
            date_to=period_to,
        )

        plan_value = plan["plan_value"]
        if not isinstance(plan_value, Decimal):
            plan_value = Decimal(str(plan_value))

        variance = actual - plan_value
        variance_pct: Optional[float]
        if plan_value == 0:
            variance_pct = None
        else:
            variance_pct = float((actual / plan_value - 1) * 100)

        return {
            "plan_id": plan_id,
            "plan_value": plan_value,
            "actual_value": actual,
            "variance": variance,
            "variance_pct": variance_pct,
            "date_from": period_from,
            "date_to": period_to,
        }

    # ------------------------------------------------------------------
    # LLM context
    # ------------------------------------------------------------------

    # Static markdown block injected into the system prompt of AIService.
    _LLM_STATIC_TEMPLATE = (
        "## Таблица планов (plans) — для отчётов «план vs факт»\n"
        "В БД есть таблица `plans` с пользовательскими плановыми значениями.\n"
        "Колонки: id, table_name, field_name, assigned_by_id (nullable — NULL = общий план на всех),\n"
        "period_type ('month'|'quarter'|'year'|'custom'), period_value, date_from, date_to,\n"
        "plan_value, description, created_at, updated_at.\n"
        "\n"
        "### Как выбрать нужный план\n"
        "План может быть поставлен на **ЛЮБОЕ числовое поле ЛЮБОЙ таблицы** — это может быть\n"
        "`crm_deals.opportunity`, количество сделок, количество звонков, сумма по кастомному полю и\n"
        "т.п. НЕ хардкодь `crm_deals.opportunity` — всегда бери `table_name` и `field_name` из\n"
        "конкретной строки таблицы `plans`, которую собираешься использовать.\n"
        "\n"
        "Если пользователь не указал явно, какой план использовать (по какой таблице/полю/периоду/\n"
        "менеджеру), **ВСЕГДА бери самый свежий план** — это строка с максимальным `id`\n"
        "(эквивалентно максимальному `created_at`). Ниже в разделе «Активные планы» они уже\n"
        "перечислены в порядке от самого нового к самому старому — первая строка списка и есть\n"
        "план по умолчанию.\n"
        "\n"
        "После того, как ты определил план, ВСЕ части SQL (FROM, WHERE по дате, SUM по полю)\n"
        "должны строиться именно под его `table_name` / `field_name` / период / `assigned_by_id`.\n"
        "Если самый новый план, например, по `crm_calls.duration` — факт считается как\n"
        "`SUM(crm_calls.duration)`, а не `SUM(crm_deals.opportunity)`.\n"
        "\n"
        "### Жёсткие правила построения SQL для «план/факт»:\n"
        "1. НЕ добавляй фильтры `closed`, `stage_semantic_id`, статусы и т.п., если пользователь\n"
        "   их явно не попросил. План/факт сравнивает ВСЕ записи за период, а не только выигранные\n"
        "   сделки.\n"
        "2. Bitrix-поле `closed` содержит строки `'Y'`/`'N'` (НЕ `'1'`/`'0'`).\n"
        "   `stage_semantic_id`: `'P'` = в процессе, `'S'` = успешно (выигранные), `'F'` = провал.\n"
        "3. ВСЕГДА фильтруй факт по периоду плана через WHERE на столбец даты основной таблицы:\n"
        "   - для `crm_deals` используй `begindate` (по умолчанию);\n"
        "   - для остальных таблиц — `date_create`.\n"
        "   Границы периода вычисляй сам из `period_type`/`period_value` (fixed) или бери\n"
        "   `date_from`/`date_to` напрямую (custom). Интервал полузакрытый: `>= from AND < to`.\n"
        "4. Для общего плана (`assigned_by_id IS NULL`) НЕ дублируй его на каждого менеджера\n"
        "   через `OR p.assigned_by_id IS NULL` — это приведёт к тому, что общее плановое значение\n"
        "   навесится на каждую строку группировки. Либо строй отчёт БЕЗ группировки по менеджерам\n"
        "   (одна строка «Всего»), либо выводи общий план отдельной строкой через UNION ALL.\n"
        "5. НИКОГДА не джойнь `bitrix_users` как источник строк результата — менеджеры, у которых\n"
        "   нет ни записей за период, ни персонального плана, не должны появляться в отчёте.\n"
        "   Строй строки ОТ основной таблицы (через `assigned_by_id` из записей за период) и\n"
        "   LEFT JOIN `bitrix_users` только ради получения имён.\n"
        "6. Используй агрегат, соответствующий смыслу поля: `SUM` для сумм, `COUNT(*)` если план\n"
        "   выставлен на количество записей, `AVG` — для средних. По умолчанию `SUM(field_name)`.\n"
        "\n"
        "### Канонический пример (персональный план по месяцу, опора на plans):\n"
        "Предположим, самый свежий план в списке:\n"
        "`table_name='crm_deals', field_name='opportunity', assigned_by_id='16',\n"
        " period_type='month', period_value='2026-04', plan_value=20000`.\n"
        "Тогда SQL:\n"
        "```sql\n"
        "SELECT\n"
        "  CONCAT(COALESCE(u.name,''),' ',COALESCE(u.last_name,'')) AS manager,\n"
        "  COALESCE(SUM(d.opportunity), 0) AS actual,\n"
        "  MAX(p.plan_value)               AS plan\n"
        "FROM crm_deals d\n"
        "LEFT JOIN bitrix_users u ON u.bitrix_id = d.assigned_by_id\n"
        "LEFT JOIN plans p\n"
        "  ON p.table_name = 'crm_deals'\n"
        " AND p.field_name = 'opportunity'\n"
        " AND p.assigned_by_id = d.assigned_by_id\n"
        " AND p.period_type = 'month' AND p.period_value = '2026-04'\n"
        "WHERE d.assigned_by_id = '16'\n"
        "  AND d.begindate >= '2026-04-01' AND d.begindate < '2026-05-01'\n"
        "GROUP BY d.assigned_by_id, u.name, u.last_name;\n"
        "```\n"
        "Обрати внимание: имя поля в `SUM(d.opportunity)` и имя таблицы в `FROM crm_deals d`\n"
        "взяты ИЗ ПЛАНА, а не захардкожены.\n"
        "\n"
        "### Канонический пример (общий custom-период, план на количество звонков):\n"
        "Предположим, свежий план: `table_name='bitrix_calls', field_name='id', assigned_by_id=NULL,\n"
        " period_type='custom', date_from='2026-01-01', date_to='2026-04-10', plan_value=500`\n"
        "(план на количество звонков → используем COUNT).\n"
        "```sql\n"
        "SELECT\n"
        "  COUNT(*) AS actual,\n"
        "  (SELECT plan_value FROM plans\n"
        "     WHERE table_name='bitrix_calls' AND field_name='id'\n"
        "       AND assigned_by_id IS NULL AND period_type='custom'\n"
        "       AND date_from='2026-01-01' AND date_to='2026-04-10') AS plan\n"
        "FROM bitrix_calls c\n"
        "WHERE c.date_create >= '2026-01-01' AND c.date_create < '2026-04-10';\n"
        "```"
    )

    # Max number of plans embedded into the system prompt as a concrete
    # "pick-me" list. Kept small to avoid blowing up the prompt size; the
    # LLM only needs enough context to identify the most recent plan and
    # a handful of alternatives.
    _LLM_PLAN_LIST_LIMIT = 20

    async def get_plans_llm_context(self) -> str:
        """Return a markdown block describing the ``plans`` table for the LLM.

        Appends a concrete list of currently saved plans sorted from newest
        to oldest so the model can:

        * identify *which* (table, field) pairs actually have a plan attached;
        * pick the most recent plan as the default when the user didn't
          specify one explicitly.

        On an empty ``plans`` table only the static template is returned.
        """
        engine = get_engine()
        try:
            async with engine.begin() as conn:
                rows = (
                    await conn.execute(
                        text(
                            "SELECT id, table_name, field_name, assigned_by_id, "
                            "       period_type, period_value, date_from, date_to, "
                            "       plan_value, created_at "
                            "FROM plans "
                            "ORDER BY id DESC "
                            f"LIMIT {int(self._LLM_PLAN_LIST_LIMIT)}"
                        )
                    )
                ).fetchall()
        except Exception as exc:  # pragma: no cover — best-effort for LLM prompt
            logger.warning(
                "get_plans_llm_context: failed to read plans list",
                error=str(exc),
            )
            return self._LLM_STATIC_TEMPLATE

        if not rows:
            return self._LLM_STATIC_TEMPLATE

        def _fmt_period(
            period_type: Optional[str],
            period_value: Optional[str],
            date_from: Any,
            date_to: Any,
        ) -> str:
            if period_type == "custom":
                return f"custom {date_from}..{date_to}"
            return f"{period_type}={period_value}"

        lines: list[str] = [
            "",
            "",
            "### Активные планы (от самого нового к самому старому)",
            (
                "Первая строка — план по умолчанию, если пользователь не указал "
                "явно, какой план использовать."
            ),
            "",
            "| id | table | field | assigned_by_id | period | plan_value | created_at |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in rows:
            (
                plan_id,
                table_name,
                field_name,
                assigned_by_id,
                period_type,
                period_value,
                date_from,
                date_to,
                plan_value,
                created_at,
            ) = r
            assigned_str = assigned_by_id if assigned_by_id is not None else "NULL (все)"
            period_str = _fmt_period(period_type, period_value, date_from, date_to)
            lines.append(
                f"| {plan_id} | {table_name} | {field_name} | {assigned_str} | "
                f"{period_str} | {plan_value} | {created_at} |"
            )

        return self._LLM_STATIC_TEMPLATE + "\n".join(lines)
