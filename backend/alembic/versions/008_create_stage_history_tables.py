"""create stage history tables

Revision ID: 008
Revises: 007
Create Date: 2026-02-08
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create stage history tables.

    Note: Tables will be created automatically via DynamicTableBuilder
    when the first sync is triggered.

    This migration serves as a marker that stage_history tables
    are now supported in the system.
    """
    pass


def downgrade() -> None:
    """Drop stage history tables.

    Optionally can add DROP TABLE statements here if needed.
    """
    pass
