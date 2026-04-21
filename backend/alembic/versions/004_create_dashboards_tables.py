"""Create published_dashboards and dashboard_charts tables.

Revision ID: 004
Revises: 003
Create Date: 2026-02-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "published_dashboards",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("slug", sa.String(32), nullable=False, unique=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default="1"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_published_dashboards_slug", "published_dashboards", ["slug"], unique=True)

    op.create_table(
        "dashboard_charts",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("dashboard_id", sa.BigInteger(), nullable=False),
        sa.Column("chart_id", sa.BigInteger(), nullable=False),
        sa.Column("title_override", sa.String(255), nullable=True),
        sa.Column("description_override", sa.Text(), nullable=True),
        sa.Column("layout_x", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("layout_y", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("layout_w", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("layout_h", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["dashboard_id"],
            ["published_dashboards.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["chart_id"],
            ["ai_charts.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_dashboard_charts_unique",
        "dashboard_charts",
        ["dashboard_id", "chart_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_dashboard_charts_unique", table_name="dashboard_charts")
    op.drop_table("dashboard_charts")
    op.drop_index("ix_published_dashboards_slug", table_name="published_dashboards")
    op.drop_table("published_dashboards")
