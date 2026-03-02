"""stub: revision 014 (migration file was lost, DB already applied)

Revision ID: 014
Revises: 013
Create Date: 2026-03-02

"""

from typing import Union

from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
