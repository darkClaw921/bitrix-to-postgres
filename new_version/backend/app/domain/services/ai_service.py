"""AI service for interaction with OpenAI API."""

import json

import openai
from openai import AsyncOpenAI
from sqlalchemy import text

from app.config import get_settings
from app.core.exceptions import AIServiceError
from app.core.logging import get_logger
from app.infrastructure.database.connection import get_engine

logger = get_logger(__name__)

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
"""

SELECTOR_GENERATION_PROMPT = """You are an analytics dashboard configuration expert for a Bitrix24 CRM system.

You need to analyze the SQL queries of charts on a dashboard and suggest relevant selectors (filters) that users can use to filter chart data dynamically.

Charts on this dashboard:
{charts_context}

Database schema:
{schema_context}

Your task: generate a JSON object with a "selectors" array. Each selector has:
- name (string): unique internal key in snake_case (e.g. "date_filter", "manager_filter", "stage_filter")
- label (string): display label in Russian (e.g. "Период", "Менеджер", "Стадия")
- selector_type (string): one of date_range, single_date, dropdown, multi_select, text
- operator (string): one of equals, not_equals, in, not_in, between, gt, lt, gte, lte, like, not_like
- config (object): optional, with source_table and source_column for dropdown/multi_select options
- is_required (boolean): whether the filter is mandatory
- mappings (array): chart mappings, each with:
  - dashboard_chart_id (number): the ID of the chart on this dashboard
  - target_column (string): the column in that chart's SQL to filter on

Rules:
1. Choose selector_type based on the data type of the columns (dates → date_range, text with few values → dropdown, text with many values → text, etc.)
2. Match operator to selector_type: date_range → between, dropdown → equals, multi_select → in, text → like
3. For dropdown/multi_select, set config.source_table and config.source_column to provide options
4. Map the same selector to multiple charts if they share the same concept (e.g. date field) but possibly different column names
5. Suggest 2-5 selectors that would be most useful for filtering the data
6. Only suggest selectors for columns that actually exist in the charts' SQL queries
7. Return valid JSON only
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
"""

REPORT_ANALYSIS_PROMPT = """Ты — аналитик данных. Проанализируй результаты SQL-запросов и напиши аналитический отчёт в формате Markdown.

Отчёт: {report_title}

Результаты запросов:
{sql_results_text}

{analysis_prompt}

Требования к отчёту:
- Пиши на русском языке
- Используй заголовки, списки, таблицы Markdown
- Включи ключевые показатели и метрики
- Сделай выводы и рекомендации
- Если есть ошибки в запросах — укажи это
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


