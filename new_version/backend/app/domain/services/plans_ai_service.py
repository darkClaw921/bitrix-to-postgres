"""Aggregating service for AI-generated plans (Phase 3).

Обёртка над :class:`AIService` + :class:`PlanService` + :class:`DepartmentService`,
которая превращает свободный текстовый запрос пользователя в список
:class:`PlanDraft` для превью в UI (без записи в БД).

Поток данных:

1. ``AIService.generate_plans_from_description`` вызывает LLM и возвращает
   «сырые» черновики (где ``assigned_by_id`` может быть спец-значением
   ``"all_managers"`` / ``"department:Название"``).
2. :meth:`PlansAIService.expand_ai_drafts` разворачивает спец-значения
   в конкретные ``bitrix_id`` (через :class:`DepartmentService` и
   ``bitrix_users``), затем валидирует каждый черновик через
   :meth:`PlanService._validate_numeric_column` и
   :meth:`PlanService._validate_period` — без INSERT.
3. Невалидные черновики не попадают в ``plans`` ответа, но получают
   человеко-читаемое предупреждение в ``warnings`` — фронт показывает его
   пользователю, чтобы он мог откорректировать запрос.

Единственная точка входа — :meth:`PlansAIService.generate_and_expand`.
Она вызывается из endpoint'а ``POST /plans/ai-generate``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from sqlalchemy import text

from app.api.v1.schemas.plans import (
    ALL_PERIOD_TYPES,
    PlanAIGenerateResponse,
    PlanDraft,
)
from app.core.logging import get_logger
from app.domain.services.ai_service import AIService
from app.domain.services.department_service import DepartmentService
from app.domain.services.plan_service import (
    PlanService,
    PlanValidationError,
)
from app.infrastructure.database.connection import get_engine

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class PlansAIService:
    """High-level orchestrator for the ``POST /plans/ai-generate`` flow.

    Агрегирует три доменных сервиса:

    * :class:`AIService` — вызов LLM + парсинг JSON.
    * :class:`PlanService` — валидация drafts через существующие методы
      (``_validate_numeric_column``, ``_validate_period``) БЕЗ INSERT.
    * :class:`DepartmentService` — поиск отдела по имени и выборка
      менеджеров (включая подотделы, только активные).
    """

    def __init__(
        self,
        ai_service: Optional[AIService] = None,
        plan_service: Optional[PlanService] = None,
        department_service: Optional[DepartmentService] = None,
    ) -> None:
        """All three collaborators may be injected for tests/DI."""
        self._plan_service = plan_service or PlanService()
        self._department_service = department_service or DepartmentService()
        # AIService конструируется с тем же PlanService, чтобы
        # _get_bitrix_context внутри AIService видел актуальные планы.
        self._ai_service = ai_service or AIService(plan_service=self._plan_service)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _as_decimal(value: Any) -> Optional[Decimal]:
        """Coerce ``value`` into Decimal, or return None on failure."""
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None

    @staticmethod
    def _as_date(value: Any) -> Optional[date]:
        """Coerce an ISO-string / date to ``date``; return None on failure."""
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            try:
                return date.fromisoformat(s[:10])
            except ValueError:
                return None
        return None

    async def _find_department_by_name(
        self, name: str
    ) -> Optional[str]:
        """Case-insensitive search for a department by name.

        Возвращает ``bitrix_id`` первого найденного отдела или ``None``
        если совпадений нет. ``LOWER(name) = LOWER(:name)`` работает и в
        PostgreSQL, и в MySQL — не требует регистра-независимых collations.
        """
        if not name:
            return None
        engine = get_engine()
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT bitrix_id FROM bitrix_departments "
                        "WHERE LOWER(name) = LOWER(:name) "
                        "ORDER BY bitrix_id ASC LIMIT 1"
                    ),
                    {"name": name},
                )
            ).first()
        return str(row[0]) if row else None

    async def _fetch_active_managers(self) -> list[dict[str, Any]]:
        """Return all users from ``bitrix_users`` (active + inactive).

        Возвращает ВСЕХ пользователей с флагом ``active`` (``'Y'``/``'N'``).
        Inactive-юзеры нужны для LLM-контекста и fallback-matcher'а — иначе
        пользователь пишет «Максим Крылов», а LLM видит пустой список и
        безнадёжно ставит ``null``. При expand для ``"all_managers"`` мы
        фильтруем только active.
        """
        engine = get_engine()
        async with engine.begin() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT bitrix_id, name, last_name, active "
                        "FROM bitrix_users "
                        "ORDER BY bitrix_id"
                    )
                )
            ).fetchall()
        # Bitrix может отдавать active в разных форматах: 'Y'/'N' или '1'/'0'.
        # Normalize: считаем активным если значение Y/1/true (любой регистр).
        active_truthy = {"Y", "y", "1", "true", "TRUE", "True"}
        return [
            {
                "bitrix_id": str(r[0]),
                "name": r[1],
                "last_name": r[2],
                "active": (r[3] in active_truthy) if r[3] is not None else True,
            }
            for r in rows
        ]

    async def _fetch_user_by_id(
        self, bitrix_id: str
    ) -> Optional[dict[str, Any]]:
        """Return a single user row by bitrix_id, or None if not found."""
        engine = get_engine()
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT bitrix_id, name, last_name "
                        "FROM bitrix_users "
                        "WHERE bitrix_id = :bid"
                    ),
                    {"bid": str(bitrix_id)},
                )
            ).first()
        if not row:
            return None
        return {
            "bitrix_id": str(row[0]),
            "name": row[1],
            "last_name": row[2],
        }

    @staticmethod
    def _format_manager_name(user: dict[str, Any]) -> Optional[str]:
        """Build a human-readable ``"Name LastName"`` string."""
        name = user.get("name") or ""
        last_name = user.get("last_name") or ""
        full = f"{name} {last_name}".strip()
        return full or None

    @staticmethod
    def _format_managers_context(managers: list[dict[str, Any]]) -> str:
        """Format active managers as markdown for LLM prompt injection.

        Пример вывода:

        ```
        | bitrix_id | name |
        |-----------|------|
        | 123       | Максим Крылов |
        ```

        Используется LLM для резолвинга имён в bitrix_id. Обрезаем до первых
        500 менеджеров (мягкий лимит — обычно CRM имеет сильно меньше).
        """
        if not managers:
            return "нет менеджеров в bitrix_users (таблица пуста — запустите sync users)"
        rows = [
            "| bitrix_id | Имя | Активен |",
            "|-----------|-----|---------|",
        ]
        for m in managers[:500]:
            full = PlansAIService._format_manager_name(m) or "(без имени)"
            safe = full.replace("|", "/")
            active_flag = "да" if m.get("active") else "нет"
            rows.append(f"| {m['bitrix_id']} | {safe} | {active_flag} |")
        if len(managers) > 500:
            rows.append(f"| ... | (ещё {len(managers) - 500} менеджеров) | ... |")
        return "\n".join(rows)

    @staticmethod
    def _match_manager_by_name(
        query: str, managers: list[dict[str, Any]]
    ) -> Optional[dict[str, Any]]:
        """Fuzzy name match against ``managers`` list.

        Стратегия (от строгой к мягкой):

        1. exact match на полное имя ``"Имя Фамилия"`` (case-insensitive).
        2. exact match на отдельно имя или фамилию.
        3. содержит все слова запроса (токены в обоих порядках).

        Падеж не нормализуется (русская морфология слишком объёмна для
        такого matcher'а) — но для основных именительных/родительных
        форм типа «Крылов» vs «Крылова» добавляется префиксное совпадение
        по первым 5 символам каждого токена.
        """
        if not query:
            return None
        q = query.strip().lower()
        if not q:
            return None

        # Level 1-2: exact full name / single token.
        for m in managers:
            name = (m.get("name") or "").strip().lower()
            last_name = (m.get("last_name") or "").strip().lower()
            full = f"{name} {last_name}".strip()
            reversed_full = f"{last_name} {name}".strip()
            if q == full or q == reversed_full:
                return m
            if q == name or q == last_name:
                return m

        # Level 3: all query tokens present (prefix match ≥5 chars or full
        # containment) in name+last_name combined.
        q_tokens = [t for t in q.replace(",", " ").split() if t]
        if not q_tokens:
            return None
        for m in managers:
            haystack = " ".join(
                [(m.get("name") or ""), (m.get("last_name") or "")]
            ).strip().lower()
            if not haystack:
                continue
            ok = True
            for tok in q_tokens:
                # Prefix match: first 5 chars should appear in some word.
                prefix = tok[:5]
                if prefix not in haystack:
                    ok = False
                    break
            if ok:
                return m

        return None

    # ------------------------------------------------------------------
    # Plan draft helpers
    # ------------------------------------------------------------------

    def _normalize_raw_plan(
        self, raw: dict[str, Any], warnings: list[str], idx: int
    ) -> Optional[dict[str, Any]]:
        """Coerce a raw LLM plan dict into a normalized dict.

        Возвращает None, если запись совершенно неюзабельна (отсутствует
        обязательное table_name/field_name/plan_value и т.п.), добавляя
        соответствующий warning. Вызывающий должен пропустить None.
        """
        if not isinstance(raw, dict):
            warnings.append(
                f"Запись #{idx}: ожидался объект, получено {type(raw).__name__} — пропущено"
            )
            return None

        table_name = raw.get("table_name")
        field_name = raw.get("field_name")
        if not table_name or not field_name:
            warnings.append(
                f"Запись #{idx}: не указаны table_name/field_name — пропущено"
            )
            return None

        plan_value = self._as_decimal(raw.get("plan_value"))
        if plan_value is None:
            warnings.append(
                f"Запись #{idx} ({table_name}.{field_name}): некорректное plan_value "
                f"({raw.get('plan_value')!r}) — пропущено"
            )
            return None

        period_type = raw.get("period_type")
        if period_type not in ALL_PERIOD_TYPES:
            warnings.append(
                f"Запись #{idx} ({table_name}.{field_name}): неизвестный "
                f"period_type='{period_type}' — пропущено"
            )
            return None

        period_value = raw.get("period_value")
        date_from = self._as_date(raw.get("date_from"))
        date_to = self._as_date(raw.get("date_to"))

        # Normalize empty strings → None for consistency with PlanCreateRequest.
        if isinstance(period_value, str) and not period_value.strip():
            period_value = None

        return {
            "table_name": str(table_name),
            "field_name": str(field_name),
            "assigned_by_id_raw": raw.get("assigned_by_id"),
            "period_type": period_type,
            "period_value": period_value,
            "date_from": date_from,
            "date_to": date_to,
            "plan_value": plan_value,
            "description": raw.get("description"),
        }

    def _build_draft(
        self,
        normalized: dict[str, Any],
        assigned_by_id: Optional[str],
        assigned_by_name: Optional[str],
    ) -> PlanDraft:
        """Build a :class:`PlanDraft` from a normalized record."""
        return PlanDraft(
            assigned_by_id=assigned_by_id,
            assigned_by_name=assigned_by_name,
            table_name=normalized["table_name"],
            field_name=normalized["field_name"],
            period_type=normalized["period_type"],
            period_value=normalized["period_value"],
            date_from=normalized["date_from"],
            date_to=normalized["date_to"],
            plan_value=normalized["plan_value"],
            description=normalized.get("description"),
            warnings=[],
        )

    # ------------------------------------------------------------------
    # Expand — spec values → concrete drafts
    # ------------------------------------------------------------------

    async def _expand_single(
        self,
        normalized: dict[str, Any],
        idx: int,
        warnings: list[str],
        managers_cache: Optional[list[dict[str, Any]]] = None,
    ) -> list[PlanDraft]:
        """Expand ONE normalized raw plan into a list of drafts.

        Supported ``assigned_by_id_raw`` values:

        * ``None`` / empty → one draft with ``assigned_by_id=None`` (global).
        * ``"all_managers"`` → N drafts (one per active user).
        * ``"department:Название"`` → N drafts for managers in that
          department + all descendants (active only).
        * concrete ``bitrix_id`` (str / int) → one draft (user validated
          against ``bitrix_users`` — missing user → warning + skip).
        """
        raw_aid = normalized["assigned_by_id_raw"]

        # --- 1. Global plan --------------------------------------------------
        if raw_aid is None:
            return [self._build_draft(normalized, None, None)]
        if isinstance(raw_aid, str) and not raw_aid.strip():
            return [self._build_draft(normalized, None, None)]

        raw_aid_str = str(raw_aid).strip()

        # --- 2. all_managers --------------------------------------------------
        if raw_aid_str.lower() == "all_managers":
            all_managers = managers_cache if managers_cache is not None else await self._fetch_active_managers()
            # all_managers → только active (inactive исключаем из групповой
            # рассылки; они нужны только для резолва имени в fallback).
            active_only = [m for m in all_managers if m.get("active")]
            if not active_only:
                warnings.append(
                    f"Запись #{idx}: не найдено ни одного активного менеджера "
                    f"в bitrix_users — пропущено"
                )
                return []
            return [
                self._build_draft(
                    normalized,
                    m["bitrix_id"],
                    self._format_manager_name(m),
                )
                for m in active_only
            ]

        # --- 3. department:Name -----------------------------------------------
        if raw_aid_str.lower().startswith("department:"):
            dept_name = raw_aid_str.split(":", 1)[1].strip()
            if not dept_name:
                warnings.append(
                    f"Запись #{idx}: в 'department:' не указано имя отдела — пропущено"
                )
                return []

            root_id = await self._find_department_by_name(dept_name)
            if root_id is None:
                warnings.append(
                    f"Запись #{idx}: отдел '{dept_name}' не найден в "
                    f"bitrix_departments — пропущено"
                )
                return []

            dept_ids = await self._department_service.collect_descendant_ids(root_id)
            if not dept_ids:
                dept_ids = [root_id]

            managers = await self._department_service.list_managers_in_departments(
                dept_ids, active_only=True
            )
            if not managers:
                warnings.append(
                    f"Запись #{idx}: в отделе '{dept_name}' (и подотделах) "
                    f"не найдено активных менеджеров — пропущено"
                )
                return []

            return [
                self._build_draft(
                    normalized,
                    m["bitrix_id"],
                    self._format_manager_name(m),
                )
                for m in managers
            ]

        # --- 4. concrete bitrix_id -------------------------------------------
        # Если похоже на ID (только цифры) — сначала ищем точно по bitrix_id.
        is_numeric_id = raw_aid_str.isdigit()
        if is_numeric_id:
            user = await self._fetch_user_by_id(raw_aid_str)
            if user is not None:
                return [
                    self._build_draft(
                        normalized,
                        user["bitrix_id"],
                        self._format_manager_name(user),
                    )
                ]

        # --- 5. Fallback: имя/фамилия → bitrix_id ----------------------------
        # LLM мог вернуть имя вместо ID (несмотря на инструкции в промпте).
        # Пробуем matcher против списка активных менеджеров.
        managers = managers_cache if managers_cache is not None else await self._fetch_active_managers()
        matched = self._match_manager_by_name(raw_aid_str, managers)
        if matched is not None:
            warnings.append(
                f"Запись #{idx}: assigned_by_id='{raw_aid_str}' резолвлен по имени "
                f"в bitrix_id={matched['bitrix_id']} ({self._format_manager_name(matched)})"
            )
            return [
                self._build_draft(
                    normalized,
                    matched["bitrix_id"],
                    self._format_manager_name(matched),
                )
            ]

        warnings.append(
            f"Запись #{idx}: не удалось определить bitrix_id для "
            f"'{raw_aid_str}'. Проверьте, есть ли такой менеджер в bitrix_users. "
            f"План пропущен — укажите точный bitrix_id или имя из списка."
        )
        return []

    # ------------------------------------------------------------------
    # Validation (via PlanService, no INSERT)
    # ------------------------------------------------------------------

    async def _validate_draft(
        self, draft: PlanDraft
    ) -> Optional[str]:
        """Return a user-friendly error string if draft is invalid, else None.

        Прогоняет через те же проверки, что делает
        :meth:`PlanService.create_plan` — но БЕЗ INSERT'а и БЕ�з проверки
        дубликатов (это решение принимает batch_create_plans при сохранении).
        """
        # Numeric column existence + type.
        try:
            await self._plan_service._validate_numeric_column(
                draft.table_name, draft.field_name
            )
        except PlanValidationError as exc:
            return str(exc)

        # Period mode (fixed vs custom — проверяем вручную через
        # _validate_period, который ожидает dict, чтобы обойти ограничение
        # Pydantic-валидации на PlanDraft).
        payload: dict[str, Any] = {
            "period_type": draft.period_type,
            "period_value": draft.period_value,
            "date_from": draft.date_from,
            "date_to": draft.date_to,
        }
        try:
            self._plan_service._validate_period(payload)
        except PlanValidationError as exc:
            return str(exc)

        # plan_value sanity — positive Decimal (0 допускается, но не None).
        if draft.plan_value is None:
            return "plan_value is required"

        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def expand_ai_drafts(
        self,
        raw_plans: list[Any],
        warnings: Optional[list[str]] = None,
        managers_cache: Optional[list[dict[str, Any]]] = None,
    ) -> tuple[list[PlanDraft], list[str]]:
        """Expand raw LLM drafts → validated ``PlanDraft`` + warnings.

        Args:
            raw_plans: Список сырых dict от
                :meth:`AIService.generate_plans_from_description`. Каждый
                может содержать спец-значения ``assigned_by_id``
                (``"all_managers"`` / ``"department:Name"``).
            warnings: Список warning'ов, уже собранных LLM'ом. В него
                дописываются новые (несуществующий отдел, невалидное поле
                и т.п.). Если ``None`` — создаётся новый список.

        Returns:
            Кортеж ``(drafts, warnings)``:

            * ``drafts`` — отвалидированные :class:`PlanDraft` (готовы
              к ``POST /plans/batch``).
            * ``warnings`` — объединённый список LLM + post-processing
              предупреждений.

        Важно: метод ничего не пишет в БД. Это чистый preview, который
        фронт показывает пользователю перед подтверждением.
        """
        warnings = list(warnings or [])
        drafts: list[PlanDraft] = []

        for idx, raw in enumerate(raw_plans or []):
            normalized = self._normalize_raw_plan(raw, warnings, idx)
            if normalized is None:
                continue

            expanded = await self._expand_single(
                normalized, idx, warnings, managers_cache=managers_cache
            )
            if not expanded:
                continue

            for draft in expanded:
                error = await self._validate_draft(draft)
                if error is not None:
                    warnings.append(
                        f"Запись #{idx} ({draft.table_name}.{draft.field_name}, "
                        f"assigned_by_id={draft.assigned_by_id}): {error} — пропущено"
                    )
                    continue
                drafts.append(draft)

        logger.info(
            "plans_ai: drafts expanded",
            raw_count=len(raw_plans or []),
            drafts_count=len(drafts),
            warnings_count=len(warnings),
        )

        return drafts, warnings

    async def generate_and_expand(
        self,
        description: str,
        schema_context: str,
        hints: Optional[dict[str, Any]] = None,
    ) -> PlanAIGenerateResponse:
        """End-to-end: LLM call + expand + validate → response.

        Прямой путь из endpoint'а ``POST /plans/ai-generate`` в готовый
        ответ :class:`PlanAIGenerateResponse`. Не пишет в БД.
        """
        # Fetch active managers once — переиспользуется и в LLM-контексте,
        # и в expand (как cache для all_managers / name fallback).
        managers = await self._fetch_active_managers()
        managers_context = self._format_managers_context(managers)

        raw_response = await self._ai_service.generate_plans_from_description(
            description=description,
            schema_context=schema_context,
            hints=hints,
            managers_context=managers_context,
        )
        raw_plans = raw_response.get("plans") or []
        llm_warnings = list(raw_response.get("warnings") or [])

        drafts, combined_warnings = await self.expand_ai_drafts(
            raw_plans, warnings=llm_warnings, managers_cache=managers
        )

        return PlanAIGenerateResponse(
            plans=drafts,
            warnings=combined_warnings,
        )
