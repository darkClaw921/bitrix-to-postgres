"""Update bitrix_context prompt: add transition date-create filter block.

Идемпотентно добавляет блок про фильтр по дате создания сделки на чартах
переходов (раздел «Конверсия между стадиями (переходы)» → подсекция
«Фильтр по дате создания сделки на чартах переходов») в существующую
запись ``chart_prompt_templates`` WHERE ``name = 'bitrix_context'`` для
существующих инсталляций.

Идемпотентность обеспечивается проверкой якорной фразы
«Фильтр по дате создания сделки на чартах переходов» в текущем
``content``: если фраза уже есть — UPDATE затрагивает 0 строк (no-op),
ручные правки администратора не теряются.

Кросс-диалектная миграция: используется ``op.get_bind().dialect.name``
для выбора синтаксиса конкатенации:
- PostgreSQL: ``content || :new_block``
- MySQL: ``CONCAT(content, :new_block)``

Текст блока синхронизирован с ``DEFAULT_BITRIX_PROMPT`` из миграции
``009_create_chart_prompts_table.py`` (раздел «Конверсия между стадиями
(переходы)» → подсекция «Фильтр по дате создания сделки на чартах
переходов»), чтобы оба места были консистентны.

Revision ID: 025
Revises: 024
Create Date: 2026-04-28

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Якорная фраза для проверки идемпотентности: если она уже есть в content —
# блок не добавляется повторно. Ручные правки админа не теряются.
ANCHOR_PHRASE: str = "Фильтр по дате создания сделки на чартах переходов"


# Новый блок, который добавляется в конец существующего content. Текст
# дословно совпадает с подсекцией, добавленной в DEFAULT_BITRIX_PROMPT
# в миграции 009_create_chart_prompts_table.py (раздел «Конверсия между
# стадиями (переходы)» → подсекция «Фильтр по дате создания сделки на
# чартах переходов»). Ведущие \n\n обеспечивают визуальный отступ от
# предыдущего раздела при склейке.
NEW_BLOCK: str = """

### Фильтр по дате создания сделки на чартах переходов

**ВАЖНО**: stage_history_deals.created_time — дата перехода сделки между стадиями/воронками. crm_deals.date_create — дата создания самой сделки. Это разные вещи.

Если пользователь хочет «сделки, созданные в периоде X-Y, которые перешли из воронки A в воронку B» — ВСЕГДА JOIN crm_deals и фильтруй по d.date_create, а не по sh.created_time:

```sql
SELECT COUNT(DISTINCT sh1.owner_id) AS deals_count
FROM stage_history_deals sh1
JOIN stage_history_deals sh2 ON sh1.owner_id = sh2.owner_id
  AND sh2.created_time = (
    SELECT MIN(created_time)
    FROM stage_history_deals
    WHERE owner_id = sh1.owner_id AND created_time > sh1.created_time
  )
JOIN crm_deals d ON d.bitrix_id = sh1.owner_id
JOIN ref_crm_deal_categories c1 ON sh1.category_id = c1.id
JOIN ref_crm_deal_categories c2 ON sh2.category_id = c2.id
WHERE c1.name = 'Продажа'
  AND c2.name = 'Досудебные'
  AND d.date_create BETWEEN :date_from AND :date_to
```

Сами переходы между воронками детектируются через type_id = 5 ИЛИ через смену category_id между соседними записями истории. По умолчанию — фильтруй по category_id исходной/целевой воронки (надёжнее, чем type_id = 5, на случай неполных данных истории).

Для лидов работает по аналогии: подменяем crm_deals → crm_leads и category_id → status_id (через ref_crm_statuses).
"""


def upgrade() -> None:
    """Идемпотентно добавляет NEW_BLOCK в content существующей записи
    chart_prompt_templates WHERE name='bitrix_context', если якорная фраза
    ещё не присутствует. Поддерживает PostgreSQL (||) и MySQL (CONCAT).
    """
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        # PG: оператор || для конкатенации текста; NOW() для updated_at.
        update_sql = (
            "UPDATE chart_prompt_templates "
            "SET content = content || :new_block, "
            "    updated_at = NOW() "
            "WHERE name = 'bitrix_context' "
            "  AND content NOT LIKE :anchor_pattern"
        )
    else:
        # MySQL: CONCAT(content, :new_block); NOW() работает в обоих диалектах.
        update_sql = (
            "UPDATE chart_prompt_templates "
            "SET content = CONCAT(content, :new_block), "
            "    updated_at = NOW() "
            "WHERE name = 'bitrix_context' "
            "  AND content NOT LIKE :anchor_pattern"
        )

    op.execute(
        sa.text(update_sql).bindparams(
            sa.bindparam("new_block", NEW_BLOCK),
            sa.bindparam("anchor_pattern", f"%{ANCHOR_PHRASE}%"),
        )
    )


def downgrade() -> None:
    """Удаляет ровно тот блок, который добавил upgrade(), через REPLACE.

    REPLACE — стандартная функция в PostgreSQL и MySQL, поэтому
    диалект-специфичной логики не требуется. Если блока нет в content
    (был удалён вручную, или upgrade не запускался) — REPLACE no-op,
    миграция не падает. updated_at обновляется через NOW().
    """
    op.execute(
        sa.text(
            "UPDATE chart_prompt_templates "
            "SET content = REPLACE(content, :new_block, ''), "
            "    updated_at = NOW() "
            "WHERE name = 'bitrix_context'"
        ).bindparams(
            sa.bindparam("new_block", NEW_BLOCK),
        )
    )
