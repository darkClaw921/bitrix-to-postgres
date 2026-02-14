"""add llm_prompt to ai_report_runs

Revision ID: 013
Revises: 012
Create Date: 2026-02-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '013'
down_revision: Union[str, None] = '012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ai_report_runs', sa.Column('llm_prompt', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('ai_report_runs', 'llm_prompt')
