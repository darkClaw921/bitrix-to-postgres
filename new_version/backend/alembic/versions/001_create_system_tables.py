"""Create system tables for sync management.

Revision ID: 001
Revises:
Create Date: 2025-02-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # sync_config table
    op.create_table(
        "sync_config",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column(
            "sync_interval_minutes", sa.Integer(), nullable=False, server_default="30"
        ),
        sa.Column(
            "webhook_enabled", sa.Boolean(), nullable=False, server_default="1"
        ),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_type"),
    )
    op.create_index("ix_sync_config_entity_type", "sync_config", ["entity_type"])

    # sync_logs table
    op.create_table(
        "sync_logs",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("sync_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("records_processed", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_logs_entity_type", "sync_logs", ["entity_type"])
    op.create_index("ix_sync_logs_status", "sync_logs", ["status"])

    # sync_state table
    op.create_table(
        "sync_state",
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("last_modified_date", sa.DateTime(), nullable=True),
        sa.Column("last_bitrix_id", sa.String(50), nullable=True),
        sa.Column("total_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("entity_type"),
    )

    # Insert default configurations
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO sync_config (entity_type, enabled, sync_interval_minutes, webhook_enabled) "
            "VALUES ('deal', 1, 30, 1), "
            "       ('contact', 1, 30, 1), "
            "       ('lead', 1, 30, 1), "
            "       ('company', 1, 30, 1)"
        )
    )


def downgrade() -> None:
    op.drop_table("sync_state")
    op.drop_index("ix_sync_logs_status", table_name="sync_logs")
    op.drop_index("ix_sync_logs_entity_type", table_name="sync_logs")
    op.drop_table("sync_logs")
    op.drop_index("ix_sync_config_entity_type", table_name="sync_config")
    op.drop_table("sync_config")
