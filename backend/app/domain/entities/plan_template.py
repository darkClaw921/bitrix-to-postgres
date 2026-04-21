"""Domain entity for plan templates (``plan_templates`` table).

Чистая доменная модель шаблона для массового создания планов. Шаблон
описывает:

* **режим периода** (``period_mode``) — один из
  ``current_month`` / ``current_quarter`` / ``current_year`` / ``custom_period``;
  для ``custom_period`` используются ``period_type`` / ``period_value``
  или ``date_from`` / ``date_to`` в стиле ``plans.period_type``.
* **режим получателей** (``assignees_mode``) — один из
  ``all_managers`` / ``department`` / ``specific`` / ``global``.
  Для ``department`` хранится ``department_name`` (имя отдела в
  ``bitrix_departments.name``), для ``specific`` — JSON-массив
  bitrix_id менеджеров в ``specific_manager_ids``.

``table_name``/``field_name`` сделаны опциональными: встроенные шаблоны
(``is_builtin=True``) не привязаны к конкретной цели и получают её при
применении (override-ы в ``PlanTemplateApplyRequest``).

``specific_manager_ids`` хранится в БД как JSON text, но в entity уже
типизирован как ``list[str] | None`` — JSON-десериализация происходит в
``PlanTemplateService`` при чтении из БД (и сериализация — при записи).

Аналог :mod:`app.domain.entities.plan` (``PlanEntity``) — тоже Pydantic
``BaseModel`` с ``ConfigDict(from_attributes=True)``, чтобы удобно
конвертировать сырые словари из БД в типизированные объекты через
``model_validate``.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


PeriodMode = Literal[
    "current_month",
    "current_quarter",
    "current_year",
    "custom_period",
]

AssigneesMode = Literal[
    "all_managers",
    "department",
    "specific",
    "global",
]

TemplatePeriodType = Literal["month", "quarter", "year", "custom"]


class PlanTemplateEntity(BaseModel):
    """Internal domain representation of one row in ``plan_templates``.

    Используется ``PlanTemplateService`` как типизированная обёртка над
    сырыми словарями из БД. Поля соответствуют миграции 024.
    ``specific_manager_ids`` уже распарсен из JSON в ``list[str]``.
    """

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    name: str
    description: Optional[str] = None

    # Цель плана — nullable для builtin без привязки.
    table_name: Optional[str] = None
    field_name: Optional[str] = None

    # Период.
    period_mode: PeriodMode
    period_type: Optional[TemplatePeriodType] = None
    period_value: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None

    # Получатели.
    assignees_mode: AssigneesMode
    department_name: Optional[str] = None
    specific_manager_ids: Optional[list[str]] = None

    # Значение плана по умолчанию.
    default_plan_value: Optional[Decimal] = None

    # Системные поля.
    is_builtin: bool = False
    created_by_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
