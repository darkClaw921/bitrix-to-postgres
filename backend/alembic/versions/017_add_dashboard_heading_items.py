"""Add polymorphic heading items support to dashboard_charts.

Расширяет таблицу `dashboard_charts` для поддержки полиморфных элементов
дашборда (chart | heading) без создания отдельной таблицы.

Изменения схемы:
1. ``item_type VARCHAR(20) NOT NULL DEFAULT 'chart'`` — тип элемента
   (``chart`` для существующих графиков, ``heading`` для текстовых заголовков).
2. ``heading_config JSON NULL`` — конфигурация заголовка
   (text/level/align/colors/divider). Заполняется только для строк,
   у которых ``item_type='heading'``.
3. ``chart_id`` теряет ограничение ``NOT NULL`` — для headings внешний
   ключ на ``ai_charts`` не имеет смысла и должен быть NULL.

Существующие строки автоматически получают ``item_type='chart'`` благодаря
server_default; ``heading_config`` остаётся NULL.

Кросс-БД: реализация для PostgreSQL и MySQL различается через
``op.get_bind().dialect.name`` (тот же подход, что в миграциях
009/011/012).

Revision ID: 017
Revises: 016
Create Date: 2026-04-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # 1. item_type — общий путь, op.add_column генерит совместимый SQL
    #    как для PostgreSQL, так и для MySQL. server_default гарантирует
    #    что существующие строки получат значение 'chart'.
    op.add_column(
        "dashboard_charts",
        sa.Column(
            "item_type",
            sa.String(length=20),
            nullable=False,
            server_default="chart",
        ),
    )

    # 2. heading_config JSON NULL — sa.JSON выбирает корректный тип
    #    (JSONB/JSON для PG, JSON для MySQL 5.7+).
    op.add_column(
        "dashboard_charts",
        sa.Column(
            "heading_config",
            sa.JSON(),
            nullable=True,
        ),
    )

    # 3. Снять NOT NULL с chart_id. Раздельная логика для PG и MySQL,
    #    т.к. MySQL требует явное указание полного типа в MODIFY COLUMN,
    #    а alter_column для существующего FK-столбца — самый безопасный
    #    способ переключить nullable.
    if dialect == "postgresql":
        op.alter_column(
            "dashboard_charts",
            "chart_id",
            existing_type=sa.BigInteger(),
            nullable=True,
        )
    else:  # mysql / mariadb
        op.alter_column(
            "dashboard_charts",
            "chart_id",
            existing_type=sa.BigInteger(),
            nullable=True,
            existing_nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Перед возвращением NOT NULL для chart_id нужно избавиться от
    # строк-headings (у них chart_id = NULL и они не могут существовать
    # в "до-полиморфной" схеме). Безопаснее всего удалить их.
    op.execute(
        sa.text(
            "DELETE FROM dashboard_charts WHERE item_type = 'heading'"
        )
    )

    # Возврат NOT NULL для chart_id.
    if dialect == "postgresql":
        op.alter_column(
            "dashboard_charts",
            "chart_id",
            existing_type=sa.BigInteger(),
            nullable=False,
        )
    else:  # mysql / mariadb
        op.alter_column(
            "dashboard_charts",
            "chart_id",
            existing_type=sa.BigInteger(),
            nullable=False,
            existing_nullable=True,
        )

    # Удаляем добавленные колонки в обратном порядке.
    op.drop_column("dashboard_charts", "heading_config")
    op.drop_column("dashboard_charts", "item_type")
