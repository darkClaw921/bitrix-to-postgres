"""Create plans table for user-defined plan/fact values.

Создаёт таблицу ``plans`` — хранилище пользовательских плановых значений,
которые можно привязывать к любому числовому полю любой таблицы БД
(типичный пример — план по ``opportunity`` в ``crm_deals`` на менеджера за месяц).

Поддерживаются два взаимоисключающих режима периода:

  * фиксированный — ``period_type ∈ (month, quarter, year)`` + ``period_value``
    (например ``2026-04``, ``2026-Q2``, ``2026``);
  * произвольный — ``period_type = 'custom'`` + ``date_from`` / ``date_to``.

Взаимоисключение режимов и дубликат-детекция для NULL-комбинаций
гарантируются на уровне сервиса (PlanService), а ``UniqueConstraint``
оставлен как страховочный инвариант.

Кросс-диалектная миграция: использует только нейтральные типы sqlalchemy,
работает и в PostgreSQL, и в MySQL.

Revision ID: 022
Revises: 021
Create Date: 2026-04-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("table_name", sa.String(length=64), nullable=False),
        sa.Column("field_name", sa.String(length=128), nullable=False),
        sa.Column("assigned_by_id", sa.String(length=32), nullable=True),
        sa.Column("period_type", sa.String(length=16), nullable=True),
        sa.Column("period_value", sa.String(length=16), nullable=True),
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column("plan_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "table_name",
            "field_name",
            "assigned_by_id",
            "period_type",
            "period_value",
            "date_from",
            "date_to",
            name="uq_plan_key",
        ),
    )

    op.create_index(
        "ix_plans_table_field",
        "plans",
        ["table_name", "field_name"],
    )
    op.create_index(
        "ix_plans_assigned_by",
        "plans",
        ["assigned_by_id"],
    )
    op.create_index(
        "ix_plans_period",
        "plans",
        ["period_type", "period_value"],
    )
    op.create_index(
        "ix_plans_dates",
        "plans",
        ["date_from", "date_to"],
    )


def downgrade() -> None:
    op.drop_index("ix_plans_dates", table_name="plans")
    op.drop_index("ix_plans_period", table_name="plans")
    op.drop_index("ix_plans_assigned_by", table_name="plans")
    op.drop_index("ix_plans_table_field", table_name="plans")
    op.drop_table("plans")
