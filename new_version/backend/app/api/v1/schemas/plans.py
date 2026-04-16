"""Pydantic schemas for plan (target value) endpoints.

Covers the request/response shapes used by ``/api/v1/plans`` — CRUD,
plan-vs-actual, batch-create, plan templates (CRUD + expand + apply),
AI-generated drafts and the small meta-endpoints (``/meta/tables``,
``/meta/numeric-fields``, ``/meta/managers``).

The request validators mirror the logic in
``app.domain.services.plan_service.PlanService._validate_period`` so that
obviously invalid payloads fail fast at the HTTP boundary.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Shared constants (must stay in sync with PlanService / PlanTemplateService)
# ---------------------------------------------------------------------------


FIXED_PERIOD_TYPES: frozenset[str] = frozenset({"month", "quarter", "year"})
ALL_PERIOD_TYPES: frozenset[str] = FIXED_PERIOD_TYPES | {"custom"}

# Template-level period modes (см. PlanTemplateEntity.period_mode).
ALL_PERIOD_MODES: frozenset[str] = frozenset(
    {"current_month", "current_quarter", "current_year", "custom_period"}
)

# Template-level assignee modes (см. PlanTemplateEntity.assignees_mode).
ALL_ASSIGNEES_MODES: frozenset[str] = frozenset(
    {"all_managers", "department", "specific", "global"}
)


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class PlanCreateRequest(BaseModel):
    """Payload to create a new plan row.

    Exactly one of the two period modes must be provided:

    * **fixed** — ``period_type ∈ {month, quarter, year}`` + ``period_value``
      (e.g. ``"2026-04"``, ``"2026-Q2"``, ``"2026"``).
    * **custom** — ``period_type == "custom"`` + ``date_from`` + ``date_to``.
    """

    table_name: str = Field(..., min_length=1, max_length=64)
    field_name: str = Field(..., min_length=1, max_length=128)
    assigned_by_id: Optional[str] = Field(
        None,
        max_length=32,
        description="Manager id; NULL means a plan for everyone.",
    )
    period_type: str = Field(
        ...,
        description="One of: month, quarter, year, custom.",
    )
    period_value: Optional[str] = Field(
        None,
        max_length=16,
        description="Required for fixed period_type; NULL for 'custom'.",
    )
    date_from: Optional[date] = Field(
        None, description="Required for period_type='custom'."
    )
    date_to: Optional[date] = Field(
        None, description="Required for period_type='custom'."
    )
    plan_value: Decimal = Field(..., description="Planned numeric value.")
    description: Optional[str] = None
    created_by_id: Optional[str] = Field(None, max_length=32)

    @model_validator(mode="after")
    def _validate_period_mode(self) -> "PlanCreateRequest":
        if self.period_type not in ALL_PERIOD_TYPES:
            raise ValueError(
                f"period_type must be one of {sorted(ALL_PERIOD_TYPES)}, "
                f"got '{self.period_type}'"
            )

        if self.period_type in FIXED_PERIOD_TYPES:
            if not self.period_value:
                raise ValueError(
                    f"period_value is required for period_type='{self.period_type}'"
                )
            if self.date_from is not None or self.date_to is not None:
                raise ValueError(
                    "date_from/date_to must be NULL for fixed period_type "
                    f"'{self.period_type}'"
                )
        else:  # custom
            if self.date_from is None or self.date_to is None:
                raise ValueError(
                    "date_from and date_to are required for period_type='custom'"
                )
            if self.period_value:
                raise ValueError(
                    "period_value must be NULL for period_type='custom'"
                )
            if self.date_to < self.date_from:
                raise ValueError("date_to must be >= date_from")
        return self


class PlanUpdateRequest(BaseModel):
    """Payload to update an existing plan.

    All fields are optional: the service performs a partial update when
    only ``plan_value`` / ``description`` are sent, and a full update
    (re-validating the logical key) when any of the key fields are
    present.

    For a full update, the period-mode invariant is verified inside
    ``PlanService.update_plan`` against the merged row, so this schema
    intentionally does not run the same ``model_validator`` as
    ``PlanCreateRequest``.
    """

    table_name: Optional[str] = Field(None, min_length=1, max_length=64)
    field_name: Optional[str] = Field(None, min_length=1, max_length=128)
    assigned_by_id: Optional[str] = Field(None, max_length=32)
    period_type: Optional[str] = None
    period_value: Optional[str] = Field(None, max_length=16)
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    plan_value: Optional[Decimal] = None
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class PlanResponse(BaseModel):
    """A single plan row as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    table_name: str
    field_name: str
    assigned_by_id: Optional[str] = None
    period_type: Optional[str] = None
    period_value: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    plan_value: Decimal
    description: Optional[str] = None
    created_by_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PlanVsActualResponse(BaseModel):
    """Plan vs actual snapshot for a single plan.

    ``variance = actual_value - plan_value``. ``variance_pct`` is ``None`` when
    ``plan_value == 0`` to avoid division-by-zero on the client.
    ``period_effective_from`` / ``period_effective_to`` are the concrete
    ``[from, to)`` bounds used for the SUM, materialised from
    ``period_type``/``period_value`` (or copied from ``date_from``/``date_to``
    for custom periods).
    """

    plan_id: int
    plan_value: Decimal
    actual_value: Decimal
    variance: Decimal
    variance_pct: Optional[float] = None
    period_effective_from: date
    period_effective_to: date


