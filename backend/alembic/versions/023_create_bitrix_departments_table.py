"""Create bitrix_departments and bitrix_user_departments tables.

Создаёт две таблицы для хранения структуры отделов Bitrix24:

1) ``bitrix_departments`` — справочник отделов, копируемый из ``department.get``.
   Каждая запись соответствует одному отделу (или подразделению) в Bitrix24
   со ссылкой на родителя (``parent_id``) и опциональным руководителем
   (``uf_head`` — bitrix_id пользователя).

2) ``bitrix_user_departments`` — junction-таблица связи юзеров и отделов
   (массив ``UF_DEPARTMENT`` из ``user.get`` раскладывается по строкам).
   Один юзер может принадлежать нескольким отделам; PK по
   ``(user_id, department_id)`` даёт естественный UNIQUE и защищает от
   дублей при повторной синхронизации юзеров.

Кросс-диалектная миграция: использует только нейтральные типы sqlalchemy,
работает и в PostgreSQL, и в MySQL. PK auto_increment создаётся через
``sa.BigInteger()`` + ``autoincrement=True``.

Revision ID: 023
Revises: 022
Create Date: 2026-04-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- bitrix_departments: справочник отделов ---
    op.create_table(
        "bitrix_departments",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("bitrix_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("parent_id", sa.String(length=32), nullable=True),
        sa.Column("sort", sa.Integer(), nullable=True, server_default="500"),
        sa.Column("uf_head", sa.String(length=32), nullable=True),
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
        sa.UniqueConstraint("bitrix_id", name="uq_bitrix_departments_bitrix_id"),
    )

    op.create_index(
        "ix_bitrix_departments_parent",
        "bitrix_departments",
        ["parent_id"],
    )

    # --- bitrix_user_departments: junction user <-> department ---
    op.create_table(
        "bitrix_user_departments",
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("department_id", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint(
            "user_id", "department_id", name="pk_bitrix_user_departments"
        ),
    )

    op.create_index(
        "ix_bud_user",
        "bitrix_user_departments",
        ["user_id"],
    )
    op.create_index(
        "ix_bud_dept",
        "bitrix_user_departments",
        ["department_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_bud_dept", table_name="bitrix_user_departments")
    op.drop_index("ix_bud_user", table_name="bitrix_user_departments")
    op.drop_table("bitrix_user_departments")

    op.drop_index(
        "ix_bitrix_departments_parent", table_name="bitrix_departments"
    )
    op.drop_table("bitrix_departments")
