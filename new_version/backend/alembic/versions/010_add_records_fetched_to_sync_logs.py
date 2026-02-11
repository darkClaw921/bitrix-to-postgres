"""Add records_fetched column to sync_logs.

Revision ID: 010
Revises: 009
Create Date: 2026-02-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sync_logs",
        sa.Column("records_fetched", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sync_logs", "records_fetched")
