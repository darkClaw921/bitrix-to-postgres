"""Add refresh_interval_minutes to published_dashboards.

Revision ID: 005
Revises: 004
Create Date: 2026-02-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "published_dashboards",
        sa.Column(
            "refresh_interval_minutes",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
    )


def downgrade() -> None:
    op.drop_column("published_dashboards", "refresh_interval_minutes")
