"""Create dashboard_links table.

Revision ID: 006
Revises: 005
Create Date: 2026-02-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dashboard_links",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "dashboard_id",
            sa.BigInteger(),
            sa.ForeignKey("published_dashboards.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "linked_dashboard_id",
            sa.BigInteger(),
            sa.ForeignKey("published_dashboards.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("dashboard_id", "linked_dashboard_id", name="uq_dashboard_linked"),
    )


def downgrade() -> None:
    op.drop_table("dashboard_links")