class AIService:
    """Service for generating chart specs and schema descriptions via OpenAI."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout_seconds,
        )
        self.model = settings.openai_model

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

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=2000,
            )
        except openai.APIConnectionError as e:
            logger.error("OpenAI connection error", error=str(e))
            raise AIServiceError("Не удалось подключиться к OpenAI API") from e
        except openai.RateLimitError as e:
            logger.error("OpenAI rate limit", error=str(e))
            raise AIServiceError("Превышен лимит запросов OpenAI") from e
        except openai.APIStatusError as e:
            logger.error("OpenAI API error", status=e.status_code, error=e.message)
            raise AIServiceError(f"Ошибка OpenAI: {e.message}") from e

        content = response.choices[0].message.content
        if not content:
            raise AIServiceError("AI вернул пустой ответ")

        try:
            spec = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON from AI", content=content)
            raise AIServiceError("AI вернул невалидный JSON") from e

        logger.info("Chart spec generated", chart_type=spec.get("chart_type"))
        return spec

    async def generate_schema_description(self, schema_context: str) -> str:
        """Generate a markdown description of the DB schema.

        Args:
            schema_context: Formatted DB schema (tables, columns, types).

        Returns:
            Markdown string describing each table and its fields.
        """
        system_message = SCHEMA_DESCRIPTION_PROMPT.format(schema_context=schema_context)

        logger.info("Generating schema description", model=self.model)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {
                        "role": "user",
                        "content": "Сгенерируй подробное описание всех таблиц и полей в формате markdown.",
                    },
                ],
                temperature=0.3,
                max_tokens=10000,
            )
        except openai.APIConnectionError as e:
            logger.error("OpenAI connection error", error=str(e))
            raise AIServiceError("Не удалось подключиться к OpenAI API") from e
        except openai.RateLimitError as e:
            logger.error("OpenAI rate limit", error=str(e))
            raise AIServiceError("Превышен лимит запросов OpenAI") from e
        except openai.APIStatusError as e:
            logger.error("OpenAI API error", status=e.status_code, error=e.message)
            raise AIServiceError(f"Ошибка OpenAI: {e.message}") from e

        content = response.choices[0].message.content
        if not content:
            raise AIServiceError("AI вернул пустой ответ")

        logger.info("Schema description generated", length=len(content))
        return content

    async def generate_selectors(
        self, charts_context: str, schema_context: str
    ) -> list[dict]:
        """Generate selector suggestions for a dashboard based on its charts.

        Args:
            charts_context: Formatted chart info (id, title, SQL).
            schema_context: Formatted DB schema.

        Returns:
            List of selector dicts with name, label, type, operator, config, mappings.
        """
        system_message = SELECTOR_GENERATION_PROMPT.format(
            charts_context=charts_context,
            schema_context=schema_context,
        )

        logger.info("Generating selectors", model=self.model)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {
                        "role": "user",
                        "content": "Предложи подходящие фильтры (селекторы) для этого дашборда на основе SQL-запросов чартов.",
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=3000,
            )
        except openai.APIConnectionError as e:
            logger.error("OpenAI connection error", error=str(e))
            raise AIServiceError("Не удалось подключиться к OpenAI API") from e
        except openai.RateLimitError as e:
            logger.error("OpenAI rate limit", error=str(e))
            raise AIServiceError("Превышен лимит запросов OpenAI") from e
        except openai.APIStatusError as e:
            logger.error("OpenAI API error", status=e.status_code, error=e.message)
            raise AIServiceError(f"Ошибка OpenAI: {e.message}") from e

        content = response.choices[0].message.content
        if not content:
            raise AIServiceError("AI вернул пустой ответ")

        try:
            result = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON from AI", content=content)
            raise AIServiceError("AI вернул невалидный JSON") from e

        selectors = result.get("selectors", [])
        logger.info("Selectors generated", count=len(selectors))
        return selectors

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

        messages = [{"role": "system", "content": system_message}]
        messages.extend(conversation_history)

        logger.info(
            "Generating report step",
            model=self.model,
            history_len=len(conversation_history),
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=4000,
            )
        except openai.APIConnectionError as e:
            logger.error("OpenAI connection error", error=str(e))
            raise AIServiceError("Не удалось подключиться к OpenAI API") from e
        except openai.RateLimitError as e:
            logger.error("OpenAI rate limit", error=str(e))
            raise AIServiceError("Превышен лимит запросов OpenAI") from e
        except openai.APIStatusError as e:
            logger.error("OpenAI API error", status=e.status_code, error=e.message)
            raise AIServiceError(f"Ошибка OpenAI: {e.message}") from e

        content = response.choices[0].message.content
        if not content:
            raise AIServiceError("AI вернул пустой ответ")

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
    ) -> str:
        """Analyze SQL query results and generate a Markdown report.

        Args:
            report_title: Title of the report.
            sql_results: List of {sql, purpose, rows, row_count, time_ms, error?}.
            analysis_prompt: Additional instructions for analysis.

        Returns:
            Markdown string with the report.
        """
        # Format SQL results for the prompt
        results_parts = []
        for i, r in enumerate(sql_results, 1):
            part = f"### Запрос {i}: {r.get('purpose', 'N/A')}\n"
            part += f"SQL: `{r.get('sql', 'N/A')}`\n"
            if r.get("error"):
                part += f"**Ошибка:** {r['error']}\n"
            else:
                part += f"Получено строк: {r.get('row_count', 0)}, время: {r.get('time_ms', 0)}мс\n"
                rows = r.get("rows", [])
                if rows:
                    # Show first 20 rows as JSON for brevity
                    sample = rows[:20]
                    part += f"Данные (первые {len(sample)} строк):\n```json\n{json.dumps(sample, ensure_ascii=False, default=str, indent=2)}\n```\n"
            results_parts.append(part)

        sql_results_text = "\n".join(results_parts)

        system_message = REPORT_ANALYSIS_PROMPT.format(
            report_title=report_title,
            sql_results_text=sql_results_text,
            analysis_prompt=analysis_prompt or "Проведи общий анализ данных.",
        )

        logger.info("Analyzing report data", model=self.model, title=report_title)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {
                        "role": "user",
                        "content": "Проанализируй данные и сгенерируй отчёт в формате Markdown.",
                    },
                ],
                temperature=0.3,
                max_tokens=6000,
            )
        except openai.APIConnectionError as e:
            logger.error("OpenAI connection error", error=str(e))
            raise AIServiceError("Не удалось подключиться к OpenAI API") from e
        except openai.RateLimitError as e:
            logger.error("OpenAI rate limit", error=str(e))
            raise AIServiceError("Превышен лимит запросов OpenAI") from e
        except openai.APIStatusError as e:
            logger.error("OpenAI API error", status=e.status_code, error=e.message)
            raise AIServiceError(f"Ошибка OpenAI: {e.message}") from e

        content = response.choices[0].message.content
        if not content:
            raise AIServiceError("AI вернул пустой ответ")

        logger.info("Report analysis generated", length=len(content))
        return content
