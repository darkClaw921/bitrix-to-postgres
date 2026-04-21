"""Domain service for plan templates (``plan_templates`` table).

CRUD над ``plan_templates`` и центральный ``expand_template`` — развёртывание
шаблона в список черновиков (``PlanDraft``), которые фронт показывает
пользователю перед массовым сохранением через ``PlanService.batch_create_plans``.

Реализован поверх сырых ``text()``-запросов (``get_engine().begin()``) —
тот же паттерн, что и в ``PlanService``: целевые таблицы/колонки планов
динамические, а сам ``plan_templates`` как первичный источник хранит
``specific_manager_ids`` в JSON text (парсится здесь в ``list[str]``).

Взаимодействие с другими модулями:

* :class:`app.domain.services.department_service.DepartmentService` —
  используется при ``assignees_mode='department'`` (резолв имени
  отдела в ``bitrix_id``, сбор подотделов, выборка менеджеров).
* :class:`app.api.v1.schemas.plans.PlanDraft` — финальный формат
  одной строки превью.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Optional

from sqlalchemy import bindparam, text

from app.api.v1.schemas.plans import (
    ALL_ASSIGNEES_MODES,
    ALL_PERIOD_MODES,
    ALL_PERIOD_TYPES,
    PlanDraft,
    PlanTemplateCreateRequest,
    PlanTemplateUpdateRequest,
)
from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.domain.entities.plan_template import PlanTemplateEntity
from app.domain.services.department_service import DepartmentService
from app.infrastructure.database.connection import get_dialect, get_engine

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PlanTemplateServiceError(AppException):
    """Base class for PlanTemplateService errors."""


class PlanTemplateValidationError(PlanTemplateServiceError):
    """Payload failed validation (bad mode combination, missing field, etc)."""


class PlanTemplateNotFoundError(PlanTemplateServiceError):
    """Template with the requested id does not exist."""


class PlanTemplateConflictError(PlanTemplateServiceError):
    """Operation not allowed (e.g. deleting a builtin template)."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class PlanTemplateService:
    """CRUD over ``plan_templates`` + expand_template → list[PlanDraft]."""

    def __init__(
        self,
        department_service: Optional[DepartmentService] = None,
    ) -> None:
        """Allow injecting a custom DepartmentService (tests / fakes)."""
        self._department_service = department_service or DepartmentService()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        """Convert a SQLAlchemy Row into a plain dict."""
        mapping = getattr(row, "_mapping", None)
        if mapping is None:
            return dict(row)
        return {k: v for k, v in mapping.items()}

    @staticmethod
    def _parse_specific_ids(raw: Any) -> Optional[list[str]]:
        """Parse ``specific_manager_ids`` text column into a list of strings.

        Accepts JSON array (``'["1","2"]'``) or ``None``. Falls back to an
        empty list on malformed JSON so we never blow up in the middle of
        an endpoint — a warning is logged instead.
        """
        if raw is None:
            return None
        if isinstance(raw, list):
            return [str(x) for x in raw]
        if not isinstance(raw, str):
            return None
        s = raw.strip()
        if not s:
            return None
        try:
            parsed = json.loads(s)
        except (TypeError, ValueError) as exc:
            logger.warning(
                "plan_template: malformed specific_manager_ids JSON — "
                "treating as empty",
                raw=raw,
                error=str(exc),
            )
            return []
        if not isinstance(parsed, list):
            return []
        return [str(x) for x in parsed]

    @classmethod
    def _row_to_entity(cls, row: Any) -> PlanTemplateEntity:
        """Convert a raw ``plan_templates`` row into a typed entity."""
        data = cls._row_to_dict(row)
        data["specific_manager_ids"] = cls._parse_specific_ids(
            data.get("specific_manager_ids")
        )
        return PlanTemplateEntity.model_validate(data)

    @staticmethod
    def _serialize_specific_ids(ids: Optional[list[str]]) -> Optional[str]:
        """Serialize ``list[str]`` → JSON text for the ``specific_manager_ids`` column.

        ``None`` stays ``None`` (NULL in DB); an explicit empty list becomes
        ``'[]'`` so we can distinguish "not set" from "explicitly none".
        """
        if ids is None:
            return None
        return json.dumps([str(x) for x in ids])

    # ------------------------------------------------------------------
    # Period helpers — map period_mode → (period_type, period_value, dates)
    # ------------------------------------------------------------------

    @staticmethod
    def _current_month_value(today: Optional[date] = None) -> str:
        today = today or date.today()
        return today.strftime("%Y-%m")

    @staticmethod
    def _current_quarter_value(today: Optional[date] = None) -> str:
        today = today or date.today()
        quarter = (today.month - 1) // 3 + 1
        return f"{today.year}-Q{quarter}"

    @staticmethod
    def _current_year_value(today: Optional[date] = None) -> str:
        today = today or date.today()
        return today.strftime("%Y")

    @classmethod
    def _resolve_period(
        cls,
        template: PlanTemplateEntity,
        period_value_override: Optional[str] = None,
    ) -> tuple[str, Optional[str], Optional[date], Optional[date]]:
        """Return ``(period_type, period_value, date_from, date_to)`` for a plan.

        Маппинг ``period_mode`` → конкретный period:

        * ``current_month`` → ``(month, YYYY-MM, None, None)``
        * ``current_quarter`` → ``(quarter, YYYY-QN, None, None)``
        * ``current_year`` → ``(year, YYYY, None, None)``
        * ``custom_period`` → берутся template.period_type/period_value/
          date_from/date_to как есть.

        ``period_value_override`` заменяет вычисленное значение (удобно,
        когда хочется создать план на, скажем, следующий месяц).
        """
        mode = template.period_mode
        if mode == "current_month":
            value = period_value_override or cls._current_month_value()
            return "month", value, None, None
        if mode == "current_quarter":
            value = period_value_override or cls._current_quarter_value()
            return "quarter", value, None, None
        if mode == "current_year":
            value = period_value_override or cls._current_year_value()
            return "year", value, None, None
        if mode == "custom_period":
            ptype = template.period_type or "custom"
            if ptype not in ALL_PERIOD_TYPES:
                raise PlanTemplateValidationError(
                    f"Invalid period_type '{ptype}' for custom_period"
                )
            pvalue = period_value_override or template.period_value
            if ptype in {"month", "quarter", "year"} and not pvalue:
                raise PlanTemplateValidationError(
                    f"period_value is required for period_type='{ptype}'"
                )
            if ptype == "custom":
                if template.date_from is None or template.date_to is None:
                    raise PlanTemplateValidationError(
                        "date_from and date_to are required for "
                        "period_type='custom'"
                    )
                return ptype, None, template.date_from, template.date_to
            return ptype, pvalue, None, None
        raise PlanTemplateValidationError(f"Unknown period_mode: {mode}")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def list_templates(self) -> list[PlanTemplateEntity]:
        """Return all templates (including builtin) ordered by id ASC."""
        engine = get_engine()
        async with engine.begin() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT id, name, description, table_name, field_name, "
                        "       period_mode, period_type, period_value, "
                        "       date_from, date_to, assignees_mode, "
                        "       department_name, specific_manager_ids, "
                        "       default_plan_value, is_builtin, "
                        "       created_by_id, created_at, updated_at "
                        "FROM plan_templates "
                        "ORDER BY id ASC"
                    )
                )
            ).fetchall()
        return [self._row_to_entity(r) for r in rows]

    async def get_template(
        self, template_id: int
    ) -> Optional[PlanTemplateEntity]:
        """Return a single template by id, or ``None`` if not found."""
        engine = get_engine()
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT id, name, description, table_name, field_name, "
                        "       period_mode, period_type, period_value, "
                        "       date_from, date_to, assignees_mode, "
                        "       department_name, specific_manager_ids, "
                        "       default_plan_value, is_builtin, "
                        "       created_by_id, created_at, updated_at "
                        "FROM plan_templates "
                        "WHERE id = :id"
                    ),
                    {"id": template_id},
                )
            ).first()
        return self._row_to_entity(row) if row else None

    async def create_template(
        self,
        payload: PlanTemplateCreateRequest,
        created_by_id: Optional[str],
    ) -> PlanTemplateEntity:
        """Insert a new user-defined template (``is_builtin=FALSE``)."""
        if payload.period_mode not in ALL_PERIOD_MODES:
            raise PlanTemplateValidationError(
                f"period_mode must be one of {sorted(ALL_PERIOD_MODES)}"
            )
        if payload.assignees_mode not in ALL_ASSIGNEES_MODES:
            raise PlanTemplateValidationError(
                f"assignees_mode must be one of {sorted(ALL_ASSIGNEES_MODES)}"
            )

        engine = get_engine()
        insert_cols = [
            "name",
            "description",
            "table_name",
            "field_name",
            "period_mode",
            "period_type",
            "period_value",
            "date_from",
            "date_to",
            "assignees_mode",
            "department_name",
            "specific_manager_ids",
            "default_plan_value",
            "is_builtin",
            "created_by_id",
        ]
        col_list = ", ".join(insert_cols)
        placeholders = ", ".join(f":{c}" for c in insert_cols)

        params: dict[str, Any] = {
            "name": payload.name,
            "description": payload.description,
            "table_name": payload.table_name,
            "field_name": payload.field_name,
            "period_mode": payload.period_mode,
            "period_type": payload.period_type,
            "period_value": payload.period_value,
            "date_from": payload.date_from,
            "date_to": payload.date_to,
            "assignees_mode": payload.assignees_mode,
            "department_name": payload.department_name,
            "specific_manager_ids": self._serialize_specific_ids(
                payload.specific_manager_ids
            ),
            "default_plan_value": payload.default_plan_value,
            "is_builtin": False,
            "created_by_id": created_by_id,
        }

        dialect = get_dialect()
        async with engine.begin() as conn:
            if dialect == "postgresql":
                sql = (
                    f"INSERT INTO plan_templates ({col_list}) "
                    f"VALUES ({placeholders}) RETURNING id"
                )
                result = await conn.execute(text(sql), params)
                new_id = int(result.scalar())
            else:
                sql = (
                    f"INSERT INTO plan_templates ({col_list}) "
                    f"VALUES ({placeholders})"
                )
                result = await conn.execute(text(sql), params)
                new_id = int(result.lastrowid)

        logger.info(
            "plan_template created",
            template_id=new_id,
            name=payload.name,
            period_mode=payload.period_mode,
            assignees_mode=payload.assignees_mode,
        )

        created = await self.get_template(new_id)
        if created is None:
            raise PlanTemplateServiceError(
                f"Template {new_id} was created but could not be re-read"
            )
        return created

    async def update_template(
        self,
        template_id: int,
        payload: PlanTemplateUpdateRequest,
    ) -> PlanTemplateEntity:
        """Partial update.

        Builtin-шаблоны защищены: для них запрещено менять ``name``,
        ``period_mode``, ``assignees_mode`` (они определяют сам смысл
        шаблона). Остальные поля (description, table_name/field_name,
        default_plan_value) можно обновлять — чтобы пользователь мог
        подготовить builtin к быстрому применению.
        """
        existing = await self.get_template(template_id)
        if existing is None:
            raise PlanTemplateNotFoundError(
                f"Template {template_id} not found"
            )

        data = payload.model_dump(exclude_unset=True)

        if existing.is_builtin:
            protected = {"name", "period_mode", "assignees_mode"}
            touched = protected & data.keys()
            if touched:
                raise PlanTemplateConflictError(
                    f"Cannot modify builtin template fields: "
                    f"{sorted(touched)}"
                )

        if not data:
            return existing

        if "period_mode" in data and data["period_mode"] not in ALL_PERIOD_MODES:
            raise PlanTemplateValidationError(
                f"period_mode must be one of {sorted(ALL_PERIOD_MODES)}"
            )
        if (
            "assignees_mode" in data
            and data["assignees_mode"] not in ALL_ASSIGNEES_MODES
        ):
            raise PlanTemplateValidationError(
                f"assignees_mode must be one of {sorted(ALL_ASSIGNEES_MODES)}"
            )

        # Сериализуем specific_manager_ids, если он в payload.
        if "specific_manager_ids" in data:
            data["specific_manager_ids"] = self._serialize_specific_ids(
                data["specific_manager_ids"]
            )

        set_parts = [f"{col} = :{col}" for col in data.keys()]
        set_parts.append("updated_at = NOW()")
        params: dict[str, Any] = dict(data)
        params["id"] = template_id
        sql = (
            f"UPDATE plan_templates SET {', '.join(set_parts)} "
            f"WHERE id = :id"
        )

        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text(sql), params)

        logger.info(
            "plan_template updated",
            template_id=template_id,
            fields=list(data.keys()),
        )

        updated = await self.get_template(template_id)
        if updated is None:
            raise PlanTemplateServiceError(
                f"Template {template_id} was updated but could not be re-read"
            )
        return updated

    async def delete_template(self, template_id: int) -> None:
        """Delete a user template. Raises on not-found / builtin."""
        existing = await self.get_template(template_id)
        if existing is None:
            raise PlanTemplateNotFoundError(
                f"Template {template_id} not found"
            )
        if existing.is_builtin:
            raise PlanTemplateConflictError(
                f"Builtin template (id={template_id}) cannot be deleted"
            )

        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM plan_templates WHERE id = :id"),
                {"id": template_id},
            )

        logger.info("plan_template deleted", template_id=template_id)

    # ------------------------------------------------------------------
    # Expand — template → list[PlanDraft]
    # ------------------------------------------------------------------

    async def _resolve_department_ids(
        self, department_name: str
    ) -> list[str]:
        """Resolve a department name into the list of self+descendant bitrix_ids.

        Ищем через ``bitrix_departments.name``. Для кросс-БД совместимости
        (PG / MySQL) используем обычный ``=`` — точное совпадение. Если
        найдено несколько записей с одинаковым именем, берём первую
        (deterministic: ORDER BY bitrix_id ASC). Если не найден —
        ``PlanTemplateValidationError``.
        """
        engine = get_engine()
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT bitrix_id FROM bitrix_departments "
                        "WHERE name = :name "
                        "ORDER BY bitrix_id ASC LIMIT 1"
                    ),
                    {"name": department_name},
                )
            ).first()
        if not row:
            raise PlanTemplateValidationError(
                f"Department '{department_name}' not found in "
                f"bitrix_departments"
            )

        root_id = str(row[0])
        descendant_ids = await self._department_service.collect_descendant_ids(
            root_id
        )
        return descendant_ids or [root_id]

    async def _fetch_all_active_managers(self) -> list[dict[str, Any]]:
        """Return all active bitrix_users.

        Bitrix может отдавать ACTIVE в разных форматах: 'Y'/'N' (классика)
        или '1'/'0' (boolean cast). Принимаем оба + NULL.
        """
        engine = get_engine()
        async with engine.begin() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT bitrix_id, name, last_name, active "
                        "FROM bitrix_users "
                        "WHERE active IN ('Y', 'y', '1', 'true', 'TRUE') "
                        "OR active IS NULL "
                        "ORDER BY bitrix_id"
                    )
                )
            ).fetchall()
        return [
            {
                "bitrix_id": str(r[0]),
                "name": r[1],
                "last_name": r[2],
                "active": r[3],
            }
            for r in rows
        ]

    async def _fetch_users_by_ids(
        self, ids: list[str]
    ) -> list[dict[str, Any]]:
        """Return selected users by bitrix_id (preserves all, active or not).

        Используется при ``assignees_mode='specific'`` — пользователь мог
        явно добавить неактивного менеджера, и решение о блокировке
        остаётся за UI (сервис только помечает draft-ы warning'ами).
        """
        if not ids:
            return []
        str_ids = [str(x) for x in ids]
        engine = get_engine()
        stmt = text(
            "SELECT bitrix_id, name, last_name, active "
            "FROM bitrix_users "
            "WHERE bitrix_id IN :ids"
        ).bindparams(bindparam("ids", expanding=True))
        async with engine.begin() as conn:
            rows = (
                await conn.execute(stmt, {"ids": str_ids})
            ).fetchall()
        found = {
            str(r[0]): {
                "bitrix_id": str(r[0]),
                "name": r[1],
                "last_name": r[2],
                "active": r[3],
            }
            for r in rows
        }
        # Сохраняем порядок из входа; менеджеры, отсутствующие в
        # bitrix_users, всё равно попадают в драфт — но с warning'ом в
        # upstream-коде (если нужно).
        result: list[dict[str, Any]] = []
        for sid in str_ids:
            if sid in found:
                result.append(found[sid])
            else:
                result.append(
                    {
                        "bitrix_id": sid,
                        "name": None,
                        "last_name": None,
                        "active": None,
                    }
                )
        return result

    @staticmethod
    def _format_manager_name(user: dict[str, Any]) -> Optional[str]:
        """Build a human-readable ``"Name LastName"`` for a user dict."""
        name = user.get("name") or ""
        last_name = user.get("last_name") or ""
        full = f"{name} {last_name}".strip()
        return full or None

    async def expand_template(
        self,
        template_id: int,
        overrides: Optional[dict[str, Any]] = None,
    ) -> list[PlanDraft]:
        """Expand a template into a list of ``PlanDraft`` previews.

        ``overrides`` keys:

        * ``table_name`` — заменяет ``template.table_name`` (обязателен,
          когда template.table_name IS NULL, как у builtin).
        * ``field_name`` — аналогично.
        * ``period_value`` — заменяет вычисленное период-значение
          (например, конкретный месяц вместо текущего).
        """
        overrides = overrides or {}
        template = await self.get_template(template_id)
        if template is None:
            raise PlanTemplateNotFoundError(
                f"Template {template_id} not found"
            )

        table_name = overrides.get("table_name") or template.table_name
        field_name = overrides.get("field_name") or template.field_name
        if not table_name or not field_name:
            raise PlanTemplateValidationError(
                "table_name and field_name are required to expand a template "
                "(pass as overrides for builtin templates)"
            )

        period_type, period_value, date_from, date_to = self._resolve_period(
            template,
            period_value_override=overrides.get("period_value"),
        )

        drafts: list[PlanDraft] = []
        mode = template.assignees_mode

        if mode == "all_managers":
            managers = await self._fetch_all_active_managers()
            for m in managers:
                drafts.append(
                    PlanDraft(
                        assigned_by_id=m["bitrix_id"],
                        assigned_by_name=self._format_manager_name(m),
                        table_name=table_name,
                        field_name=field_name,
                        period_type=period_type,
                        period_value=period_value,
                        date_from=date_from,
                        date_to=date_to,
                        plan_value=template.default_plan_value,
                        description=f"Шаблон: {template.name}",
                        warnings=[],
                    )
                )

        elif mode == "department":
            if not template.department_name:
                raise PlanTemplateValidationError(
                    "department_name is required for "
                    "assignees_mode='department'"
                )
            dept_ids = await self._resolve_department_ids(
                template.department_name
            )
            managers = await self._department_service.list_managers_in_departments(
                dept_ids, active_only=True
            )
            if not managers:
                logger.warning(
                    "plan_template expand: department has no active managers",
                    template_id=template_id,
                    department_name=template.department_name,
                )
            for m in managers:
                drafts.append(
                    PlanDraft(
                        assigned_by_id=m["bitrix_id"],
                        assigned_by_name=self._format_manager_name(m),
                        table_name=table_name,
                        field_name=field_name,
                        period_type=period_type,
                        period_value=period_value,
                        date_from=date_from,
                        date_to=date_to,
                        plan_value=template.default_plan_value,
                        description=f"Шаблон: {template.name}",
                        warnings=[],
                    )
                )

        elif mode == "specific":
            ids = template.specific_manager_ids or []
            managers = await self._fetch_users_by_ids(ids)
            for m in managers:
                warnings: list[str] = []
                if m.get("active") and m.get("active") != "Y":
                    warnings.append(
                        f"Менеджер {m['bitrix_id']} не активен"
                    )
                if m.get("name") is None and m.get("last_name") is None:
                    warnings.append(
                        f"Менеджер {m['bitrix_id']} не найден в bitrix_users"
                    )
                drafts.append(
                    PlanDraft(
                        assigned_by_id=m["bitrix_id"],
                        assigned_by_name=self._format_manager_name(m),
                        table_name=table_name,
                        field_name=field_name,
                        period_type=period_type,
                        period_value=period_value,
                        date_from=date_from,
                        date_to=date_to,
                        plan_value=template.default_plan_value,
                        description=f"Шаблон: {template.name}",
                        warnings=warnings,
                    )
                )

        elif mode == "global":
            drafts.append(
                PlanDraft(
                    assigned_by_id=None,
                    assigned_by_name=None,
                    table_name=table_name,
                    field_name=field_name,
                    period_type=period_type,
                    period_value=period_value,
                    date_from=date_from,
                    date_to=date_to,
                    plan_value=template.default_plan_value,
                    description=f"Шаблон: {template.name}",
                    warnings=[],
                )
            )

        else:
            raise PlanTemplateValidationError(
                f"Unknown assignees_mode: {mode}"
            )

        logger.info(
            "plan_template expanded",
            template_id=template_id,
            assignees_mode=mode,
            period_type=period_type,
            period_value=period_value,
            drafts_count=len(drafts),
        )

        return drafts