class NumericFieldInfo(BaseModel):
    """A single numeric column descriptor returned by /meta/numeric-fields."""

    name: str
    data_type: str


class NumericFieldsResponse(BaseModel):
    """Response of /meta/numeric-fields."""

    table_name: str
    fields: list[NumericFieldInfo]


class TableInfo(BaseModel):
    """A single table descriptor returned by /meta/tables."""

    name: str
    label: Optional[str] = None


class TablesResponse(BaseModel):
    """Response of /meta/tables."""

    tables: list[TableInfo]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def plan_row_to_response(row: dict[str, Any]) -> PlanResponse:
    """Convert a raw ``plans`` row (dict) into a ``PlanResponse``.

    ``PlanService`` returns plain dicts via ``_row_to_dict``; this helper
    centralises the conversion so endpoints stay thin.
    """
    return PlanResponse.model_validate(row)


# ---------------------------------------------------------------------------
# Plan templates — CRUD requests
# ---------------------------------------------------------------------------


class PlanTemplateCreateRequest(BaseModel):
    """Payload to create a plan template.

    ``period_mode`` и ``assignees_mode`` ограничены заранее известными
    литералами через :data:`ALL_PERIOD_MODES` / :data:`ALL_ASSIGNEES_MODES`.
    Встроенные шаблоны (``is_builtin=True``) создаются только миграцией
    024 — этот запрос всегда создаёт пользовательский шаблон, поэтому
    ``is_builtin`` в payload не принимается. Создателя проставляет сервис
    из JWT (``created_by_id``), поэтому клиент его тоже не передаёт.

    Поля режимов связаны между собой (например ``specific_manager_ids``
    обязателен при ``assignees_mode='specific'``) — кросс-поля проверяются
    в ``model_validator(mode='after')``.
    """

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None

    # Цель плана (опциональна — builtin без привязки).
    table_name: Optional[str] = Field(None, min_length=1, max_length=64)
    field_name: Optional[str] = Field(None, min_length=1, max_length=128)

    # Период.
    period_mode: str = Field(
        ...,
        description=(
            "One of: current_month, current_quarter, current_year, "
            "custom_period."
        ),
    )
    period_type: Optional[str] = Field(
        None,
        description=(
            "Required when period_mode='custom_period'; one of month/"
            "quarter/year/custom."
        ),
    )
    period_value: Optional[str] = Field(None, max_length=16)
    date_from: Optional[date] = None
    date_to: Optional[date] = None

    # Получатели.
    assignees_mode: str = Field(
        ...,
        description=(
            "One of: all_managers, department, specific, global."
        ),
    )
    department_name: Optional[str] = Field(None, max_length=255)
    specific_manager_ids: Optional[list[str]] = None

    # Значение по умолчанию.
    default_plan_value: Optional[Decimal] = None

    @field_validator("period_mode")
    @classmethod
    def _check_period_mode(cls, v: str) -> str:
        if v not in ALL_PERIOD_MODES:
            raise ValueError(
                f"period_mode must be one of {sorted(ALL_PERIOD_MODES)}, "
                f"got '{v}'"
            )
        return v

    @field_validator("assignees_mode")
    @classmethod
    def _check_assignees_mode(cls, v: str) -> str:
        if v not in ALL_ASSIGNEES_MODES:
            raise ValueError(
                f"assignees_mode must be one of {sorted(ALL_ASSIGNEES_MODES)}, "
                f"got '{v}'"
            )
        return v

    @model_validator(mode="after")
    def _check_cross_fields(self) -> "PlanTemplateCreateRequest":
        # period_type — корректные значения при custom_period.
        if self.period_mode == "custom_period":
            if self.period_type is None:
                raise ValueError(
                    "period_type is required when period_mode='custom_period'"
                )
            if self.period_type not in ALL_PERIOD_TYPES:
                raise ValueError(
                    f"period_type must be one of {sorted(ALL_PERIOD_TYPES)}, "
                    f"got '{self.period_type}'"
                )
        else:
            # period_type / period_value / даты не имеют смысла для
            # current_* — сервис всё равно пересчитает их при expand.
            pass

        # assignees cross-check.
        if self.assignees_mode == "department" and not self.department_name:
            raise ValueError(
                "department_name is required when assignees_mode='department'"
            )
        if self.assignees_mode == "specific":
            if not self.specific_manager_ids:
                raise ValueError(
                    "specific_manager_ids is required when "
                    "assignees_mode='specific'"
                )
        return self


