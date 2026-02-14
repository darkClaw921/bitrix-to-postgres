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
- Всегда получаей человеческие названия значений полей из таблицы со списком значений полей ref_enum_values или пользователей из таблицы bitrix_users никогда не работай просто с ID значениями


# Инструкции по работе с данными Bitrix24 CRM

- названия столбцов дложны быть всегда в человеческим виде и на русском языке
- сделки считаются закрытыми если у них stage_semantic_id = 'F' или 'S' 
- не используй поле closed
все sql запросы не должны быть написаны в одну строчку.
- если пользователь просит данные в человеческрм виде то возможно эти данные можно получить из таблицы со списком значений полей 



## лид считаеться качественным если он имеет статус status_semantic_id = 'S' или status_id = 'CONVERTED'
## лид считаеться не качественным если он имеет статус status_semantic_id = 'F' или status_id = 'JUNK'

## сделки и лиды которые были или находившиеся в какой-то стадии это значит что бы должны смотреть также таблицы с историей движения этих сущностей
## Получение конверсии по стадиям сделок

чтобы получить данные по конкретной воронки можно использовать WHERE d.category_id = (SELECT id FROM ref_crm_deal_categories WHERE name = 'Продажа клиенту')
Для расчета конверсии по стадиям воронки сделок необходимо:



## справка по задачам
REAL_STATUS — статус задачи.
2 — ждет выполнения
3 — выполняется
4 — ожидает контроля
5 — завершена
6 — отложена
STATUS — статус для сортировки. Аналогичен REAL_STATUS, но имеет три дополнительных мета-статуса:
-3 — задача почти просрочена
-2 — не просмотренная задача
-1 — просроченная задача

## примеры запросов
# конверия сделок по определенным стадиям и воронке 
SELECT s.name AS stage_name, COUNT(d.bitrix_id) AS deal_count
FROM crm_deals d
JOIN stage_history_deals sh ON d.bitrix_id = sh.owner_id
JOIN ref_crm_statuses s ON sh.stage_id = s.status_id
WHERE d.category_id = (SELECT id FROM ref_crm_deal_categories WHERE name = 'Продажа клиенту')
  AND s.name IN ('Новая сделка', 'КП отправлено', 'Счет/договор отправлены', 'Согласовано/договор подписан')
GROUP BY s.name
ORDER BY s.sort
LIMIT 10000

# Причины отказов сделок с человеческими названиями значений полей
SELECT
  ev.value AS reason,
  COUNT(d.bitrix_id) AS deal_count
FROM crm_deals d
JOIN ref_enum_values ev ON d.uf_crm_1674660872571 = ev.item_id
WHERE d.stage_semantic_id = 'F'
GROUP BY ev.value
ORDER BY deal_count DESC
LIMIT 10000

1. Использовать таблицу `crm_deals` для получения списка сделок
2. Использовать таблицу `stage_history_deals` для получения истории движения сделок по стадиям
3. Объединить их по `bitrix_id` (crm_deals) = `owner_id` (stage_history_deals)
4. Использовать таблицу `ref_crm_statuses` для получения названий стадий

Пример расчета конверсии:
- Количество сделок, достигших стадии N = COUNT(DISTINCT owner_id WHERE stage_semantic_id = 'N')
- Конверсия в стадию N = (Кол-во в стадии N / Общее кол-во сделок) * 100

## Получение воронки продаж

Для построения воронки продаж:

1. Посчитать количество сделок на каждой стадии из `crm_deals`
2. Объединить с `ref_crm_statuses` для получения названий стадий
3. Упорядочить по `sort` из ref_crm_statuses

```sql
SELECT
  s.name as stage_name,
  COUNT(d.bitrix_id) as deal_count,
  s.sort
FROM crm_deals d
LEFT JOIN ref_crm_statuses s ON d.stage_id = s.status_id
GROUP BY s.name, s.sort
ORDER BY s.sort
LIMIT 10000
```

## Получение времени в стадиях

Для расчета среднего времени пребывания сделок в стадиях:

1. Использовать `stage_history_deals` для получения истории переходов
2. Вычислить разницу между `created_time` соседних записей для одной сделки
3. Сгруппировать по стадиям

