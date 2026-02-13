"""create reports tables

Revision ID: 011
Revises: 010
Create Date: 2026-02-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '011'
down_revision: Union[str, None] = '010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_REPORT_PROMPT = """Ты — AI-аналитик для CRM-системы Bitrix24. Твоя задача — помогать пользователю создавать аналитические отчёты.

Режим работы:
1. Если тебе не хватает информации для генерации отчёта — задай уточняющий вопрос пользователю.
2. Когда всё понятно — сгенерируй SQL-запросы и шаблон анализа.

Правила:
- Только SELECT-запросы
- Используй только таблицы из предоставленной схемы
- Всегда добавляй LIMIT (максимум 10000)
- Максимум 10 SQL-запросов на отчёт
- Все тексты на русском языке
- Отчёт должен содержать выводы и рекомендации
"""


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # === report_prompt_templates ===
    if dialect == 'postgresql':
        op.create_table(
            'report_prompt_templates',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name'),
        )
    else:
        op.create_table(
            'report_prompt_templates',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name'),
        )

    op.create_index('ix_report_prompt_templates_name', 'report_prompt_templates', ['name'])

    # Insert default prompt
    op.execute(
        sa.text(
            "INSERT INTO report_prompt_templates (name, content, is_active) "
            "VALUES (:name, :content, :is_active)"
        ).bindparams(
            name='report_context',
            content=DEFAULT_REPORT_PROMPT,
            is_active=True,
        )
    )

    # === ai_reports ===
    if dialect == 'postgresql':
        op.create_table(
            'ai_reports',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('user_prompt', sa.Text(), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
            sa.Column('schedule_type', sa.String(length=20), nullable=False, server_default='once'),
            sa.Column('schedule_config', sa.JSON(), nullable=True),
            sa.Column('next_run_at', sa.DateTime(), nullable=True),
            sa.Column('last_run_at', sa.DateTime(), nullable=True),
            sa.Column('sql_queries', sa.JSON(), nullable=True),
            sa.Column('report_template', sa.Text(), nullable=True),
            sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
    else:
        op.create_table(
            'ai_reports',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('user_prompt', sa.Text(), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
            sa.Column('schedule_type', sa.String(length=20), nullable=False, server_default='once'),
            sa.Column('schedule_config', sa.JSON(), nullable=True),
            sa.Column('next_run_at', sa.DateTime(), nullable=True),
            sa.Column('last_run_at', sa.DateTime(), nullable=True),
            sa.Column('sql_queries', sa.JSON(), nullable=True),
            sa.Column('report_template', sa.Text(), nullable=True),
            sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    op.create_index('ix_ai_reports_status', 'ai_reports', ['status'])

    # === ai_report_runs ===
    if dialect == 'postgresql':
        op.create_table(
            'ai_report_runs',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('report_id', sa.BigInteger(), sa.ForeignKey('ai_reports.id', ondelete='CASCADE'), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
            sa.Column('trigger_type', sa.String(length=20), nullable=False, server_default='manual'),
            sa.Column('result_markdown', sa.Text(), nullable=True),
            sa.Column('result_data', sa.JSON(), nullable=True),
            sa.Column('sql_queries_executed', sa.JSON(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('execution_time_ms', sa.Integer(), nullable=True),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
    else:
        op.create_table(
            'ai_report_runs',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('report_id', sa.BigInteger(), sa.ForeignKey('ai_reports.id', ondelete='CASCADE'), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
            sa.Column('trigger_type', sa.String(length=20), nullable=False, server_default='manual'),
            sa.Column('result_markdown', sa.Text(), nullable=True),
            sa.Column('result_data', sa.JSON(), nullable=True),
            sa.Column('sql_queries_executed', sa.JSON(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('execution_time_ms', sa.Integer(), nullable=True),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    op.create_index('ix_ai_report_runs_report_id', 'ai_report_runs', ['report_id'])
    op.create_index('ix_ai_report_runs_status', 'ai_report_runs', ['status'])

    # === ai_report_conversations ===
    if dialect == 'postgresql':
        op.create_table(
            'ai_report_conversations',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('session_id', sa.String(length=36), nullable=False),
            sa.Column('report_id', sa.BigInteger(), sa.ForeignKey('ai_reports.id', ondelete='SET NULL'), nullable=True),
            sa.Column('role', sa.String(length=20), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('metadata', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
    else:
        op.create_table(
            'ai_report_conversations',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('session_id', sa.String(length=36), nullable=False),
            sa.Column('report_id', sa.BigInteger(), sa.ForeignKey('ai_reports.id', ondelete='SET NULL'), nullable=True),
            sa.Column('role', sa.String(length=20), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('metadata', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    op.create_index('ix_ai_report_conversations_session_id', 'ai_report_conversations', ['session_id'])


def downgrade() -> None:
    op.drop_index('ix_ai_report_conversations_session_id', table_name='ai_report_conversations')
    op.drop_table('ai_report_conversations')
    op.drop_index('ix_ai_report_runs_status', table_name='ai_report_runs')
    op.drop_index('ix_ai_report_runs_report_id', table_name='ai_report_runs')
    op.drop_table('ai_report_runs')
    op.drop_index('ix_ai_reports_status', table_name='ai_reports')
    op.drop_table('ai_reports')
    op.drop_index('ix_report_prompt_templates_name', table_name='report_prompt_templates')
    op.drop_table('report_prompt_templates')