class PlanTemplateUpdateRequest(BaseModel):
    """Payload for partial update of an existing template.

    Все поля опциональны — сервис патчит только переданные. Изменение
    ``is_builtin`` запрещено и на уровне схемы (поле отсутствует), и на
    уровне сервиса (дополнительная проверка перед UPDATE).
    """

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None

    table_name: Optional[str] = Field(None, min_length=1, max_length=64)
    field_name: Optional[str] = Field(None, min_length=1, max_length=128)

    period_mode: Optional[str] = None
    period_type: Optional[str] = None
    period_value: Optional[str] = Field(None, max_length=16)
    date_from: Optional[date] = None
    date_to: Optional[date] = None

    assignees_mode: Optional[str] = None
    department_name: Optional[str] = Field(None, max_length=255)
    specific_manager_ids: Optional[list[str]] = None

    default_plan_value: Optional[Decimal] = None

    @field_validator("period_mode")
    @classmethod
    def _check_period_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALL_PERIOD_MODES:
            raise ValueError(
                f"period_mode must be one of {sorted(ALL_PERIOD_MODES)}, "
                f"got '{v}'"
            )
        return v

    @field_validator("assignees_mode")
    @classmethod
    def _check_assignees_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALL_ASSIGNEES_MODES:
            raise ValueError(
                f"assignees_mode must be one of {sorted(ALL_ASSIGNEES_MODES)}, "
                f"got '{v}'"
            )
        return v


