"""Add hide_title column to dashboard_charts.

Добавляет колонку `hide_title BOOLEAN NOT NULL DEFAULT FALSE` в таблицу
`dashboard_charts`, позволяя скрывать заголовок отдельных элементов
дашборда (особенно полезно для индикаторов).

Кросс-БД: op.add_column с sa.Boolean() генерирует совместимый SQL
как для PostgreSQL, так и для MySQL.

Revision ID: 019
Revises: 018
Create Date: 2026-04-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "dashboard_charts",
        sa.Column(
            "hide_title",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("dashboard_charts", "hide_title")
