"""AI service for interaction with OpenAI API."""

import json
import re

import openai
from openai import AsyncOpenAI
from sqlalchemy import text

from app.config import get_settings
from app.core.exceptions import AIServiceError
from app.core.logging import get_logger
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

    def __init__(self) -> None:
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

        Returns:
            Bitrix context string or empty string if not found.
        """
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
                    return row[0]
                return ""
        except Exception as e:
            logger.warning("Failed to load bitrix context", error=str(e))
            return ""

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
