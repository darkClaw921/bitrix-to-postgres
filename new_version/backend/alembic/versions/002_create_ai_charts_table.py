"""Create ai_charts table for storing AI-generated charts.

Revision ID: 002
Revises: 001
Create Date: 2026-02-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_charts",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("user_prompt", sa.Text(), nullable=False),
        sa.Column("chart_type", sa.String(50), nullable=False),
        sa.Column("chart_config", sa.JSON(), nullable=False),
        sa.Column("sql_query", sa.Text(), nullable=False),
        sa.Column(
            "is_pinned", sa.Boolean(), nullable=False, server_default="0"
        ),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_charts_chart_type", "ai_charts", ["chart_type"])
    op.create_index("ix_ai_charts_created_at", "ai_charts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_charts_created_at", table_name="ai_charts")
    op.drop_index("ix_ai_charts_chart_type", table_name="ai_charts")
    op.drop_table("ai_charts")
