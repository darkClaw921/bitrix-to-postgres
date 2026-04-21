"""Add title_font_size_override column to dashboard_charts.

Добавляет колонку `title_font_size_override VARCHAR(10) NULL DEFAULT NULL`
в таблицу `dashboard_charts`, позволяя задавать размер заголовка
индивидуально для каждого элемента дашборда.

Кросс-БД: op.add_column с sa.String(10) генерирует совместимый SQL
как для PostgreSQL, так и для MySQL.

Revision ID: 020
Revises: 019
Create Date: 2026-04-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "dashboard_charts",
        sa.Column(
            "title_font_size_override",
            sa.String(length=10),
            nullable=True,
            server_default=None,
        ),
    )


def downgrade() -> None:
    op.drop_column("dashboard_charts", "title_font_size_override")
