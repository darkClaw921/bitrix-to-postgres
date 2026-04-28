"""AI service for interaction with OpenAI API."""

import json
import re
from datetime import date
from typing import Any

import openai
from openai import AsyncOpenAI
from sqlalchemy import text

from app.config import get_settings
from app.core.exceptions import AIServiceError
from app.core.logging import get_logger
from app.domain.services.plan_service import PlanService
from app.infrastructure.database.connection import get_engine

logger = get_logger(__name__)

CHART_SQL_REFINE_PROMPT = """You are a SQL query refactoring assistant for a CRM analytics dashboard.
You will receive the CURRENT SQL query of an existing chart and a natural-language
INSTRUCTION describing what the user wants changed. Your job is to return a
single updated SELECT query that satisfies the instruction.

Available database schema:
{schema_context}

{bitrix_context}

Current SQL query:
```sql
{current_sql}
```

User instruction (highest priority — this is what to change):
{instruction}

## Rules
1. ONLY use SELECT statements — no INSERT, UPDATE, DELETE, DROP, ALTER, CREATE.
2. ONLY reference tables from the schema above.
3. Always include LIMIT (max 10000 rows).
4. Use standard SQL compatible with both PostgreSQL and MySQL.
5. Preserve the chart's general shape when possible (same aggregate / grouping
   structure) — change ONLY what the user asked for. Do not rename output
   columns unless the user asked for it, otherwise the saved chart's
   chart_config (data_keys, colors) will break.
6. For aggregations, always use GROUP BY.
7. MySQL CAST compatibility: use CHAR (not varchar) inside CAST.
8. MySQL identifier quoting: backticks for aliases with spaces or Cyrillic.
9. Все сущности из Битрикса обращай по bitrix_id.

## Output format
Return ONLY a JSON object with a single key, no markdown, no commentary:
{{
  "sql_query": "SELECT ..."
}}
"""

CHART_SYSTEM_PROMPT = """You are a SQL query and chart configuration generator for a CRM analytics dashboard.

Available database schema:
{schema_context}

{bitrix_context}

Your task: generate a JSON object with the following fields:
- title (string): short chart title in Russian
- chart_type (string): one of bar, line, pie, area, scatter, indicator, table, funnel, horizontal_bar
- sql_query (string): a SELECT-only SQL query using ONLY the tables listed above
- data_keys (object): {{x: "column_name", y: "column_name"}} or {{x: "column_name", y: ["col1", "col2"]}} for multi-series
- colors (array of strings): hex color codes for chart series, e.g. ["#8884d8", "#82ca9d"]
- description (string): brief description of what the chart shows, in Russian
- chart_config (object, optional): free-form chart config. Currently the only
  structurally-interpreted key is `plan_fact` — see the "Таблица планов (plans)"
  section below for details. Include `chart_config.plan_fact` ONLY when the user
  asks for a plan-vs-fact report; for regular charts omit `chart_config` entirely.
  Shape of plan_fact:
  {{
    "plan_fact": {{
      "table_name": "<fact table, e.g. crm_deals>",
      "field_name": "<numeric fact column, e.g. opportunity>",
      "date_column": "<date column in table_name — always date_create (plan/fact uses record creation date)>",
      "group_by_column": "<optional: assigned_by_id when fact is grouped by managers; omit for a single total>"
    }}
  }}

Rules:
1. ONLY use SELECT statements — no INSERT, UPDATE, DELETE, DROP, ALTER, CREATE
2. ONLY reference tables from the schema above
3. Always include LIMIT (max 10000 rows)
4. Use standard SQL compatible with both PostgreSQL and MySQL
5. For aggregations, always use GROUP BY
6. Return valid JSON only
7. Все сущности из битрикса ты должен обращаться по bitrix_id так как это уникальный идентификатор в битриксе
8. For chart_type "indicator": SQL must return exactly ONE row with a single aggregate value. data_keys.y is the value column. Used for KPI cards showing a single metric.
9. For chart_type "table": SQL returns tabular data with all columns displayed. data_keys.x is not required. All columns from the query result will be shown in the table.
10. For chart_type "funnel": SQL must return stages with names and values, ordered from largest to smallest. data_keys.x is the stage name column, data_keys.y is the value column. Used for sales funnels, conversion funnels.
11. For chart_type "horizontal_bar": same as "bar" but for scenarios with long category names or rankings. data_keys.x is the category column, data_keys.y is the value column. The bars are rendered horizontally.
12. MySQL CAST compatibility: use CHAR (not varchar) inside CAST — correct: CAST(col AS CHAR), wrong: CAST(col AS varchar)
13. MySQL identifier quoting: use backticks for column aliases with spaces or Cyrillic characters — correct: COUNT(*) AS `Количество`, wrong: COUNT(*) AS "Количество". Also use backticks in ORDER BY when referencing aliases: ORDER BY `Количество` DESC
14. Plan-vs-fact charts use POST-ENRICHMENT, not a JOIN on `plans`. When the user
    asks for a plan/fact report, return `chart_config.plan_fact` as described above
    AND include both columns in data_keys (e.g. `"data_keys": {{"x": ["actual", "plan"], "y": "manager"}}`).
    The backend will inject the `plan` column into each row after executing your
    `sql_query`. Your SQL must contain ONLY the fact — NO `LEFT JOIN plans`, NO
    subqueries against `plans`, NO hard-coded period/manager constants in WHERE.
    See the "Таблица планов (plans)" section below for full rules and a canonical
    example.
"""

