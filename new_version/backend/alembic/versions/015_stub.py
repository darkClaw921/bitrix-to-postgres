"""stub: revision 015 (migration file was lost, DB already applied)

Revision ID: 015
Revises: 014
Create Date: 2026-03-02

"""

from typing import Union

from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
