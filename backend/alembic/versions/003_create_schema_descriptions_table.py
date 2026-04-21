"""Create schema_descriptions table for storing generated schema documentation.

Revision ID: 003
Revises: 002
Create Date: 2026-02-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "schema_descriptions",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("entity_filter", sa.Text(), nullable=True),
        sa.Column(
            "include_related", sa.Boolean(), nullable=False, server_default="1"
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_schema_descriptions_created_at", "schema_descriptions", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_schema_descriptions_created_at", table_name="schema_descriptions"
    )
    op.drop_table("schema_descriptions")