REPORT_SYSTEM_PROMPT = """Ты — AI-аналитик для CRM-системы Bitrix24. Твоя задача — помогать пользователю создавать аналитические отчёты на основе данных из базы данных.

Доступная схема базы данных:
{schema_context}

{report_context}

## Режим работы

Ты ведёшь диалог с пользователем. На каждом шаге ты ДОЛЖЕН вернуть JSON одного из двух типов:

### Тип 1: Уточняющий вопрос (когда нужна доп. информация)
```json
{{
  "is_complete": false,
  "question": "Ваш вопрос пользователю на русском языке"
}}
```

### Тип 2: Готовый отчёт (когда всё понятно)
```json
{{
  "is_complete": true,
  "title": "Название отчёта",
  "description": "Краткое описание",
  "sql_queries": [
    {{"sql": "SELECT ...", "purpose": "Описание что получаем"}},
    {{"sql": "SELECT ...", "purpose": "Описание что получаем"}}
  ],
  "analysis_prompt": "Инструкция для анализа полученных данных и генерации текста отчёта"
}}
```

## Правила
1. ТОЛЬКО SELECT-запросы
2. ТОЛЬКО таблицы из схемы выше
3. Всегда добавляй LIMIT (максимум 10000)
4. Максимум 10 SQL-запросов на отчёт
5. Все тексты на русском
6. Возвращай ТОЛЬКО валидный JSON
7. Если запрос пользователя слишком расплывчатый — задай уточняющий вопрос
8. SQL-запросы должны быть оптимальными и не вызывать таймаутов

## Критические правила по статусам задач (bitrix_tasks)
- Поля real_status и status содержат ЧИСЛА, а не строки. НИКОГДА не сравнивай с текстом вроде 'Завершена', 'Выполняется'
- real_status: 2=ждёт выполнения, 3=выполняется, 4=ожидает контроля, 5=завершена, 6=отложена
- status (с мета-статусами): -3=почти просрочена, -2=непросмотренная, -1=просроченная
- Просроченные задачи: WHERE status = -1 (не WHERE status = 'Просрочена')
- Завершённые задачи: WHERE real_status = 5

## Критические правила по комментариям задач (bitrix_tasks)
- Поле new_comments_count ВСЕГДА равно 0 после синхронизации (это счётчик непрочитанных, который сбрасывается в реальном времени)
- Для анализа коммуникаций используй поле comments_count (общее число комментариев к задаче)
- Пример: доля задач с хотя бы одним комментарием = COUNT(CASE WHEN comments_count > 0 THEN 1 END)
"""

REPORT_ANALYSIS_PROMPT = """Ты — аналитик данных. Проанализируй результаты запросов и напиши аналитический отчёт в формате Markdown для руководителя.

Отчёт: {report_title}

{report_context}

Исходный запрос пользователя:
{user_prompt}

Результаты запросов:
{sql_results_text}

{analysis_prompt}

Требования к отчёту:
- Пиши на русском языке
- Используй заголовки, списки, таблицы Markdown
- Включи ключевые показатели и метрики
- Сделай выводы и рекомендации
- ЗАПРЕЩЕНО включать SQL-запросы в текст отчёта — отчёт читает руководитель, технические детали не нужны
- ЗАПРЕЩЕНО цитировать поля "SQL:", "Запрос N:" из входных данных — используй только смысловые названия ("Активность по задачам", "Топ создателей" и т.п.)
- Если данные выглядят некорректно (все нули при большом объёме, подозрительные значения) — явно укажи, что данные требуют проверки, не выдавай нули за реальный результат
- Не упоминай технические термины: таблицы БД, поля, SQL, запросы, ошибки парсинга
"""

