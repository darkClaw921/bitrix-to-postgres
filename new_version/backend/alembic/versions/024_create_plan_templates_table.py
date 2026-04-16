"""Create plan_templates table and seed a builtin template.

Создаёт таблицу ``plan_templates`` — хранилище шаблонов для массового
создания планов (batch). Шаблон описывает ``period_mode`` (какой период
использовать — текущий месяц/квартал/год или произвольный) и
``assignees_mode`` (для кого создавать планы — все менеджеры, отдел,
конкретные или глобальный план). При "применении" шаблона UI формирует
черновики (``PlanDraft``) и передаёт их в transactional batch-create.

Колонки ``table_name``/``field_name`` сделаны nullable: встроенные
шаблоны (``is_builtin=TRUE``) не привязаны к конкретной таблице/полю
заранее — пользователь выбирает их при применении. Пользовательские
шаблоны обычно заполняют эти поля.

Seed: одна встроенная запись — *"Все менеджеры на текущий месяц"* —
минимальный стартовый шаблон, доступный сразу после миграции. Его
``is_builtin=TRUE`` защищает строку от удаления через API.

Кросс-диалектная миграция: используются только нейтральные типы
sqlalchemy, работает и в PostgreSQL, и в MySQL. Seed делается через
``op.execute`` с параметризованным INSERT — совместимо с обоими
диалектами, не зависит от MetaData/reflection.

Revision ID: 024
Revises: 023
Create Date: 2026-04-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plan_templates",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Цель плана — nullable для встроенных шаблонов без привязки.
        sa.Column("table_name", sa.String(length=64), nullable=True),
        sa.Column("field_name", sa.String(length=128), nullable=True),
        # Режим периода и его параметры.
        sa.Column("period_mode", sa.String(length=32), nullable=False),
        sa.Column("period_type", sa.String(length=16), nullable=True),
        sa.Column("period_value", sa.String(length=16), nullable=True),
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column("date_to", sa.Date(), nullable=True),
        # Режим получателей и его параметры.
        sa.Column("assignees_mode", sa.String(length=32), nullable=False),
        sa.Column("department_name", sa.String(length=255), nullable=True),
        sa.Column("specific_manager_ids", sa.Text(), nullable=True),
        # Значение плана по умолчанию (может быть переопределено в UI).
        sa.Column("default_plan_value", sa.Numeric(18, 2), nullable=True),
        # Системные поля.
        sa.Column(
            "is_builtin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
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
    )

    op.create_index(
        "ix_plan_templates_is_builtin",
        "plan_templates",
        ["is_builtin"],
    )

    # --- Seed встроенного шаблона ---
    # Используем параметризованный INSERT через op.execute(sa.text(...)) —
    # cross-dialect-safe (PG и MySQL). Колонки ``created_at``/``updated_at``
    # проставятся через server_default=NOW(), поэтому их не указываем.
    op.execute(
        sa.text(
            "INSERT INTO plan_templates "
            "(name, description, period_mode, assignees_mode, is_builtin) "
            "VALUES ("
            ":name, :description, :period_mode, :assignees_mode, :is_builtin"
            ")"
        ).bindparams(
            sa.bindparam("name", "Все менеджеры на текущий месяц"),
            sa.bindparam(
                "description",
                "Создать индивидуальный план для каждого активного "
                "менеджера на текущий календарный месяц",
            ),
            sa.bindparam("period_mode", "current_month"),
            sa.bindparam("assignees_mode", "all_managers"),
            sa.bindparam("is_builtin", True),
        )
    )


def downgrade() -> None:
    op.drop_index("ix_plan_templates_is_builtin", table_name="plan_templates")
    op.drop_table("plan_templates")
