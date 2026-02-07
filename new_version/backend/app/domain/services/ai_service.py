"""AI service for interaction with OpenAI API."""

import json

import openai
from openai import AsyncOpenAI

from app.config import get_settings
from app.core.exceptions import AIServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)

CHART_SYSTEM_PROMPT = """You are a SQL query and chart configuration generator for a CRM analytics dashboard.

Available database schema:
{schema_context}

Your task: generate a JSON object with the following fields:
- title (string): short chart title in Russian
- chart_type (string): one of bar, line, pie, area, scatter, indicator, table
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

    async def generate_chart_spec(self, prompt: str, schema_context: str) -> dict:
        """Generate a chart specification from a natural language prompt.

        Args:
            prompt: Chart description in natural language.
            schema_context: Formatted DB schema (tables, columns, types).

        Returns:
            Dict with keys: title, chart_type, sql_query, data_keys, colors, description.
        """
        system_message = CHART_SYSTEM_PROMPT.format(schema_context=schema_context)

        logger.info("Generating chart spec", prompt=prompt, model=self.model)

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