SELECTORS_GENERATE_PROMPT = """You are an analytics dashboard expert. Given the SQL of every chart on a dashboard
plus the database schema, generate a list of useful selectors (filters) that the
end user can apply to all relevant charts.

Database schema:
{schema_context}

Charts on the dashboard:
{charts_context}
{user_request_block}
Return JSON with this exact shape (no markdown, no commentary):

{{
  "selectors": [
    {{
      "name": "snake_case_id",
      "label": "Человеко-читаемое название на русском",
      "selector_type": "date_range|single_date|dropdown|multi_select|text",
      "operator": "equals|not_equals|in|not_in|between|gt|lt|gte|lte|like|not_like",
      "config": {{
        "default_value": "TODAY|LAST_7_DAYS|LAST_30_DAYS|... or {{from, to}} or null",
        "source_table": "table_name (for dropdown/multi_select pulled from DB)",
        "source_column": "column_name",
        "label_table": "optional join table for human labels",
        "label_column": "optional label column",
        "label_value_column": "optional join key on the label table",
        "static_values": [{{"value": "v", "label": "L"}}]
      }},
      "mappings": [
        {{
          "dashboard_chart_id": <int>,
          "target_column": "column_in_chart_sql",
          "target_table": "optional table qualifier",
          "operator_override": "optional",
          "post_filter_resolve_table": "optional auxiliary table",
          "post_filter_resolve_column": "optional column to filter by inside the auxiliary table",
          "post_filter_resolve_id_column": "optional id column whose values plug into target_column"
        }}
      ]
    }}
  ]
}}

## Rules

1. Use ONLY tables/columns from the schema and chart SQLs above.
2. **selector_type → operator pairing:**
   - `date_range` → `between`
   - `single_date` → `equals` (or `gte`/`lte`)
   - `dropdown` → `equals`
   - `multi_select` → `in`
   - `text` → `like`
3. **Date tokens** (use these for `default_value` of date selectors):
   `TODAY`, `YESTERDAY`, `TOMORROW`, `LAST_7_DAYS`, `LAST_14_DAYS`, `LAST_30_DAYS`,
   `LAST_90_DAYS`, `THIS_MONTH_START`, `LAST_MONTH_START`, `THIS_QUARTER_START`,
   `LAST_QUARTER_START`, `THIS_YEAR_START`, `LAST_YEAR_START`.
   For `date_range` use `{{"from": "LAST_30_DAYS", "to": "TODAY"}}`.
4. **`mappings` is the source of truth for selector → chart links.** Only create
   a mapping when `target_column` actually exists in that chart's SQL output.
5. **Use `post_filter_*` ONLY when `target_column` exists in the chart's table
   but the selector's value semantically refers to a different (related) table.**
   Example: a chart over `stage_history_deals` (which has `owner_id`) needs to
   be filtered by manager. The selector loads managers from `crm_users`, so the
   mapping is: `target_column: "owner_id"`,
   `post_filter_resolve_table: "crm_deals"`,
   `post_filter_resolve_column: "assigned_by_id"`,
   `post_filter_resolve_id_column: "id"`.
   The generated SQL becomes
   `WHERE owner_id IN (SELECT id FROM crm_deals WHERE assigned_by_id = :p)`.
5a. **Чарты переходов между стадиями/воронками (FROM stage_history_deals / stage_history_leads).**
   Если на дашборде есть чарт по `stage_history_deals` и пользователь хочет
   фильтр **по дате создания сделки** (а не по дате перехода) — генерируй
   `date_range` селектор с маппингом `post_filter` через `crm_deals.date_create`:
   ```json
   {{
     "target_column": "owner_id",
     "target_table": "stage_history_deals",
     "post_filter_resolve_table": "crm_deals",
     "post_filter_resolve_column": "date_create",
     "post_filter_resolve_id_column": "bitrix_id"
   }}
   ```
   Это даст SQL
   `WHERE sh.owner_id IN (SELECT bitrix_id FROM crm_deals WHERE date_create BETWEEN :p_from AND :p_to)`.
   **Никогда не маппь** «дату создания сделки» на `stage_history_deals.created_time` —
   это дата перехода, не дата создания сделки.
   Аналогично для лидов: чарт по `stage_history_leads` →
   `target_column: "owner_id"`, `target_table: "stage_history_leads"`,
   `post_filter_resolve_table: "crm_leads"`,
   `post_filter_resolve_column: "date_create"`,
   `post_filter_resolve_id_column: "bitrix_id"`.
6. For `dropdown`/`multi_select`, prefer DB-backed options (`source_table` +
   `source_column`) over `static_values`. **Always populate `label_table` /
   `label_column` / `label_value_column` when the source column is an ID** so
   the dropdown shows human-readable names instead of raw numbers:
   - manager / responsible / assigned_by_id → join `bitrix_users` on
     `bitrix_id`, label `CONCAT_WS(' ', name, last_name)` (set
     `label_column: "name"` and the resolver will fall back smartly).
   - stage_id → join `ref_crm_statuses` on `status_id`, label `name`.
   - category_id → join `ref_crm_deal_categories` on `id`, label `name`.
   - currency_id → join `ref_crm_currencies` on `currency`, label `full_name`.
   When the selector pulls directly from `bitrix_users` (e.g.
   `source_table: "bitrix_users"`, `source_column: "bitrix_id"`), set
   `label_table: "bitrix_users"`, `label_value_column: "bitrix_id"`,
   `label_column: "last_name"`.
7. **Always set `target_table`** on every mapping. Without it, an unqualified
   `created_time` (or any common column) becomes ambiguous when the chart
   joins the same table twice.
8. Generate at most 6 selectors. Pick the most universally useful ones for
   THIS dashboard given its charts.
9. All `label` values in Russian. All `name` values in snake_case English.
10. Return valid JSON only — no comments, no trailing commas.
11. **If a "User request" block is present above, treat it as the highest priority
    instruction.** Generate selectors that match what the user described — their
    requested fields, filter types, and operators take precedence over your own
    suggestions. You may still add a couple of obvious extras if the user did not
    explicitly forbid it, but never drop or substitute selectors the user asked for.
"""

MAPPING_REGENERATE_PROMPT = """You are an analytics dashboard expert. Generate the optimal selector→chart
MAPPING for ONE specific chart on a dashboard. The user has clicked an existing
selector-to-chart connection and asks you to (re)build it correctly.

Database schema:
{schema_context}

All charts on the dashboard (so you can compare and copy filter logic from
sibling charts when the user references them by title):
{charts_context}

Target chart: dashboard_chart_id={target_dc_id}

Selector meta (the selector that this mapping belongs to):
  name: {sel_name}
  label: {sel_label}
  selector_type: {sel_type}
  operator: {sel_operator}

User request (highest priority — may reference another chart by title, e.g.
"посмотри как сделан фильтр у графика X"):
{user_request}

Return JSON ONLY (no markdown fences, no commentary), exactly this shape:
{{
  "target_column": "column_in_target_chart_sql_or_base_table",
  "target_table": "optional table qualifier or null",
  "operator_override": "optional override or null",
  "post_filter_resolve_table": "optional or null",
  "post_filter_resolve_column": "optional or null",
  "post_filter_resolve_id_column": "optional or null"
}}

## Rules
1. `target_column` MUST exist on the TARGET chart's base table (or be the column
   you want to filter by inside the chart's logical scope).
2. **`post_filter_*` triple is REQUIRED** when `target_column` lives in the
   chart's table but the selector value semantically belongs to a different
   (related) table. Otherwise omit (null).
   - Manager selector over a chart on `stage_history_deals` →
     `target_column: "owner_id"`, `target_table: "stage_history_deals"`,
     `post_filter_resolve_table: "crm_deals"`,
     `post_filter_resolve_column: "assigned_by_id"`,
     `post_filter_resolve_id_column: "id"`.
   - **Date of deal CREATION** (not transition) for a chart on
     `stage_history_deals` →
     `target_column: "owner_id"`, `target_table: "stage_history_deals"`,
     `post_filter_resolve_table: "crm_deals"`,
     `post_filter_resolve_column: "date_create"`,
     `post_filter_resolve_id_column: "bitrix_id"`.
   - Same pattern for `stage_history_leads` → resolve via `crm_leads`.
3. **Never** map "дата создания сделки" onto `stage_history_deals.created_time` —
   that is the transition date, not the creation date.
4. **NEVER** apply a `between` operator with date values directly to an integer
   column like `owner_id` / `*_id`. If the operator is `between`/`gte`/`lte` and
   the chart's table is a transition/history table, you MUST use `post_filter_*`
   to redirect the date comparison to a date column.
5. **Always set `target_table`** when the chart joins the same physical table
   twice or when the column name is ambiguous.
6. If the chart's outer SELECT wraps logic in a subquery
   (`SELECT ... FROM (SELECT ...) t`), prefer a `target_column` that is exposed
   by that outer SELECT — the runtime cannot reach inner aliases.
7. If the user request references a sibling chart ("look how filter is set in
   chart X"), find that chart in the list above, infer its filter pattern from
   its SQL/columns, and copy it onto the TARGET chart's mapping.
8. Return null (JSON null, not the string "null") for any optional field that
   does not apply. Return only the JSON object — no extra text.
"""

