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
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import bindparam, text

from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.infrastructure.database.connection import get_dialect, get_engine

if TYPE_CHECKING:
    from app.api.v1.schemas.charts import PlanFactConfig

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
# All tables fall back to ``date_create`` — план/факт считается по дате создания.
DEFAULT_DATE_COLUMNS: dict[str, str] = {}
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

    # ------------------------------------------------------------------
    # Internal INSERT helper (shared by single- and batch-create)
    # ------------------------------------------------------------------

    _INSERT_COLS: list[str] = [
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

    async def _insert_plan_in_conn(
        self,
        conn: Any,
        payload: dict[str, Any],
    ) -> int:
        """Insert one plan row using the given live connection.

        Assumes validations already passed (numeric column check +
        period-mode check + duplicate check for that payload). Returns
        the freshly inserted id.

        Shared by :meth:`create_plan` (wraps it in a single ``begin()``)
        and :meth:`batch_create_plans` (wraps many calls in one
        transaction — any failure rolls back all inserts).
        """
        dialect = self._dialect()
        col_list = ", ".join(self._INSERT_COLS)
        placeholders = ", ".join(f":{c}" for c in self._INSERT_COLS)

        params: dict[str, Any] = {
            "table_name": payload["table_name"],
            "field_name": payload["field_name"],
            "assigned_by_id": payload.get("assigned_by_id"),
            "period_type": payload.get("period_type"),
            "period_value": payload.get("period_value"),
            "date_from": payload.get("date_from"),
            "date_to": payload.get("date_to"),
            "plan_value": payload["plan_value"],
            "description": payload.get("description"),
            "created_by_id": payload.get("created_by_id"),
        }

        if dialect == "postgresql":
            sql = (
                f"INSERT INTO plans ({col_list}) VALUES ({placeholders}) "
                f"RETURNING id"
            )
            result = await conn.execute(text(sql), params)
            return int(result.scalar())
        # mysql / mariadb
        sql = f"INSERT INTO plans ({col_list}) VALUES ({placeholders})"
        result = await conn.execute(text(sql), params)
        return int(result.lastrowid)

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
        async with engine.begin() as conn:
            new_id = await self._insert_plan_in_conn(conn, payload)

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

    async def batch_create_plans(
        self,
        plans: list[dict[str, Any]],
        created_by_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Create many plan rows in a single transaction.

        All-or-nothing semantics: any validation error, logical duplicate,
        or DB-level IntegrityError rolls back the whole batch — no plan
        is partially created. Each plan goes through the same validation
        chain as :meth:`create_plan` (numeric column + period mode +
        logical-duplicate check), so the batch endpoint can not be used
        to bypass business rules.

        Args:
            plans: Each dict has the same shape as the payload of
                :meth:`create_plan`.
            created_by_id: If provided, overrides/fills in
                ``created_by_id`` on every plan (typically pulled from
                the JWT of the authenticated user).

        Returns:
            List of freshly-inserted plan rows in the same order as the
            input. Re-read via :meth:`get_plan` for consistent shape
            (timestamps, etc).

        Raises:
            PlanValidationError: Bad column/period/etc for some entry.
            PlanConflictError: Logical duplicate of an existing plan,
                OR logical duplicate inside the batch itself (two
                payloads collide on the unique key).
            PlanServiceError: Any other unexpected failure.
        """
        if not plans:
            return []

        engine = get_engine()
        created_ids: list[int] = []

        # Pre-validate everything outside the DB transaction to fail
        # fast with the most helpful error (and to surface logical dup
        # conflicts inside the batch itself).
        seen_keys: set[tuple[Any, ...]] = set()
        resolved_payloads: list[dict[str, Any]] = []

        for idx, raw in enumerate(plans):
            # Shallow copy + apply created_by_id override.
            payload = dict(raw)
            if created_by_id is not None:
                payload["created_by_id"] = created_by_id

            if payload.get("plan_value") is None:
                raise PlanValidationError(
                    f"plan_value is required (entry #{idx})"
                )

            table_name = payload.get("table_name")
            field_name = payload.get("field_name")
            await self._validate_numeric_column(table_name, field_name)
            self._validate_period(payload)

            # Intra-batch duplicate check (DB unique constraint would
            # surface later but as an opaque IntegrityError).
            key = (
                payload.get("table_name"),
                payload.get("field_name"),
                payload.get("assigned_by_id"),
                payload.get("period_type"),
                payload.get("period_value"),
                payload.get("date_from"),
                payload.get("date_to"),
            )
            if key in seen_keys:
                raise PlanConflictError(
                    f"Duplicate plan inside batch (entry #{idx}): {key}"
                )
            seen_keys.add(key)

            # Cross-batch vs existing-DB duplicate.
            existing_id = await self._find_duplicate(payload)
            if existing_id is not None:
                raise PlanConflictError(
                    f"Plan with the same logical key already exists "
                    f"(id={existing_id}, entry #{idx})"
                )

            resolved_payloads.append(payload)

        async with engine.begin() as conn:
            for payload in resolved_payloads:
                new_id = await self._insert_plan_in_conn(conn, payload)
                created_ids.append(new_id)

        logger.info(
            "Plans batch-created",
            count=len(created_ids),
            plan_ids=created_ids,
        )

        created_rows: list[dict[str, Any]] = []
        for pid in created_ids:
            row = await self.get_plan(pid)
            if row is None:
                raise PlanServiceError(
                    f"Plan {pid} was created but could not be re-read"
                )
            created_rows.append(row)
        return created_rows

    async def list_plans(
        self, filters: Optional[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        """Return plans filtered by an optional set of columns.

        ``assigned_by_ids`` (list[str]) uses IN clause; all other keys use
        equality.  Unknown keys are silently ignored.
        """
        filters = filters or {}
        scalar_allowed = {"table_name", "field_name", "assigned_by_id", "period_type", "period_value"}

        where_parts: list[str] = []
        params: dict[str, Any] = {}
        use_in_manager = False

        assigned_by_ids = filters.get("assigned_by_ids")
        if assigned_by_ids and isinstance(assigned_by_ids, list) and len(assigned_by_ids) > 0:
            where_parts.append("assigned_by_id IN :assigned_by_ids")
            params["assigned_by_ids"] = assigned_by_ids
            use_in_manager = True

        for key, value in filters.items():
            if key == "assigned_by_ids" or key not in scalar_allowed or value is None:
                continue
            where_parts.append(f"{key} = :{key}")
            params[key] = value

        sql = "SELECT * FROM plans"
        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)
        sql += " ORDER BY id DESC"

        engine = get_engine()
        async with engine.begin() as conn:
            if use_in_manager:
                stmt = text(sql).bindparams(bindparam("assigned_by_ids", expanding=True))
                rows = (await conn.execute(stmt, params)).fetchall()
            else:
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

        Always returns ``date_create`` — план/факт считается по дате
        создания записи (включая crm_deals).
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

    # ------------------------------------------------------------------
    # Post-enrichment helpers (plan/fact without JOIN)
    # ------------------------------------------------------------------

    @staticmethod
    def _norm_group_key(value: Any) -> str:
        """Normalize a group key to a string for dict lookups.

        Group keys coming from fact rows may be ``int`` (e.g. ``assigned_by_id``
        stored as BIGINT) while the ``plans.assigned_by_id`` column is ``TEXT``.
        To compare them reliably we always coerce to ``str``. ``None`` becomes
        an empty string (effectively meaning "no group").
        """
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def _coerce_date(value: Any) -> Optional[date]:
        """Try to coerce ``value`` into a ``date`` object.

        Accepts ``date``, ``datetime`` and ISO-format strings (``YYYY-MM-DD``
        or full ISO datetime). Returns ``None`` for unparseable input so the
        caller can safely skip malformed filter values without blowing up.
        """
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            # Accept both bare date and full datetime prefixes.
            try:
                return date.fromisoformat(s[:10])
            except ValueError:
                try:
                    return datetime.fromisoformat(s).date()
                except ValueError:
                    return None
        return None

    @classmethod
    def _extract_selector_signals(
        cls,
        resolved_filters: Optional[list[dict[str, Any]]],
    ) -> tuple[Optional[list[str]], Optional[tuple[date, date]]]:
        """Extract ``(assigned_ids, date_range)`` from resolved dashboard filters.

        ``resolved_filters`` is the list returned by
        ``SelectorService.build_filters_for_chart``: every element is a dict
        with keys ``column``, ``operator``, ``value``, ``table``,
        ``param_prefix`` and optionally ``post_filter``. Values are already
        passed through ``date_tokens.resolve_filter_value`` — we do not
        re-resolve anything here.

        Signals:
        1) Filter by managers — first element whose ``column == 'assigned_by_id'``.
           ``value`` may be a scalar (``operator == 'eq'``) or a list
           (``operator == 'in'``). Returned as ``list[str]`` (ids coerced to
           str so they match ``plans.assigned_by_id``). Returns ``None`` when
           no such filter is present (i.e. "no manager filter applied").
        2) Date range — first element with ``operator == 'between'`` whose
           ``value`` contains ``from``/``to`` keys. Returned as
           ``tuple[date, date]``. Returns ``None`` when no date filter exists
           (i.e. "entire time range").

        Returns ``(None, None)`` for an empty/``None`` input.
        """
        if not resolved_filters:
            return None, None

        assigned_ids: Optional[list[str]] = None
        date_range: Optional[tuple[date, date]] = None

        for flt in resolved_filters:
            if not isinstance(flt, dict):
                continue

            column = flt.get("column")
            operator = (flt.get("operator") or "").lower()
            value = flt.get("value")

            # Managers filter: match by target column name.
            if assigned_ids is None and column == "assigned_by_id":
                if isinstance(value, (list, tuple, set)):
                    assigned_ids = [str(v) for v in value if v is not None]
                elif value is not None:
                    assigned_ids = [str(value)]
                # Do not `continue` — one filter could theoretically be both
                # a between (unlikely) but we still want to scan the rest.

            # Date range filter: match by operator. We pick the first
            # between-filter we see — scenario #6 in the edge-cases task.
            if date_range is None and operator == "between":
                range_from: Optional[date] = None
                range_to: Optional[date] = None
                if isinstance(value, dict):
                    range_from = cls._coerce_date(value.get("from"))
                    range_to = cls._coerce_date(value.get("to"))
                elif isinstance(value, (list, tuple)) and len(value) == 2:
                    range_from = cls._coerce_date(value[0])
                    range_to = cls._coerce_date(value[1])
                if range_from is not None and range_to is not None:
                    date_range = (range_from, range_to)

        return assigned_ids, date_range

    @classmethod
    def _period_intersects(
        cls,
        plan_row: dict[str, Any],
        range_from: Optional[date],
        range_to: Optional[date],
    ) -> bool:
        """Return True iff the plan's effective period intersects the range.

        The effective plan period is resolved via the existing
        ``_resolve_period_bounds`` (``[plan_from, plan_to)`` half-open). The
        dashboard selector range is also treated as half-open
        ``[range_from, range_to)``. Two half-open intervals intersect iff
        ``plan_from < range_to AND plan_to > range_from``.

        When both ``range_from`` and ``range_to`` are ``None`` the caller
        expressed "entire time range" — every plan passes.

        Malformed plan rows (bad ``period_value`` / missing ``date_from`` for
        custom, etc.) are handled gracefully: a warning is logged and the
        plan is skipped (scenario #4 in the edge-cases task).
        """
        if range_from is None and range_to is None:
            return True

        try:
            plan_from, plan_to = cls._resolve_period_bounds(
                plan_row.get("period_type"),
                plan_row.get("period_value"),
                plan_row.get("date_from"),
                plan_row.get("date_to"),
            )
        except Exception as exc:
            logger.warning(
                "plan_enrich: failed to resolve plan period — skipping",
                plan_id=plan_row.get("id"),
                period_type=plan_row.get("period_type"),
                period_value=plan_row.get("period_value"),
                error=str(exc),
            )
            return False

        # Half-open intersection test. A plan ending exactly at range_from
        # (plan_to == range_from) does NOT intersect the range.
        if range_to is not None and not (plan_from < range_to):
            return False
        if range_from is not None and not (plan_to > range_from):
            return False
        return True

    async def enrich_rows_with_plan(
        self,
        rows: list[dict[str, Any]],
        plan_fact_cfg: "PlanFactConfig",
        resolved_filters: Optional[list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """Post-enrich fact rows with plan values from the ``plans`` table.

        This is the core of the "plan/fact without JOIN" flow: the chart's
        SQL query only produces fact values, and this method afterwards
        attaches the corresponding plan value to every row using the
        dashboard selectors that are already applied to the fact.

        Args:
            rows: Fact rows returned by ``chart_service.execute_chart_query``.
                Mutated in place for efficiency — the same list is returned.
            plan_fact_cfg: Typed config read from ``chart_config.plan_fact``.
                Carries ``table_name``, ``field_name``, optional
                ``group_by_column`` and ``plan_key``.
            resolved_filters: The filter list produced by
                ``SelectorService.build_filters_for_chart`` — values are
                already resolved via ``date_tokens``. May be ``None`` or
                empty (treated as "no selectors", i.e. entire time range
                and no manager restriction).

        Returns:
            The ``rows`` list with an extra column named ``plan_key`` on
            every row. Rows whose group key has no matching plan still
            receive the "common plan" (``assigned_by_id IS NULL``) if any
            — they do NOT fall back to zero when common plans exist.

        Notes:
            * The common plan (``assigned_by_id IS NULL``) is **always**
              included, regardless of whether a manager filter is active.
            * When ``group_by_column`` is not set (or missing from rows)
              the method produces a scalar total and writes it onto every
              row — typical for single-row "Total" charts.
            * Malformed plan rows are skipped with a warning rather than
              crashing the entire chart.
        """
        # --- Edge cases & guards ---------------------------------------------------
        if not rows:  # scenario: empty fact → nothing to enrich
            return []
        if plan_fact_cfg is None:  # defensive — callers should gate on this
            return rows

        plan_key = plan_fact_cfg.plan_key or "plan"
        group_by_column = plan_fact_cfg.group_by_column
        table_name = plan_fact_cfg.table_name
        field_name = plan_fact_cfg.field_name

        if not table_name or not field_name:
            logger.warning(
                "plan_enrich: plan_fact_cfg missing table/field — skipping",
                table_name=table_name,
                field_name=field_name,
            )
            for row in rows:
                row.setdefault(plan_key, 0)
            return rows

        # --- 1. Extract selector signals ------------------------------------------
        assigned_ids, date_range = self._extract_selector_signals(resolved_filters)
        range_from, range_to = (date_range if date_range is not None else (None, None))

        # --- 2. Load candidate plans ----------------------------------------------
        # The SQL always allows "common plan" rows (assigned_by_id IS NULL).
        # When assigned_ids is None (no filter) we additionally load ALL
        # personal plans for (table, field). When assigned_ids is an empty
        # list (scenario #5 — "no managers matched") we include only the
        # common plan.
        engine = get_engine()
        params: dict[str, Any] = {
            "tbl": table_name,
            "fld": field_name,
        }

        if assigned_ids is None:
            sql_str = (
                "SELECT id, table_name, field_name, assigned_by_id, "
                "       period_type, period_value, date_from, date_to, plan_value "
                "FROM plans "
                "WHERE table_name = :tbl AND field_name = :fld"
            )
            stmt = text(sql_str)
        elif len(assigned_ids) == 0:
            sql_str = (
                "SELECT id, table_name, field_name, assigned_by_id, "
                "       period_type, period_value, date_from, date_to, plan_value "
                "FROM plans "
                "WHERE table_name = :tbl AND field_name = :fld "
                "  AND assigned_by_id IS NULL"
            )
            stmt = text(sql_str)
        else:
            sql_str = (
                "SELECT id, table_name, field_name, assigned_by_id, "
                "       period_type, period_value, date_from, date_to, plan_value "
                "FROM plans "
                "WHERE table_name = :tbl AND field_name = :fld "
                "  AND (assigned_by_id IS NULL OR assigned_by_id IN :ids)"
            )
            stmt = text(sql_str).bindparams(bindparam("ids", expanding=True))
            params["ids"] = list(assigned_ids)

        try:
            async with engine.begin() as conn:
                fetched = (await conn.execute(stmt, params)).fetchall()
        except Exception as exc:
            logger.warning(
                "plan_enrich: failed to load plans — returning zero plan",
                table_name=table_name,
                field_name=field_name,
                error=str(exc),
            )
            for row in rows:
                row.setdefault(plan_key, 0)
            return rows

        if not fetched:
            # Scenario #1: cfg points at (table, field) with no plans.
            logger.warning(
                "plan_enrich: no plans found for (table, field)",
                table_name=table_name,
                field_name=field_name,
            )
            for row in rows:
                row.setdefault(plan_key, 0)
            return rows

        plan_rows: list[dict[str, Any]] = [
            {
                "id": r[0],
                "table_name": r[1],
                "field_name": r[2],
                "assigned_by_id": r[3],
                "period_type": r[4],
                "period_value": r[5],
                "date_from": r[6],
                "date_to": r[7],
                "plan_value": r[8],
            }
            for r in fetched
        ]

        # --- 3. Filter by period intersection -------------------------------------
        candidates = [
            p for p in plan_rows if self._period_intersects(p, range_from, range_to)
        ]

        logger.debug(
            "plan_enrich: plans loaded and filtered",
            table_name=table_name,
            field_name=field_name,
            total_loaded=len(plan_rows),
            after_period_filter=len(candidates),
            assigned_ids=assigned_ids,
            range_from=range_from,
            range_to=range_to,
        )

        # --- 4. Aggregate plan_value ----------------------------------------------
        def _as_decimal(v: Any) -> Decimal:
            if v is None:
                return Decimal("0")
            if isinstance(v, Decimal):
                return v
            try:
                return Decimal(str(v))
            except Exception:
                return Decimal("0")

        common_plan = Decimal("0")
        per_group: dict[str, Decimal] = {}

        for p in candidates:
            pv = _as_decimal(p.get("plan_value"))
            aid = p.get("assigned_by_id")
            if aid is None or (isinstance(aid, str) and aid == ""):
                common_plan += pv
            else:
                key = self._norm_group_key(aid)
                per_group[key] = per_group.get(key, Decimal("0")) + pv

        total_plan = common_plan + sum(per_group.values(), Decimal("0"))

        # --- 5. Merge into rows ----------------------------------------------------
        if group_by_column:
            # Scenario #2: group column is declared but absent from rows.
            if rows and group_by_column not in rows[0]:
                logger.warning(
                    "plan_enrich: group_by_column missing from fact rows — "
                    "applying common plan only",
                    group_by_column=group_by_column,
                )
                for row in rows:
                    row[plan_key] = float(common_plan)
                return rows

            for row in rows:
                key = self._norm_group_key(row.get(group_by_column))
                # Rows whose group has no personal plan still get the common
                # plan — they must NOT drop to zero when a common plan exists.
                group_plan = per_group.get(key, Decimal("0")) + common_plan
                row[plan_key] = float(group_plan)
        else:
            # No grouping → scalar total on every row (usually a single row).
            for row in rows:
                row[plan_key] = float(total_plan)

        logger.debug(
            "plan_enrich: enrichment done",
            plan_key=plan_key,
            group_by_column=group_by_column,
            common_plan=str(common_plan),
            per_group_count=len(per_group),
            total_plan=str(total_plan),
            rows_enriched=len(rows),
        )

        return rows

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
        "### ГЛАВНОЕ ПРАВИЛО (post-enrichment, БЕЗ JOIN на plans)\n"
        "**НЕ джойни таблицу `plans` в `sql_query`.** Плановые значения подставляет backend\n"
        "после выполнения SQL — через механизм post-enrichment, который учитывает\n"
        "текущие селекторы дашборда (фильтр по менеджерам, диапазон дат).\n"
        "\n"
        "Вместо JOIN верни в JSON-ответе поле `plan_fact` внутри `chart_config` с\n"
        "параметрами того плана, который хочешь использовать:\n"
        "```\n"
        "\"chart_config\": {\n"
        "  \"plan_fact\": {\n"
        "    \"table_name\": \"<таблица факта, например crm_deals>\",\n"
        "    \"field_name\": \"<числовое поле, например opportunity>\",\n"
        "    \"date_column\": \"<дата-колонка в table_name — всегда date_create (план/факт считается по дате создания записи)>\",\n"
        "    \"group_by_column\": \"<assigned_by_id если факт группируется по менеджерам; иначе не включай/null>\"\n"
        "  }\n"
        "}\n"
        "```\n"
        "Backend сам подтянет все подходящие строки из `plans` (по table_name/field_name),\n"
        "применит фильтр менеджеров (включая общие планы с `assigned_by_id IS NULL`),\n"
        "отфильтрует по пересечению периодов с диапазоном дат и добавит в каждую строку\n"
        "результата колонку `plan` рядом с фактом. **Твой `sql_query` должен содержать\n"
        "ТОЛЬКО факт** — никакого `LEFT JOIN plans`, никаких подзапросов к `plans`,\n"
        "никаких хардкод-констант периода/менеджера из таблицы `plans`.\n"
        "\n"
        "Чтобы фронт нарисовал две серии (факт + план) рядом, включи обе колонки\n"
        "в `data_keys`: `\"data_keys\": {\"x\": [\"actual\", \"plan\"], \"y\": \"manager\"}`.\n"
        "Колонка `plan` появится в rows автоматически после enrichment — в самом\n"
        "`sql_query` её писать НЕ нужно.\n"
        "\n"
        "### Как выбрать table_name/field_name для plan_fact\n"
        "План может быть поставлен на **ЛЮБОЕ числовое поле ЛЮБОЙ таблицы** — это может быть\n"
        "`crm_deals.opportunity`, количество сделок, количество звонков, сумма по кастомному полю и\n"
        "т.п. НЕ хардкодь `crm_deals.opportunity` — всегда бери `table_name` и `field_name` из\n"
        "конкретной строки таблицы `plans`, которую собираешься использовать (см. раздел\n"
        "«Активные планы» ниже — пары (table, field), доступные в системе).\n"
        "\n"
        "Если пользователь не указал явно, какой план использовать (по какой таблице/полю/периоду/\n"
        "менеджеру), **ВСЕГДА бери самый свежий план** — это строка с максимальным `id`\n"
        "(эквивалентно максимальному `created_at`). В разделе «Активные планы» ниже они уже\n"
        "перечислены в порядке от самого нового к самому старому — первая строка списка и есть\n"
        "план по умолчанию; его `table_name` и `field_name` идут в `plan_fact`.\n"
        "\n"
        "После того, как ты определил план, `sql_query` должен считать факт по этому же\n"
        "`table_name`/`field_name`. Если самый новый план, например, по `crm_calls.duration` —\n"
        "факт считается как `SUM(crm_calls.duration)`, а не `SUM(crm_deals.opportunity)`.\n"
        "\n"
        "### Жёсткие правила построения SQL для «план/факт» (только факт, без plans):\n"
        "1. НЕ добавляй `LEFT JOIN plans`, подзапросы `SELECT ... FROM plans` или любые другие\n"
        "   обращения к таблице `plans` в `sql_query`. План подставляется post-enrichment'ом.\n"
        "2. НЕ хардкодь константы периода в WHERE/JOIN (`date_create >= '2026-04-01'` и т.п.),\n"
        "   если пользователь явно не попросил фиксированный период. Период в факт попадает\n"
        "   из селектора `date_range` дашборда, а в план — через тот же резолвнутый диапазон.\n"
        "   SQL должен оставаться «нейтральным» к периоду, чтобы `apply_filters` мог вставить\n"
        "   WHERE по `date_column` при открытии чарта.\n"
        "3. НЕ добавляй фильтры `closed`, `stage_semantic_id`, статусы и т.п., если пользователь\n"
        "   их явно не попросил. План/факт сравнивает ВСЕ записи за период, а не только выигранные\n"
        "   сделки.\n"
        "4. Bitrix-поле `closed` содержит строки `'Y'`/`'N'` (НЕ `'1'`/`'0'`).\n"
        "   `stage_semantic_id`: `'P'` = в процессе, `'S'` = успешно (выигранные), `'F'` = провал.\n"
        "5. `date_column` в `plan_fact` — это колонка даты основной таблицы, по которой\n"
        "   селектор диапазона дат будет фильтровать факт. Всегда используй `date_create`\n"
        "   (включая `crm_deals`) — план/факт считается по дате создания записи.\n"
        "   Именно эту же колонку backend использует, чтобы понять, какие планы попадают\n"
        "   в текущий диапазон.\n"
        "6. НИКОГДА не джойнь `bitrix_users` как источник строк результата — менеджеры, у которых\n"
        "   нет ни одной записи за период, не должны появляться в отчёте. Строй строки ОТ\n"
        "   основной таблицы (через `assigned_by_id` из записей) и LEFT JOIN `bitrix_users`\n"
        "   только ради получения имён.\n"
        "7. `group_by_column` в `plan_fact` заполняй, только если факт группируется по менеджерам\n"
        "   (обычно `assigned_by_id`) — тогда backend разложит план по тем же группам,\n"
        "   а общие планы (`assigned_by_id IS NULL`) добавятся к каждой группе. Если чарт —\n"
        "   одна общая метрика без группировки (индикатор, «всего по компании»), оставь\n"
        "   `group_by_column` пустым/не включай его — план будет скаляром.\n"
        "8. Используй агрегат, соответствующий смыслу поля: `SUM` для сумм, `COUNT(*)` если план\n"
        "   выставлен на количество записей, `AVG` — для средних. По умолчанию `SUM(field_name)`.\n"
        "\n"
        "### Канонический пример: план vs факт по менеджерам (post-enrichment)\n"
        "Запрос пользователя: «нужен план vs факт по менеджерам». Предположим, в разделе\n"
        "«Активные планы» самый свежий план — по `crm_deals.opportunity`. Правильный spec:\n"
        "```json\n"
        "{\n"
        "  \"title\": \"План vs Факт по менеджерам\",\n"
        "  \"chart_type\": \"horizontal_bar\",\n"
        "  \"sql_query\": \"SELECT CONCAT(COALESCE(u.name,''),' ',COALESCE(u.last_name,'')) AS manager, d.assigned_by_id, COALESCE(SUM(d.opportunity),0) AS actual FROM crm_deals d LEFT JOIN bitrix_users u ON u.bitrix_id = d.assigned_by_id GROUP BY d.assigned_by_id, u.name, u.last_name\",\n"
        "  \"data_keys\": {\"x\": [\"actual\", \"plan\"], \"y\": \"manager\"},\n"
        "  \"chart_config\": {\n"
        "    \"plan_fact\": {\n"
        "      \"table_name\": \"crm_deals\",\n"
        "      \"field_name\": \"opportunity\",\n"
        "      \"date_column\": \"date_create\",\n"
        "      \"group_by_column\": \"assigned_by_id\"\n"
        "    }\n"
        "  }\n"
        "}\n"
        "```\n"
        "Обрати внимание: в `sql_query` НЕТ `JOIN plans`, НЕТ колонки `plan`, НЕТ констант\n"
        "периода — всё это за тебя сделает backend на этапе post-enrichment. Имя поля\n"
        "`SUM(d.opportunity)` и таблица `crm_deals` взяты ИЗ САМОГО СВЕЖЕГО ПЛАНА, а не\n"
        "захардкожены произвольно.\n"
        "\n"
        "### Канонический пример: одна общая метрика (без группировки)\n"
        "Запрос: «покажи общий план/факт за текущий период». Тогда `group_by_column` не\n"
        "заполняется, `chart_type` = `indicator` или `bar`:\n"
        "```json\n"
        "{\n"
        "  \"title\": \"План vs Факт\",\n"
        "  \"chart_type\": \"bar\",\n"
        "  \"sql_query\": \"SELECT 'Итого' AS label, COALESCE(SUM(opportunity),0) AS actual FROM crm_deals\",\n"
        "  \"data_keys\": {\"x\": \"label\", \"y\": [\"actual\", \"plan\"]},\n"
        "  \"chart_config\": {\n"
        "    \"plan_fact\": {\n"
        "      \"table_name\": \"crm_deals\",\n"
        "      \"field_name\": \"opportunity\",\n"
        "      \"date_column\": \"date_create\"\n"
        "    }\n"
        "  }\n"
        "}\n"
        "```\n"
        "Здесь backend просуммирует все подходящие планы (включая общие `assigned_by_id IS NULL`\n"
        "и персональные — если выбран фильтр менеджеров) и подставит итог в колонку `plan`\n"
        "единственной строки результата."
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
            (
                "Пары `(table, field)` из этой таблицы используй как `table_name` / "
                "`field_name` в `chart_config.plan_fact` — именно они говорят backend'у, "
                "какие плановые строки подтянуть при post-enrichment. НЕ джойни эту "
                "таблицу в `sql_query`."
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
