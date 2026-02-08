"""create chart_prompts_table

Revision ID: 009
Revises: 008
Create Date: 2026-02-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_BITRIX_PROMPT = """# Инструкции по работе с данными Bitrix24 CRM

## Получение конверсии по стадиям сделок

Для расчета конверсии по стадиям воронки сделок необходимо:

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
    # Определяем диалект БД
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Создаем таблицу chart_prompt_templates
    if dialect == 'postgresql':
        op.create_table(
            'chart_prompt_templates',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )
        op.create_index(op.f('ix_chart_prompt_templates_name'), 'chart_prompt_templates', ['name'], unique=False)
    else:  # mysql
        op.create_table(
            'chart_prompt_templates',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )
        op.create_index(op.f('ix_chart_prompt_templates_name'), 'chart_prompt_templates', ['name'], unique=False)

    # Вставляем дефолтный промпт
    op.execute(
        sa.text(
            """
            INSERT INTO chart_prompt_templates (name, content, is_active)
            VALUES (:name, :content, :is_active)
            """
        ).bindparams(
            name='bitrix_context',
            content=DEFAULT_BITRIX_PROMPT,
            is_active=True
        )
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_chart_prompt_templates_name'), table_name='chart_prompt_templates')
    op.drop_table('chart_prompt_templates')