SCHEMA_DESCRIPTION_PROMPT = """You are a database documentation specialist for a Bitrix24 CRM system.

Analyze the following database schema and generate a detailed markdown documentation in Russian.

Database schema:
{schema_context}

For each table, provide:
## Table name
Brief description of what the table stores.

| Field | Type | Description |
|-------|------|-------------|
| field_name | data_type | Business meaning of this field in the context of Bitrix24 CRM |

Make descriptions clear and useful for business users who are not developers.
Use your knowledge of Bitrix24 CRM fields to provide accurate descriptions.
"""


PLANS_GENERATION_PROMPT = """Ты — AI-ассистент для генерации планов (целевых значений) в CRM-системе Bitrix24.
Пользователь описывает в свободной форме, какие планы он хочет поставить — по каким
таблицам/полям, на каких менеджеров (или на всех, или на отдел), за какой период,
с какими значениями. Твоя задача — разобрать описание и вернуть СТРОГО JSON со списком
черновиков планов и списком предупреждений.

Сегодняшняя дата: {current_date}

## Доступная схема базы данных (только отсюда можно брать table_name / field_name)
{schema_context}

## Менеджеры (bitrix_users) — для резолвинга имён в bitrix_id
Столбец «Активен» показывает флаг active. Для план-генерации используй ЛЮБОГО
найденного менеджера (даже с «Активен=нет»), но добавь warning если он неактивен.
Если пользователь назвал имя и оно есть в таблице — ВСЕГДА подставляй его
`bitrix_id`, НЕ ставь `null` с отговоркой «не найден».

{managers_context}

## Подсказки пользователя (приоритетнее, но не обязательны)
{hints}

## Формат ответа (строго JSON, без markdown-кодблоков, без комментариев)

{{
  "plans": [
    {{
      "table_name": "string — имя таблицы из схемы выше",
      "field_name": "string — имя ЧИСЛОВОГО поля этой таблицы",
      "assigned_by_id": "string | null",
      "period_type": "month | quarter | year | custom",
      "period_value": "string | null",
      "date_from": "YYYY-MM-DD | null",
      "date_to": "YYYY-MM-DD | null",
      "plan_value": 0,
      "description": "string — краткое описание плана на русском"
    }}
  ],
  "warnings": ["string", ...]
}}

## Правила для assigned_by_id

`assigned_by_id` может принимать одно из следующих значений — backend развернёт
спец-значения сам, тебе не нужно выписывать список менеджеров вручную:

- конкретный bitrix_id менеджера (строка): `"123"` — если пользователь назвал
  менеджера по имени/фамилии, найди его в разделе «Активные менеджеры» выше
  и подставь ТОЧНЫЙ `bitrix_id`. Регистр и падеж имени не важны: «Максима
  Крылова», «Крылову Максиму», «М. Крылов» — всё это один и тот же менеджер.
  Если в списке активных менеджеров есть несколько с похожим именем —
  выбери наиболее подходящего и добавь пояснение в `warnings`. Если совсем
  не нашёл — добавь warning и поставь `null` (общий план) ИЛИ пропусти запись.
- `"all_managers"` — если пользователь сказал «на всех менеджеров», «каждому
  менеджеру» и т.п. Backend развернёт это в N планов, по одному на каждого
  активного пользователя из `bitrix_users`.
- `"department:Название"` — если пользователь сказал «всем из отдела Продажи»,
  «менеджерам отдела маркетинга» и т.п. Подставь точное название отдела, как
  его назвал пользователь (регистр не важен — backend сравнит case-insensitive).
  Backend найдёт отдел в `bitrix_departments` и развернёт план на всех
  активных пользователей этого отдела (и всех подотделов).
- `null` — если план общий на всю компанию (без привязки к менеджеру).

НЕ перечисляй менеджеров вручную, если пользователь сказал «на всех» или «отделу»
— используй спец-значения выше.

## Правила для period_type / period_value

Строго соблюдай формат `period_value` в зависимости от `period_type`:

- `period_type = "month"` → `period_value = "YYYY-MM"` (например, `"2026-04"`).
  `date_from` / `date_to` должны быть `null`.
- `period_type = "quarter"` → `period_value = "YYYY-QN"`, где N от 1 до 4
  (например, `"2026-Q2"`). `date_from` / `date_to` — `null`.
- `period_type = "year"` → `period_value = "YYYY"` (например, `"2026"`).
  `date_from` / `date_to` — `null`.
- `period_type = "custom"` → `period_value` должно быть `null`,
  а `date_from` и `date_to` обязательны (формат `"YYYY-MM-DD"`).

«Следующий квартал», «текущий год», «в апреле» и т.п. разрешай относительно
сегодняшней даты `{current_date}`. Если период не указан явно — по умолчанию
используй текущий месяц: `period_type="month"`, `period_value = текущий YYYY-MM`.

## Правила для table_name / field_name

1. Используй ТОЛЬКО реальные таблицы и поля из схемы выше — НИКОГДА не придумывай
   имена. Если в схеме нет поля, к которому пользователь хочет привязать план —
   добавь предупреждение в `warnings` и пропусти этот план.
2. `field_name` должно быть ЧИСЛОВЫМ полем (numeric / integer / decimal / float).
   План-значение — это число, которое сравнивается с суммой этого поля по записям
   за период. Нечисловые поля (text, date, bool) для плана не подходят.
3. Если пользователь подсказал в `hints` конкретные `table_name` / `field_name` —
   используй их (если они существуют и числовые).
4. Типичные случаи (но не хардкодь, сверяйся со схемой):
   - выручка / оборот / сумма сделок → `crm_deals.opportunity`.
   - количество сделок / звонков / задач — соответствующая таблица с числовым
     счётчиком/полем.

## Правила для plan_value

`plan_value` — число (int или float). Если пользователь пишет «500 тысяч» — ставь
`500000`, «2 миллиона» → `2000000`, «50к» → `50000`. НЕ добавляй строки, валюту,
единицы измерения в значение — только число.

## Правила для warnings

Помещай в `warnings` всё, что не смог распознать уверенно:

- неоднозначность поля или таблицы («пользователь сказал \"по выручке\", взял
  `crm_deals.opportunity`, но в схеме есть также `crm_deals.cost` — проверьте»);
- не найденное имя отдела («отдел \"Маркетинг\" не найден в схеме — backend
  попробует его зарезолвить, но возможно имя записано иначе»);
- пропущенные обязательные параметры («не указан период — использую текущий
  месяц»);
- любые сомнительные допущения.

Если описание пользователя слишком расплывчатое и разобрать его в конкретные
планы невозможно — верни пустой `plans` и поясни проблему в `warnings`.

## Обязательные требования к формату ответа

- Верни СТРОГО валидный JSON-объект с двумя ключами `plans` и `warnings`.
- БЕЗ markdown-кодблоков (без ``` ... ```), БЕЗ комментариев, БЕЗ текста до или
  после JSON.
- Все строки — на русском языке (кроме идентификаторов таблиц/полей и
  `period_value`).
- Даже если планов нет — верни `{{"plans": [], "warnings": [...]}}`.
"""


