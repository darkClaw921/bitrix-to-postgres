"""Create dashboard_selectors and selector_chart_mappings tables.

Revision ID: 007
Revises: 006
Create Date: 2026-02-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dashboard_selectors",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "dashboard_id",
            sa.BigInteger(),
            sa.ForeignKey("published_dashboards.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("selector_type", sa.String(30), nullable=False),
        sa.Column("operator", sa.String(30), nullable=False, server_default="equals"),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("dashboard_id", "name", name="uq_dashboard_selector_name"),
    )

    op.create_table(
        "selector_chart_mappings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "selector_id",
            sa.BigInteger(),
            sa.ForeignKey("dashboard_selectors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dashboard_chart_id",
            sa.BigInteger(),
            sa.ForeignKey("dashboard_charts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_column", sa.String(255), nullable=False),
        sa.Column("target_table", sa.String(255), nullable=True),
        sa.Column("operator_override", sa.String(30), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "selector_id", "dashboard_chart_id", name="uq_selector_chart_mapping"
        ),
    )


def downgrade() -> None:
    op.drop_table("selector_chart_mappings")
    op.drop_table("dashboard_selectors")