class PlanTemplateResponse(BaseModel):
    """A single plan template row as returned by the API.

    Зеркалит ``PlanTemplateEntity``: ``specific_manager_ids`` уже список
    строк (десериализован из JSON сервисом).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None

    table_name: Optional[str] = None
    field_name: Optional[str] = None

    period_mode: str
    period_type: Optional[str] = None
    period_value: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None

    assignees_mode: str
    department_name: Optional[str] = None
    specific_manager_ids: Optional[list[str]] = None

    default_plan_value: Optional[Decimal] = None

    is_builtin: bool = False
    created_by_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Plan drafts (preview / apply)
# ---------------------------------------------------------------------------


class PlanDraft(BaseModel):
    """Preview entry produced by ``PlanTemplateService.expand_template``.

    Служит двум целям:

    1) Ответ ``POST /plans/templates/{id}/expand`` — UI показывает
       пользователю черновики и даёт отредактировать ``plan_value`` /
       ``description`` перед массовым сохранением.
    2) Вход ``PlanTemplateApplyRequest.entries`` — те же поля (уже после
       правок) конвертируются в ``PlanCreateRequest`` и уходят в
       ``batch_create_plans``.

    ``warnings`` — мягкие предупреждения от сервиса (например «менеджер
    X не активен», «уже существует план для этой комбинации»). Не
    блокируют сохранение, но UI их подсвечивает.
    """

    assigned_by_id: Optional[str] = None
    assigned_by_name: Optional[str] = None

    table_name: str = Field(..., min_length=1, max_length=64)
    field_name: str = Field(..., min_length=1, max_length=128)

    period_type: str = Field(..., description="One of: month, quarter, year, custom.")
    period_value: Optional[str] = Field(None, max_length=16)
    date_from: Optional[date] = None
    date_to: Optional[date] = None

    plan_value: Optional[Decimal] = None
    description: Optional[str] = None

    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Batch create + template apply
# ---------------------------------------------------------------------------


class PlanBatchCreateRequest(BaseModel):
    """Payload of ``POST /plans/batch`` — транзакционный batch create.

    ``plans`` — список уже отвалидированных Pydantic'ом записей
    (каждая отдельно проходит period-mode валидацию ``PlanCreateRequest``).
    Backend оборачивает INSERT'ы в один ``begin()``: при любом
    исключении (duplicate key, validation, DB error) вся транзакция
    откатывается — партического успеха нет.
    """

    plans: list[PlanCreateRequest] = Field(..., min_length=1)


class PlanTemplateApplyRequest(BaseModel):
    """Payload of ``POST /plans/templates/{template_id}/apply``.

    После ``POST /expand`` UI получает предварительные ``PlanDraft``,
    даёт пользователю отредактировать значения, затем присылает их
    обратно в ``entries`` вместе с опциональными override-ами цели
    (``table_name`` / ``field_name``) — эндпоинт маппит их в
    ``PlanCreateRequest`` и вызывает :func:`PlanService.batch_create_plans`.

    ``template_id`` здесь дублирует path-параметр эндпоинта — это
    upfront-защита от случайного применения не того шаблона (сервис
    сверяет их).
    """

    template_id: int = Field(..., gt=0)

    table_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=64,
        description=(
            "Override для template.table_name (обязателен для builtin "
            "без привязки)."
        ),
    )
    field_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=128,
        description=(
            "Override для template.field_name (обязателен для builtin "
            "без привязки)."
        ),
    )
    period_value_override: Optional[str] = Field(
        None,
        max_length=16,
        description=(
            "Override вычисленного period_value (например, чтобы задать "
            "конкретный месяц/квартал/год вместо текущего)."
        ),
    )

    entries: list[PlanDraft] = Field(..., min_length=1)


class PlanTemplateExpandRequest(BaseModel):
    """Payload of ``POST /plans/templates/{template_id}/expand``.

    Используется, чтобы UI мог переопределить ``table_name`` /
    ``field_name`` (критично для builtin шаблонов с NULL-привязкой) и
    подставить конкретный ``period_value`` при необходимости.

    Все поля опциональны: если не заданы — используются значения из
    шаблона.
    """

    table_name: Optional[str] = Field(None, min_length=1, max_length=64)
    field_name: Optional[str] = Field(None, min_length=1, max_length=128)
    period_value: Optional[str] = Field(None, max_length=16)


# ---------------------------------------------------------------------------
# AI-generated plans
# ---------------------------------------------------------------------------


class PlanAIGenerateRequest(BaseModel):
    """Payload of ``POST /plans/ai/generate`` (Phase 3).

    ``description`` — текстовая просьба пользователя в свободной форме
    («Поставь план по выручке 500к каждому менеджеру отдела продаж на
    следующий квартал»). LLM разбирает её в структурированный набор
    ``PlanDraft``. Необязательные ``table_name`` / ``field_name``
    подсказывают модели конкретную цель, когда пользователь не указал
    её явно.
    """

    description: str = Field(..., min_length=5, max_length=4000)
    table_name: Optional[str] = Field(None, min_length=1, max_length=64)
    field_name: Optional[str] = Field(None, min_length=1, max_length=128)


class PlanAIGenerateResponse(BaseModel):
    """Response of ``POST /plans/ai/generate`` (Phase 3).

    ``plans`` — черновики, которые фронт показывает пользователю перед
    сохранением через ``POST /plans/batch``. ``warnings`` — общие
    предупреждения, не привязанные к конкретному draft'у.
    """

    plans: list[PlanDraft] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Meta — managers (filtered by department)
# ---------------------------------------------------------------------------


class PlanManagerInfo(BaseModel):
    """Менеджер, возвращаемый ``GET /plans/meta/managers``."""

    bitrix_id: str
    name: Optional[str] = None
    last_name: Optional[str] = None
    active: Optional[str] = None


class PlanManagersResponse(BaseModel):
    """Response of ``GET /plans/meta/managers``.

    ``department_id`` отражает query-фильтр (или None если не задан),
    ``recursive`` — включались ли подотделы при выборке.
    """

    department_id: Optional[str] = None
    recursive: bool = False
    managers: list[PlanManagerInfo] = Field(default_factory=list)
