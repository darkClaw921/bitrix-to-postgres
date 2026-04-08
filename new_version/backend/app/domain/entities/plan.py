"""Domain entity for user-defined plan/target values."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


PeriodType = Literal["month", "quarter", "year", "custom"]


class PlanEntity(BaseModel):
    """Internal domain representation of a single row in the ``plans`` table.

    Используется ``PlanService`` как типизированная обёртка над сырыми
    словарями из БД. Поля соответствуют миграции 022 и SQLAlchemy-модели
    ``app.infrastructure.database.models.Plan``.
    """

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    table_name: str
    field_name: str
    assigned_by_id: Optional[str] = None
    period_type: Optional[PeriodType] = None
    period_value: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    plan_value: Decimal
    description: Optional[str] = None
    created_by_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