def _extract_json(content: str) -> str:
    """Extract JSON from model response, handling markdown code blocks.

    Newer models may wrap JSON in ```json ... ``` even without response_format.
    Tries: raw JSON → ```json block → ``` block → first {...} substring.
    """
    content = content.strip()
    # Already raw JSON
    if content.startswith("{") or content.startswith("["):
        return content
    # ```json ... ``` block
    m = re.search(r"```json\s*([\s\S]+?)\s*```", content)
    if m:
        return m.group(1).strip()
    # ``` ... ``` block
    m = re.search(r"```\s*([\s\S]+?)\s*```", content)
    if m:
        return m.group(1).strip()
    # First {...} substring as fallback
    m = re.search(r"\{[\s\S]+\}", content)
    if m:
        return m.group(0)
    return content


class AIService:
    """Service for generating chart specs and schema descriptions.

    Uses an OpenAI-compatible client. The actual provider is selected via
    ``settings.llm_provider`` (``openai`` or ``openrouter``); both speak the
    same wire format, so a single ``AsyncOpenAI`` instance with the right
    ``base_url`` covers both. For OpenRouter, attribution headers
    (``HTTP-Referer`` / ``X-Title``) are sent if configured.
    """

    def __init__(self, plan_service: "PlanService | None" = None) -> None:
        settings = get_settings()

        default_headers: dict[str, str] = {}
        if settings.llm_provider == "openrouter":
            if settings.openrouter_app_url:
                default_headers["HTTP-Referer"] = settings.openrouter_app_url
            if settings.openrouter_app_title:
                default_headers["X-Title"] = settings.openrouter_app_title

        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.resolved_llm_base_url,
            timeout=settings.openai_timeout_seconds,
            default_headers=default_headers or None,
        )
        self.model = settings.openai_model
        self.provider = settings.llm_provider
        # PlanService is used to inject the ``plans`` table context into the
        # system prompt. We default-construct one so the existing call sites
        # (``AIService()``) don't need to change; callers can still inject a
        # shared instance for testing or DI.
        self._plan_service: PlanService = plan_service or PlanService()

    @staticmethod
    def _to_chat_messages(
        system: str, input_: "str | list[dict]"
    ) -> list[dict]:
        """Convert (instructions, input) into Chat Completions message list.

        ``input_`` can be a plain string (a single user message) or a list of
        ``{role, content}`` dicts (full conversation history). The system
        instructions are always prepended.
        """
        messages: list[dict] = [{"role": "system", "content": system}]
        if isinstance(input_, str):
            messages.append({"role": "user", "content": input_})
        elif isinstance(input_, list):
            messages.extend(input_)
        return messages

    async def _complete(
        self,
        system: str,
        input_: "str | list[dict]",
        max_output_tokens: int,
    ) -> str:
        """Call the configured LLM provider and return text content.

        - For ``openai``: uses the new Responses API (``/v1/responses``).
        - For ``openrouter`` (and any non-OpenAI provider): falls back to
          Chat Completions (``/v1/chat/completions``), which OpenRouter
          natively speaks.
        """
        try:
            if self.provider == "openai":
                response = await self.client.responses.create(
                    model=self.model,
                    instructions=system,
                    input=input_,
                    max_output_tokens=max_output_tokens,
                )
                content = getattr(response, "output_text", None)
                if not content:
                    # Manual extraction fallback: iterate output items
                    for item in getattr(response, "output", []):
                        if getattr(item, "type", None) == "message":
                            for block in getattr(item, "content", []):
                                if getattr(block, "type", None) == "output_text":
                                    content = block.text
                                    break
                        if content:
                            break
                return content or ""

            # OpenRouter / generic OpenAI-compatible: chat completions
            messages = self._to_chat_messages(system, input_)
            chat = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                max_tokens=max_output_tokens,
            )
            try:
                return chat.choices[0].message.content or ""
            except (AttributeError, IndexError):
                return ""

        except openai.APIConnectionError as e:
            logger.error("LLM connection error", provider=self.provider, error=str(e))
            raise AIServiceError("Не удалось подключиться к LLM API") from e
        except openai.RateLimitError as e:
            logger.error("LLM rate limit", provider=self.provider, error=str(e))
            raise AIServiceError("Превышен лимит запросов LLM") from e
        except openai.APIStatusError as e:
            logger.error(
                "LLM API error",
                provider=self.provider,
                status=e.status_code,
                error=e.message,
            )
            raise AIServiceError(f"Ошибка LLM: {e.message}") from e

    async def _get_report_context(self) -> str:
        """Get active report context prompt from database."""
        engine = get_engine()
        try:
            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        """
                        SELECT content
                        FROM report_prompt_templates
                        WHERE name = 'report_context' AND is_active = true
                        ORDER BY created_at DESC
                        LIMIT 1
                        """
                    )
                )
                row = result.first()
                if row:
                    return row[0]
                return ""
        except Exception as e:
            logger.warning("Failed to load report context", error=str(e))
            return ""

    async def _get_bitrix_context(self) -> str:
        """Get active Bitrix context prompt from database.

        Returns a concatenation of:
        1. The active ``bitrix_context`` row from ``chart_prompt_templates``
           (describes the Bitrix CRM schema for the LLM).
        2. The ``plans`` table markdown block from
           :meth:`PlanService.get_plans_llm_context`, so the LLM can pick the
           right ``(table_name, field_name)`` pair for
           ``chart_config.plan_fact`` (post-enrichment — no JOIN on ``plans``).

        Both parts are best-effort: if either lookup fails the method still
        returns whatever context it managed to assemble (possibly an empty
        string) so the LLM call is never blocked on prompt enrichment.
        """
        bitrix_context = ""
        engine = get_engine()
        try:
            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        """
                        SELECT content
                        FROM chart_prompt_templates
                        WHERE name = 'bitrix_context' AND is_active = true
                        ORDER BY created_at DESC
                        LIMIT 1
                        """
                    )
                )
                row = result.first()
                if row:
                    bitrix_context = row[0] or ""
        except Exception as e:
            logger.warning("Failed to load bitrix context", error=str(e))

        plans_context = ""
        if self._plan_service is not None:
            try:
                plans_context = await self._plan_service.get_plans_llm_context()
            except Exception as e:  # pragma: no cover — best-effort enrichment
                logger.warning("Failed to load plans context", error=str(e))
                plans_context = ""

        if bitrix_context and plans_context:
            return f"{bitrix_context}\n\n{plans_context}".strip()
        return (bitrix_context or plans_context).strip()

    async def generate_chart_spec(self, prompt: str, schema_context: str) -> dict:
        """Generate a chart specification from a natural language prompt.

        Args:
            prompt: Chart description in natural language.
            schema_context: Formatted DB schema (tables, columns, types).

        Returns:
            Dict with keys: title, chart_type, sql_query, data_keys, colors, description.
        """
        bitrix_context = await self._get_bitrix_context()
        system_message = CHART_SYSTEM_PROMPT.format(
            schema_context=schema_context,
            bitrix_context=bitrix_context
        )

        logger.info("Generating chart spec", prompt=prompt, model=self.model, has_bitrix_context=bool(bitrix_context))

        content = await self._complete(system_message, prompt, 2000)
        if not content:
            raise AIServiceError("AI вернул пустой ответ")

        content = _extract_json(content)
        try:
            spec = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON from AI", content=content)
            raise AIServiceError("AI вернул невалидный JSON") from e

        logger.info("Chart spec generated", chart_type=spec.get("chart_type"))
        return spec

    async def refine_chart_sql(
        self,
        current_sql: str,
        instruction: str,
        schema_context: str,
    ) -> str:
        """Refine an existing chart's SQL based on a user instruction.

        Args:
            current_sql: The chart's current ``sql_query`` (saved in the DB).
            instruction: Free-form description of the change the user wants
                (e.g. "добавь фильтр по последним 30 дням", "сгруппируй
                по менеджерам").
            schema_context: Formatted DB schema (tables, columns, types).

        Returns:
            The refined SQL string. Chart type / data_keys are NOT touched —
            the caller should assume the chart config stays the same unless
            the refined query obviously breaks it.
        """
        bitrix_context = await self._get_bitrix_context()
        system_message = CHART_SQL_REFINE_PROMPT.format(
            schema_context=schema_context,
            bitrix_context=bitrix_context,
            current_sql=current_sql,
            instruction=instruction,
        )

        logger.info("Refining chart SQL", instruction=instruction, model=self.model)

        content = await self._complete(
            system_message,
            "Верни обновлённый SQL в JSON.",
            2000,
        )
        if not content:
            raise AIServiceError("AI вернул пустой ответ")

        content = _extract_json(content)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON from AI (refine_chart_sql)", content=content)
            raise AIServiceError("AI вернул невалидный JSON") from e

        new_sql = parsed.get("sql_query") if isinstance(parsed, dict) else None
        if not isinstance(new_sql, str) or not new_sql.strip():
            raise AIServiceError("AI не вернул sql_query")

        logger.info("Chart SQL refined", length=len(new_sql))
        return new_sql.strip()

    async def generate_selectors(
        self,
        charts_context: str,
        schema_context: str,
        user_request: str | None = None,
    ) -> list[dict]:
        """Generate a list of selectors for a dashboard from its charts and schema.

        Args:
            charts_context: Formatted text describing each chart on the dashboard
                (id, title, SQL, columns, tables).
            schema_context: Formatted DB schema (tables, columns, types).
            user_request: Optional free-form description from the user about which
                selectors they want (in natural language). Used as a high-priority
                hint inside the prompt.

        Returns:
            List of selector dicts (each ready to be passed to
            ``SelectorService.create_selector`` plus ``mappings``).
        """
        user_request_clean = (user_request or "").strip()
        if user_request_clean:
            user_request_block = (
                "\nUser request (highest priority — generate selectors that match this):\n"
                f"{user_request_clean}\n"
            )
        else:
            user_request_block = ""

        system_message = SELECTORS_GENERATE_PROMPT.format(
            schema_context=schema_context,
            charts_context=charts_context,
            user_request_block=user_request_block,
        )

        logger.info("Generating selectors", model=self.model)

        content = await self._complete(
            system_message,
            "Сгенерируй селекторы для этого дашборда. Верни валидный JSON.",
            4000,
        )
        if not content:
            raise AIServiceError("AI вернул пустой ответ")

        content = _extract_json(content)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON from AI (selectors)", content=content)
            raise AIServiceError("AI вернул невалидный JSON") from e

        selectors = parsed.get("selectors") if isinstance(parsed, dict) else parsed
        if not isinstance(selectors, list):
            raise AIServiceError("AI вернул не список селекторов")

        logger.info("Selectors generated", count=len(selectors))
        return selectors

    async def regenerate_mapping(
        self,
        schema_context: str,
        charts_context: str,
        target_dc_id: int,
        selector_name: str,
        selector_label: str,
        selector_type: str,
        selector_operator: str,
        user_request: str | None = None,
    ) -> dict:
        """Regenerate a single selector→chart mapping for a specific chart.

        Returns a dict with keys:
            target_column, target_table, operator_override,
            post_filter_resolve_table, post_filter_resolve_column,
            post_filter_resolve_id_column

        Optional fields may be None.
        """
        user_request_clean = (user_request or "").strip() or "(no specific request)"

        system_message = MAPPING_REGENERATE_PROMPT.format(
            schema_context=schema_context,
            charts_context=charts_context,
            target_dc_id=target_dc_id,
            sel_name=selector_name,
            sel_label=selector_label,
            sel_type=selector_type,
            sel_operator=selector_operator,
            user_request=user_request_clean,
        )

        logger.info(
            "Regenerating selector mapping",
            model=self.model,
            dc_id=target_dc_id,
            selector_name=selector_name,
        )

        content = await self._complete(
            system_message,
            "Сгенерируй маппинг для этого чарта. Верни только валидный JSON-объект.",
            1500,
        )
        if not content:
            raise AIServiceError("AI вернул пустой ответ")

        content = _extract_json(content)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON from AI (mapping)", content=content)
            raise AIServiceError("AI вернул невалидный JSON") from e

        if not isinstance(parsed, dict):
            raise AIServiceError("AI вернул не объект")

        target_column = parsed.get("target_column")
        if not target_column or not isinstance(target_column, str):
            raise AIServiceError("AI не вернул target_column")

        def _norm(key: str) -> str | None:
            v = parsed.get(key)
            if v is None:
                return None
            if isinstance(v, str):
                v = v.strip()
                return v or None
            return None

        return {
            "target_column": target_column.strip(),
            "target_table": _norm("target_table"),
            "operator_override": _norm("operator_override"),
            "post_filter_resolve_table": _norm("post_filter_resolve_table"),
            "post_filter_resolve_column": _norm("post_filter_resolve_column"),
            "post_filter_resolve_id_column": _norm("post_filter_resolve_id_column"),
        }

    async def generate_schema_description(self, schema_context: str) -> str:
        """Generate a markdown description of the DB schema.

        Args:
            schema_context: Formatted DB schema (tables, columns, types).

        Returns:
            Markdown string describing each table and its fields.
        """
        system_message = SCHEMA_DESCRIPTION_PROMPT.format(schema_context=schema_context)

        logger.info("Generating schema description", model=self.model)

        content = await self._complete(
            system_message,
            "Сгенерируй подробное описание всех таблиц и полей в формате markdown.",
            10000,
        )
        if not content:
            raise AIServiceError("AI вернул пустой ответ")

        logger.info("Schema description generated", length=len(content))
        return content

    async def generate_report_step(
        self,
        conversation_history: list[dict[str, str]],
        schema_context: str,
    ) -> dict:
        """One step of the report generation dialog.

        Args:
            conversation_history: List of {role, content} messages.
            schema_context: Formatted DB schema.

        Returns:
            Dict with is_complete, and either question or full report spec.
        """
        report_context = await self._get_report_context()
        system_message = REPORT_SYSTEM_PROMPT.format(
            schema_context=schema_context,
            report_context=report_context,
        )

        logger.info(
            "Generating report step",
            model=self.model,
            history_len=len(conversation_history),
        )

        content = await self._complete(system_message, conversation_history, 4000)
        if not content:
            raise AIServiceError("AI вернул пустой ответ")

        content = _extract_json(content)
        try:
            result = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON from AI (report step)", content=content)
            raise AIServiceError("AI вернул невалидный JSON") from e

        logger.info("Report step generated", is_complete=result.get("is_complete"))
        return result

    async def analyze_report_data(
        self,
        report_title: str,
        sql_results: list[dict],
        analysis_prompt: str,
        user_prompt: str = "",
        report_context: str = "",
    ) -> tuple[str, str]:
        """Analyze SQL query results and generate a Markdown report.

        Args:
            report_title: Title of the report.
            sql_results: List of {sql, purpose, rows, row_count, time_ms, error?}.
            analysis_prompt: Additional instructions for analysis.
            user_prompt: Original user request that created the report.
            report_context: Custom report context from prompt templates.

        Returns:
            Tuple of (markdown_content, full_prompt_sent_to_llm).
        """
        if not report_context:
            report_context = await self._get_report_context()

        # Format SQL results for the prompt (no raw SQL shown to keep report manager-friendly)
        results_parts = []
        for i, r in enumerate(sql_results, 1):
            part = f"### Блок данных {i}: {r.get('purpose', 'N/A')}\n"
            if r.get("error"):
                part += f"**Данные недоступны (ошибка получения):** {r['error']}\n"
            else:
                row_count = r.get('row_count', 0)
                part += f"Получено записей: {row_count}\n"
                rows = r.get("rows", [])
                if rows:
                    # Show first 20 rows as JSON for brevity
                    sample = rows[:20]
                    part += f"Данные (первые {len(sample)} из {row_count}):\n```json\n{json.dumps(sample, ensure_ascii=False, default=str, indent=2)}\n```\n"
                elif row_count == 0:
                    part += "Данных не найдено (возможно, ошибка в логике получения или данные отсутствуют).\n"
            results_parts.append(part)

        sql_results_text = "\n".join(results_parts)

        system_message = REPORT_ANALYSIS_PROMPT.format(
            report_title=report_title,
            report_context=report_context,
            user_prompt=user_prompt or "(не указан)",
            sql_results_text=sql_results_text,
            analysis_prompt=analysis_prompt or "Проведи общий анализ данных.",
        )

        logger.info("Analyzing report data", model=self.model, title=report_title)

        content = await self._complete(
            system_message,
            "Проанализируй данные и сгенерируй отчёт в формате Markdown.",
            6000,
        )
        if not content:
            raise AIServiceError("AI вернул пустой ответ")

        logger.info("Report analysis generated", length=len(content))
        return content, system_message

    # ------------------------------------------------------------------
    # Plans generation (Phase 3)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_plans_hints(hints: dict[str, Any] | None) -> str:
        """Format optional table/field hints for the plans prompt.

        Возвращает короткий русскоязычный блок, который подставляется в
        placeholder ``{hints}`` системного промпта
        :data:`PLANS_GENERATION_PROMPT`. Если hints пустые — возвращает
        «не указаны», чтобы шаблон не ломался.
        """
        if not hints:
            return "не указаны"
        parts: list[str] = []
        table_name = hints.get("table_name")
        field_name = hints.get("field_name")
        if table_name:
            parts.append(f"таблица = `{table_name}`")
        if field_name:
            parts.append(f"поле = `{field_name}`")
        if not parts:
            return "не указаны"
        return "; ".join(parts)

    async def generate_plans_from_description(
        self,
        description: str,
        schema_context: str,
        hints: dict[str, Any] | None = None,
        managers_context: str | None = None,
    ) -> dict[str, Any]:
        """Generate plan drafts from a natural-language description.

        Собирает системный промпт :data:`PLANS_GENERATION_PROMPT` c
        подстановкой ``schema_context`` (markdown-описание таблиц) и
        ``current_date`` (сегодня, в ISO), вызывает LLM через
        ``_complete`` (OpenAI / OpenRouter — оба провайдера работают
        через общий абстракционный метод) и парсит JSON-ответ.

        Args:
            description: Свободный пользовательский запрос на русском
                языке. Помещается в ``user``-сообщение.
            schema_context: Markdown-блок c описанием таблиц — тот же,
                что используется для генерации чартов (берётся
                endpoint'ом из ``ChartService.get_any_latest_schema_description``
                или ``get_schema_context``).
            hints: Опциональные подсказки о таблице/поле. Если
                заданы — добавляются в конец description как отдельный
                «Подсказки пользователя» блок и подставляются в
                placeholder ``{hints}`` системного промпта.

        Returns:
            dict c ключами ``plans`` (list сырых черновиков от LLM,
            где ``assigned_by_id`` может быть спец-значением
            ``"all_managers"`` / ``"department:Name"``) и ``warnings``
            (list строк). Фактический разворот спец-значений в
            ``PlanDraft`` — обязанность вызывающего (см.
            ``expand_ai_drafts``).

        Raises:
            AIServiceError: если LLM вернул пустой ответ или невалидный
                JSON. Это единственный тип ошибок, который поднимается
                слоем ``_complete`` для провайдерских сбоев (rate-limit,
                connection, bad status).
        """
        plans_context = ""
        if self._plan_service is not None:
            try:
                plans_context = await self._plan_service.get_plans_llm_context()
            except Exception as exc:  # pragma: no cover — best-effort
                logger.warning(
                    "generate_plans_from_description: failed to load plans context",
                    error=str(exc),
                )

        # Compose schema_context: базовая схема + markdown-блок про
        # таблицу planов (включая список уже созданных планов). LLM
        # подставит ``table_name``/``field_name`` в черновики только
        # из этого объединённого контекста.
        combined_schema = schema_context
        if plans_context:
            combined_schema = f"{schema_context}\n\n{plans_context}".strip()

        hints_block = self._format_plans_hints(hints)
        current_date = date.today().isoformat()
        managers_block = managers_context or "список активных менеджеров не передан"

        system_message = PLANS_GENERATION_PROMPT.format(
            schema_context=combined_schema,
            current_date=current_date,
            hints=hints_block,
            managers_context=managers_block,
        )

        logger.info(
            "Generating plans from description",
            model=self.model,
            description_length=len(description or ""),
            has_hints=bool(hints),
        )

        content = await self._complete(system_message, description, 3000)
        if not content:
            raise AIServiceError("AI вернул пустой ответ")

        content = _extract_json(content)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(
                "Invalid JSON from AI (generate_plans_from_description)",
                content=content,
            )
            raise AIServiceError("AI вернул невалидный JSON") from e

        if not isinstance(parsed, dict):
            raise AIServiceError("AI вернул не JSON-объект")

        raw_plans = parsed.get("plans") or []
        raw_warnings = parsed.get("warnings") or []
        if not isinstance(raw_plans, list):
            raise AIServiceError("AI вернул поле 'plans' не списком")
        if not isinstance(raw_warnings, list):
            raise AIServiceError("AI вернул поле 'warnings' не списком")

        # Нормализуем warnings в list[str], фильтруем не-строки.
        warnings: list[str] = [str(w) for w in raw_warnings if w is not None]

        logger.info(
            "Plans generated",
            plans_count=len(raw_plans),
            warnings_count=len(warnings),
        )

        return {"plans": raw_plans, "warnings": warnings}