```sql
SELECT
  s.name as stage_name,
  AVG(TIMESTAMPDIFF(SECOND, sh.created_time, sh2.created_time)) / 86400 as avg_days
FROM stage_history_deals sh
LEFT JOIN stage_history_deals sh2 ON sh.owner_id = sh2.owner_id
  AND sh2.created_time > sh.created_time
LEFT JOIN ref_crm_statuses s ON sh.stage_id = s.status_id
GROUP BY s.name
LIMIT 10000
```

## Конверсия между стадиями (переходы)

**ВАЖНО**: При анализе переходов между стадиями НИКОГДА не используйте прямой JOIN между stage_history_deals сама с собой без подзапроса - это создаст огромное декартово произведение и вызовет timeout!

**ПРАВИЛЬНЫЙ подход** - использовать подзапрос для получения следующей стадии:

```sql
SELECT
  CONCAT(s1.name, ' → ', s2.name) AS stage_transition,
  COUNT(*) AS transition_count
FROM stage_history_deals sh1
JOIN stage_history_deals sh2 ON sh1.owner_id = sh2.owner_id
  AND sh2.created_time = (
    SELECT MIN(created_time)
    FROM stage_history_deals
    WHERE owner_id = sh1.owner_id
      AND created_time > sh1.created_time
  )
JOIN ref_crm_statuses s1 ON sh1.stage_id = s1.status_id
JOIN ref_crm_statuses s2 ON sh2.stage_id = s2.status_id
WHERE s1.name != s2.name
GROUP BY s1.name, s2.name, s1.sort, s2.sort
ORDER BY s1.sort, s2.sort
LIMIT 10000
```

Для исключения определённых стадий добавьте условие в WHERE:
```sql
WHERE s1.name != s2.name
  AND s1.name != 'Счёт на предоплату'
  AND s2.name != 'Счёт на предоплату'
```

## Получение успешности менеджеров

Для анализа эффективности менеджеров:

1. Использовать поле `assigned_by_id` из `crm_deals` для идентификации ответственного
2. Фильтровать по `closed` = 1 и `stage_semantic_id` = 'S' (успешные сделки)
3. Суммировать `opportunity` для расчета суммы сделок
4. Использовать таблицу `bitrixusers` для получения названий менеджеров
```sql
SELECT
  assigned_by_id as manager_id,
  COUNT(*) as total_deals,
  COUNT(CASE WHEN closed = 1 AND stage_semantic_id = 'S' THEN 1 END) as won_deals,
  SUM(CASE WHEN closed = 1 AND stage_semantic_id = 'S' THEN opportunity ELSE 0 END) as total_revenue
FROM crm_deals
GROUP BY assigned_by_id
ORDER BY total_revenue DESC
LIMIT 10000
```

## Работа со справочниками

- **Статусы/стадии**: `ref_crm_statuses` - содержит все стадии для всех сущностей (сделки, лиды, контакты)
- **Воронки сделок**: `ref_crm_deal_categories` - список воронок
- **Валюты**: `ref_crm_currencies` - список валют
- **Значения enum-полей**: `ref_enum_values` - возможные значения пользовательских полей типа список

## Пользовательские поля

Пользовательские поля имеют префикс `uf_crm_`:
- Для получения возможных значений списочных полей используйте `ref_enum_values`
- Соединение: `ref_enum_values.field_name = 'UF_CRM_...'` AND `ref_enum_values.entity_type = 'DEAL'` (или другая сущность)

## Важные идентификаторы

- `bitrix_id` - уникальный ID сущности в Bitrix24 (используется для связей)
- `id` - автоинкрементный ID в локальной БД (не использовать для связей с Bitrix24)
- `owner_id` в `stage_history_deals` = `bitrix_id` в `crm_deals`

## Типы записей в истории стадий

В таблице `stage_history_deals` поле `type_id` означает:
- 1 = создание элемента
- 2 = промежуточная стадия
- 3 = финальная стадия
- 5 = смена воронки

Поле `stage_semantic_id`:
- P = промежуточная стадия
- S = успешная (выиграно)
- F = провальная (проиграно)
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
