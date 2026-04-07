"""Add tab_label column to published_dashboards.

Добавляет опциональное поле ``tab_label`` в таблицу ``published_dashboards``.
Когда заполнено, используется как метка первой (главной) вкладки в публичном
дашборде вместо ``title``. Это позволяет задать короткое название вкладки,
не меняя полного заголовка дашборда.

Revision ID: 018
Revises: 017
Create Date: 2026-04-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "published_dashboards",
        sa.Column("tab_label", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("published_dashboards", "tab_label")
