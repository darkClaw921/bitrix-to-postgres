"""create published reports tables

Revision ID: 012
Revises: 011
Create Date: 2026-02-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '012'
down_revision: Union[str, None] = '011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # === published_reports ===
    if dialect == 'postgresql':
        op.create_table(
            'published_reports',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('slug', sa.String(length=32), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('report_id', sa.BigInteger(), sa.ForeignKey('ai_reports.id', ondelete='CASCADE'), nullable=False),
            sa.Column('password_hash', sa.String(length=255), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('slug'),
        )
    else:
        op.create_table(
            'published_reports',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('slug', sa.String(length=32), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('report_id', sa.BigInteger(), sa.ForeignKey('ai_reports.id', ondelete='CASCADE'), nullable=False),
            sa.Column('password_hash', sa.String(length=255), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('slug'),
        )

    op.create_index('ix_published_reports_slug', 'published_reports', ['slug'], unique=True)
    op.create_index('ix_published_reports_report_id', 'published_reports', ['report_id'])

    # === published_report_links ===
    if dialect == 'postgresql':
        op.create_table(
            'published_report_links',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('published_report_id', sa.BigInteger(), sa.ForeignKey('published_reports.id', ondelete='CASCADE'), nullable=False),
            sa.Column('linked_published_report_id', sa.BigInteger(), sa.ForeignKey('published_reports.id', ondelete='CASCADE'), nullable=False),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('label', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('published_report_id', 'linked_published_report_id', name='uq_published_report_linked'),
        )
    else:
        op.create_table(
            'published_report_links',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('published_report_id', sa.BigInteger(), sa.ForeignKey('published_reports.id', ondelete='CASCADE'), nullable=False),
            sa.Column('linked_published_report_id', sa.BigInteger(), sa.ForeignKey('published_reports.id', ondelete='CASCADE'), nullable=False),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('label', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('published_report_id', 'linked_published_report_id', name='uq_published_report_linked'),
        )


def downgrade() -> None:
    op.drop_table('published_report_links')
    op.drop_index('ix_published_reports_report_id', table_name='published_reports')
    op.drop_index('ix_published_reports_slug', table_name='published_reports')
    op.drop_table('published_reports')
