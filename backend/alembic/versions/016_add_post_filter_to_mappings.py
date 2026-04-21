"""Add post_filter columns to selector_chart_mappings.

Adds three optional columns that enable two-step (post_filter) selector
filtering: when a chart's table does not contain the column to filter by,
the selector value is resolved through an auxiliary table.

Generated SQL becomes::

    WHERE target_column IN (
        SELECT post_filter_resolve_id_column
        FROM post_filter_resolve_table
        WHERE post_filter_resolve_column <op> :value
    )

Revision ID: 016
Revises: 015
Create Date: 2026-04-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "selector_chart_mappings",
        sa.Column("post_filter_resolve_table", sa.String(255), nullable=True),
    )
    op.add_column(
        "selector_chart_mappings",
        sa.Column("post_filter_resolve_column", sa.String(255), nullable=True),
    )
    op.add_column(
        "selector_chart_mappings",
        sa.Column("post_filter_resolve_id_column", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("selector_chart_mappings", "post_filter_resolve_id_column")
    op.drop_column("selector_chart_mappings", "post_filter_resolve_column")
    op.drop_column("selector_chart_mappings", "post_filter_resolve_table")
