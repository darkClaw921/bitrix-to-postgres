# Архитектура Bitrix24 Sync Service

## Обзор системы

Bitrix24 Sync Service — микросервис для односторонней синхронизации данных CRM из Bitrix24 в базу данных (PostgreSQL или MySQL). Система построена на принципах Clean Architecture и обеспечивает надежную, масштабируемую синхронизацию с поддержкой real-time обновлений через webhooks.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              ВНЕШНИЕ СИСТЕМЫ                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐                                 ┌─────────────┐            │
│  │  Bitrix24   │                                 │   Frontend  │            │
│  │  REST API   │                                 │   (React)   │            │
│  └──────┬──────┘                                 └──────┬──────┘            │
│         │                                               │                    │
│         │ webhooks                                      │ HTTP               │
│         ▼                                               ▼                    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         FastAPI Backend                               │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐     │   │
│  │  │   Sync     │  │  Webhook   │  │   Status   │  │   Config   │     │   │
│  │  │  Endpoints │  │  Handler   │  │  Endpoint  │  │  Endpoint  │     │   │
│  │  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘     │   │
│  │        │               │               │               │             │   │
│  │        └───────────────┴───────────────┴───────────────┘             │   │
│  │                              │                                        │   │
│  │                    ┌─────────▼─────────┐                             │   │
│  │                    │    SyncService    │                             │   │
│  │                    │  (Domain Layer)   │                             │   │
│  │                    └─────────┬─────────┘                             │   │
│  │                              │                                        │   │
│  │         ┌────────────────────┼────────────────────┐                  │   │
│  │         │                    │                    │                  │   │
│  │  ┌──────▼──────┐     ┌───────▼───────┐    ┌──────▼──────┐           │   │
│  │  │ BitrixClient│     │DynamicTable   │    │ APScheduler │           │   │
│  │  │(fast-bitrix)│     │   Builder     │    │  (cron)     │           │   │
│  │  └──────┬──────┘     └───────┬───────┘    └─────────────┘           │   │
│  │         │                    │                                       │   │
│  └─────────┼────────────────────┼───────────────────────────────────────┘   │
│            │                    │                                            │
│            ▼                    ▼                                            │
│  ┌─────────────────┐   ┌─────────────────┐                                  │
│  │   Bitrix24 API  │   │ PostgreSQL /    │                                  │
│  │  (External)     │   │ MySQL (external)│                                  │
│  └─────────────────┘   └─────────────────┘                                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Поддержка баз данных

Подключение к БД через `DATABASE_URL` из `.env`:

| СУБД | Формат DATABASE_URL | Async Driver |
|------|---------------------|--------------|
| PostgreSQL | `postgresql+asyncpg://user:pass@host:5432/db` | asyncpg |
| MySQL | `mysql+aiomysql://user:pass@host:3306/db` | aiomysql |

Диалект определяется автоматически из URL. Все SQL-запросы адаптируются под диалект:
- **UPSERT**: `ON CONFLICT DO UPDATE` (PG) / `ON DUPLICATE KEY UPDATE` (MySQL)
- **RETURNING**: поддерживается в PG, для MySQL используется отдельный SELECT
- **DISTINCT ON**: только PG, для MySQL — подзапрос с MAX

## Слои приложения

### 1. API Layer (`app/api/`)

```
app/api/
├── v1/
│   ├── __init__.py          # Роутер версии API (sync, webhooks, status, charts, schema, references, dashboards, selectors, public)
│   ├── endpoints/
│   │   ├── sync.py          # Эндпоинты синхронизации
│   │   ├── webhooks.py      # Обработка webhooks от Bitrix24
│   │   ├── status.py        # Статус и health checks
│   │   ├── charts.py        # AI-генерация и CRUD чартов
│   │   ├── schema_description.py  # AI-описание и raw-описание схемы БД
│   │   ├── references.py    # Синхронизация справочных данных (статусы, воронки, валюты)
│   │   ├── dashboards.py    # CRUD дашбордов, layout, ссылки, пароли. Heading-эндпоинты: POST/PUT /headings (создание и обновление heading items). Chart-add эндпоинт: POST /charts (добавление существующего AI-чарта в дашборд)
│   │   ├── selectors.py     # CRUD селекторов (фильтров) дашбордов и маппингов
│   │   └── public.py        # Публичные эндпоинты: чарты, дашборды, аутентификация, фильтрованные данные. Chart data endpoints возвращают 400 если dc_id принадлежит heading
│   └── schemas/
│       ├── sync.py          # Pydantic схемы для sync
│       ├── webhooks.py      # Схемы webhooks
│       ├── common.py        # Общие схемы
│       ├── charts.py        # Схемы чартов (ChartSpec, ChartGenerateRequest/Response и др.)
│       ├── dashboards.py    # Схемы дашбордов (DashboardResponse включает selectors). Полиморфный DashboardChartResponse (item_type='chart'|'heading', chart_id Optional, heading_config Optional). Heading-схемы: HeadingConfig, HeadingCreateRequest, HeadingUpdateRequest. Chart-add: ChartAddRequest (chart_id + опциональный layout)
│       ├── selectors.py     # Схемы селекторов (SelectorCreateRequest, SelectorResponse, FilterValue и др.)
│       └── schema_description.py  # Схемы описания схемы (TableInfo, ColumnInfo и др.)
```

#### Ключевые эндпоинты:

| Метод | Путь | Описание |
|-------|------|----------|
| `POST` | `/api/v1/sync/start/{entity}` | Запуск синхронизации |
| `GET` | `/api/v1/sync/status` | Статус синхронизации |
| `GET` | `/api/v1/sync/config` | Конфигурация |
| `PUT` | `/api/v1/sync/config` | Обновление конфигурации |
| `POST` | `/api/v1/webhooks/bitrix` | Приём webhooks |
| `POST` | `/api/v1/webhooks/register` | Регистрация в Bitrix24 |
| `POST` | `/api/v1/charts/generate` | AI-генерация чарта из промпта |
| `POST` | `/api/v1/charts/execute-sql` | Выполнение raw SQL с валидацией (для preview-редактирования) |
| `POST` | `/api/v1/charts/save` | Сохранение чарта |
| `GET` | `/api/v1/charts/list` | Список сохранённых чартов |
| `GET` | `/api/v1/charts/{id}/data` | Обновление данных чарта |
| `PATCH` | `/api/v1/charts/{id}/config` | Обновление chart_config (deep merge) |
| `PATCH` | `/api/v1/charts/{id}/sql` | Ручное обновление sql_query чарта (ChartSqlUpdateRequest: sql_query, title?, description?). Валидирует SELECT-only, allowed_tables, ensure_limit, делает smoke-test через execute_chart_query |
| `POST` | `/api/v1/charts/{id}/refine-sql-ai` | AI-рефайн SQL по текстовой инструкции пользователя (ChartSqlRefineRequest: instruction → ChartSqlRefineResponse: sql_query). Без сохранения, клиент затем вызывает PATCH /sql |
| `DELETE` | `/api/v1/charts/{id}` | Удаление чарта |
| `POST` | `/api/v1/charts/{id}/pin` | Закрепить/открепить чарт |
| `GET` | `/api/v1/charts/prompt-template/bitrix-context` | Получение промпта для AI генерации чартов (инструкции по работе с Bitrix24) |
| `PUT` | `/api/v1/charts/prompt-template/bitrix-context` | Обновление промпта для AI генерации чартов |
| `GET` | `/api/v1/schema/describe` | AI-описание схемы БД (markdown). Автоматически сохраняется в БД. Query params: `entity_tables` (comma-separated), `include_related` (bool) |
| `GET` | `/api/v1/schema/describe-raw` | Генерация markdown-описания схемы из метаданных БД (без AI). Быстро и детерминировано. Сохраняется в БД. Query params: `entity_tables`, `include_related` |
| `GET` | `/api/v1/schema/tables` | Список таблиц с колонками (включая description из комментариев и enum-значения). Query params: `entity_tables`, `include_related` |
| `GET` | `/api/v1/schema/history` | Последняя сохранённая генерация схемы по фильтрам |
| `PATCH` | `/api/v1/schema/{id}` | Обновить markdown сохранённого описания |
| `GET` | `/api/v1/schema/list` | Список всех сохранённых описаний схем |
| `GET` | `/api/v1/references/types` | Список доступных справочников |
| `GET` | `/api/v1/references/status` | Статус синхронизации справочников |
| `POST` | `/api/v1/references/sync/{ref_name}` | Синхронизация конкретного справочника |
| `POST` | `/api/v1/references/sync-all` | Синхронизация всех справочников |
| `POST` | `/api/v1/dashboards/{id}/selectors` | Создание селектора (фильтра) для дашборда |
| `GET` | `/api/v1/dashboards/{id}/selectors` | Список селекторов дашборда |
| `PUT` | `/api/v1/dashboards/{id}/selectors/{sid}` | Обновление селектора |
| `DELETE` | `/api/v1/dashboards/{id}/selectors/{sid}` | Удаление селектора |
| `POST` | `/api/v1/dashboards/{id}/selectors/{sid}/mappings` | Добавление маппинга (селектор → чарт + колонка) |
| `DELETE` | `/api/v1/dashboards/{id}/selectors/{sid}/mappings/{mid}` | Удаление маппинга |
| `GET` | `/api/v1/dashboards/{id}/selectors/{sid}/options` | Получение опций для dropdown/multi_select |
| `POST` | `/api/v1/dashboards/{id}/selectors/generate` | AI-генерация селекторов на основе SQL-запросов чартов. Body: GenerateSelectorsRequest (user_request?, chart_ids? — список dashboard_chart_id для ограничения генерации; пусто/null = все чарты дашборда) |
| `GET` | `/api/v1/dashboards/{id}/charts/{dc_id}/columns` | Получение списка колонок из SQL-запроса чарта |
| `POST` | `/api/v1/dashboards/{id}/headings` | Создание heading-элемента в дашборде (HeadingCreateRequest → DashboardChartResponse, item_type='heading') |
| `PUT` | `/api/v1/dashboards/{id}/headings/{dc_id}` | Обновление heading_config существующего heading-элемента (HeadingUpdateRequest → DashboardChartResponse) |
| `POST` | `/api/v1/dashboards/{id}/charts` | Добавление существующего AI-чарта в дашборд (ChartAddRequest: chart_id + опциональный layout → DashboardChartResponse, item_type='chart'). Валидирует существование дашборда и чарта, sort_order=MAX+1 если не задан |
| `POST` | `/api/v1/public/dashboard/{slug}/chart/{dc_id}/data` | Данные чарта с фильтрами (POST + JWT). Применяет резолв date-токенов, post_filter сабзапросы и label_resolvers. 400 если dc_id принадлежит heading-элементу |
| `POST` | `/api/v1/public/dashboard/{slug}/linked/{ls}/chart/{dc_id}/data` | Данные чарта из связанного дашборда с фильтрами. 400 если dc_id принадлежит heading-элементу |
| `GET` | `/api/v1/public/dashboard/{slug}/selectors` | Селекторы публичного дашборда (JWT) |
| `GET` | `/api/v1/public/dashboard/{slug}/selector/{sid}/options` | Опции селектора (JWT) |
| `GET` | `/api/v1/public/dashboard/{slug}/selector-options` | Batch-опции всех селекторов дашборда (JWT) |
| `GET` | `/api/v1/public/dashboard/{slug}/linked/{ls}/selectors` | Селекторы linked-дашборда (JWT главного slug) |
| `GET` | `/api/v1/public/dashboard/{slug}/linked/{ls}/selector-options` | Batch-опции селекторов linked-дашборда (JWT главного slug) |
| `GET` | `/health` | Health check |

### 2. Domain Layer (`app/domain/`)

```
app/domain/
├── entities/
│   ├── base.py              # BitrixEntity, EntityType
│   ├── deal.py              # Модель сделки
│   ├── contact.py           # Модель контакта
│   ├── lead.py              # Модель лида
│   ├── company.py           # Модель компании
│   ├── call.py              # Модель звонка (voximplant.statistic.get)
│   ├── stage_history.py     # Модель истории движения по стадиям (crm.stagehistory.list)
│   └── reference.py         # Реестр справочных типов (ReferenceType, ReferenceFieldDef)
├── services/
│   ├── sync_service.py      # Основная логика синхронизации (+ авто-синхронизация справочников)
│   ├── reference_sync_service.py  # Синхронизация справочных таблиц (статусы, воронки, валюты)
│   ├── field_mapper.py      # Маппинг полей Bitrix → DB (кросс-БД совместимый)
│   ├── ai_service.py        # Взаимодействие с LLM API (OpenAI/OpenRouter): чарты, схема, селекторы
│   ├── chart_service.py     # SQL-валидация, выполнение запросов, CRUD чартов, apply_filters(), resolve_labels_in_data()
│   ├── dashboard_service.py # CRUD дашбордов, JWT-аутентификация, layout, ссылки (загружает selectors). Поддержка полиморфных элементов dashboard_charts (chart|heading): _get_dashboard_charts (LEFT JOIN ai_charts), add_heading, update_heading; update_layout/remove_chart работают по dashboard_charts.id для обоих типов; get_chart_sql_by_slug использует LEFT JOIN ai_charts и возвращает dc.item_type для отделения headings
│   ├── selector_service.py  # CRUD селекторов и маппингов, build_filters_for_chart() (с резолвом date-токенов и post_filter), get_selector_options() (поддержка JOIN с label-таблицей)
│   └── date_tokens.py       # Резолв date-токенов (TODAY, LAST_30_DAYS, ...) и end-of-day для BETWEEN
└── interfaces/              # Абстракции (для DI)
```

#### SyncService — основные методы:

```python
class SyncService:
    async def full_sync(entity_type: str) -> dict
    async def incremental_sync(entity_type: str) -> dict
    async def sync_entity_by_id(entity_type: str, entity_id: str) -> dict
    async def delete_entity_by_id(entity_type: str, entity_id: str) -> dict
```

#### AIService — AI-интеграция:

```python
class AIService:
    # Provider-agnostic: использует AsyncOpenAI с base_url из settings.resolved_llm_base_url.
    # provider == "openai"     → /v1/responses (Responses API)
    # provider == "openrouter" → /v1/chat/completions (OpenRouter не поддерживает Responses API)
    async def _complete(system: str, input_, max_output_tokens: int) -> str
    @staticmethod def _to_chat_messages(system: str, input_) -> list[dict]  # Конвертация в chat.completions формат

    async def _get_bitrix_context() -> str  # Загружает активный Bitrix-промпт из chart_prompt_templates
    async def _get_report_context() -> str  # Загружает активный report-промпт из report_prompt_templates

    async def generate_chart_spec(prompt: str, schema_context: str) -> dict  # Автоматически подгружает Bitrix-контекст
    async def refine_chart_sql(current_sql: str, instruction: str, schema_context: str) -> str  # AI-рефайн SQL существующего чарта по текстовой инструкции; использует CHART_SQL_REFINE_PROMPT; возвращает только sql_query
    async def generate_schema_description(schema_context: str) -> str
    async def generate_selectors(charts_context: str, schema_context: str, user_request: str | None = None) -> list[dict]  # AI-генерация селекторов с поддержкой токенов, post_filter и опционального текстового пожелания пользователя. Endpoint generate_selectors дополнительно фильтрует charts по chart_ids перед формированием charts_context
    async def generate_report_step(conversation_history: list[dict], schema_context: str) -> dict
    async def analyze_report_data(report_title, sql_results, analysis_prompt, ...) -> tuple[str, str]
```

**LLM Provider**: настраивается через `settings.llm_provider` (`openai` или `openrouter`). При `openrouter` `AsyncOpenAI` инициализируется с `base_url=https://openrouter.ai/api/v1` и опциональными заголовками `HTTP-Referer`/`X-Title` (`OPENROUTER_APP_URL`, `OPENROUTER_APP_TITLE`). В качестве модели для OpenRouter используется qualified id (`openai/gpt-4o-mini`, `anthropic/claude-3.5-sonnet` и т.п.).

**Bitrix Context Prompt**: При генерации чартов AIService автоматически загружает промпт `bitrix_context` из таблицы `chart_prompt_templates` и добавляет его в контекст для AI. Этот промпт содержит инструкции по работе с данными Bitrix24:
- Как рассчитывать конверсию по стадиям
- Как получать воронку продаж
- Как анализировать время в стадиях
- Примеры SQL-запросов для типичных задач
- Информация о связях между таблицами (deal/lead + stage_history)
- Пояснения по полям и идентификаторам

Пользователь может редактировать промпт через API для добавления собственных инструкций.

#### ChartService — управление чартами:

```python
class ChartService:
    # Вспомогательные методы для связанных таблиц
    @staticmethod def get_related_tables(entity_table: str) -> list[str]
    @staticmethod def expand_tables_with_related(tables: list[str]) -> list[str]

    # Вспомогательные методы для метаданных
    async def _get_enum_values_map() -> dict[str, dict[str, list[str]]]  # Получение значений enum-полей из ref_enum_values

    # SQL-валидация
    @staticmethod def validate_sql_query(sql: str) -> None
    @staticmethod def validate_table_names(sql: str, allowed: list[str]) -> None
    @staticmethod def ensure_limit(sql: str, max_rows: int) -> str

    # Схема и контекст (с автоматическим включением связанных таблиц, комментариев и enum-значений)
    async def get_schema_context(table_filter?, include_related=True) -> str  # Включает комментарии и enum-значения
    async def get_tables_info(table_filter?, include_related=True) -> list[dict]  # Включает description из комментариев и enum
    async def get_allowed_tables() -> list[str]  # Включает crm_*, ref_*, bitrix_*, stage_history_* таблицы
    async def generate_schema_markdown(table_filter?, include_related=True) -> str  # Генерация markdown из метаданных БД (без AI)

    # Извлечение колонок из SQL
    async def get_chart_columns(sql: str) -> list[str]  # Выполняет SQL с LIMIT 0, возвращает имена колонок

    # Применение фильтров (WHERE injection)
    @staticmethod def _build_condition(col_ref, op, value, prefix, bind_params) -> str | None  # Helper: одно условие + bind-параметры (с end-of-day для дат)
    @staticmethod def apply_filters(sql: str, filters: list[dict]) -> tuple[str, dict]
        # Top-level скан WHERE/GROUP BY/ORDER BY (учёт глубины скобок и string literals)
        # Авто-резолв table alias из SQL: target_table="crm_deals" → "cd" если SQL = "FROM crm_deals cd"
        # Поддержка post_filter: WHERE col IN (SELECT id FROM resolve_table WHERE resolve_col <op> :p)
        # Авто-расширение to-даты до 23:59:59 для between/lte

    # Резолв ID → имена в результирующих rows (post-processing)
    async def resolve_labels_in_data(rows: list[dict], resolvers: list[dict]) -> list[dict]
        # Каждый resolver: {column, resolve_table, resolve_value_column, resolve_label_column}
        # Один SELECT на resolver, in-memory словарь, замена значений в указанной колонке rows.
        # Идентификаторы валидируются через _IDENT_RE для защиты от SQL injection.

    # Выполнение запросов
    async def execute_chart_query(sql: str, bind_params?: dict) -> tuple[list[dict], float]

    # CRUD чартов
    async def save_chart(data: dict) -> dict
    async def get_charts(page, per_page) -> tuple[list[dict], int]
    async def delete_chart(chart_id: int) -> bool
    async def toggle_pin(chart_id: int) -> dict
    async def update_chart_config(chart_id: int, config_patch: dict) -> dict  # Deep-merge chart_config
    async def update_chart_sql(chart_id: int, new_sql: str, title?: str, description?: str) -> dict  # Валидирует SELECT-only, allowed_tables, ensure_limit, smoke-test через execute_chart_query, затем UPDATE ai_charts.sql_query (+ опц. title/description)

    # CRUD описаний схемы
    async def get_any_latest_schema_description() -> dict | None  # Последнее описание без фильтров (для генерации чартов)
    async def save_schema_description(markdown, entity_filter?, include_related?) -> dict
    async def get_latest_schema_description(entity_filter?, include_related?) -> dict | None
    async def get_schema_description_by_id(desc_id: int) -> dict | None
    async def update_schema_description(desc_id: int, markdown: str) -> dict

    # Управление промптами для AI-генерации чартов
    async def get_chart_prompt_template(name: str = "bitrix_context") -> dict | None  # Получение промпта по имени
    async def update_chart_prompt_template(name: str, content: str) -> dict  # Обновление промпта
```

**Автоматическое включение связанных таблиц:**

При запросе схемы для конкретной сущности автоматически включаются связанные справочные таблицы:

| Основная таблица | Связанные справочники |
|---|---|
| `crm_deals` | `ref_crm_statuses`, `ref_crm_deal_categories`, `ref_crm_currencies`, `ref_enum_values` |
| `crm_contacts` | `ref_crm_statuses`, `ref_enum_values` |
| `crm_leads` | `ref_crm_statuses`, `ref_enum_values` |
| `crm_companies` | `ref_crm_statuses`, `ref_enum_values` |
| `stage_history_deals` | `crm_deals`, `ref_crm_statuses`, `ref_crm_deal_categories` |
| `stage_history_leads` | `crm_leads`, `ref_crm_statuses` |

**Улучшенное отображение метаданных полей:**

- **Комментарии полей**: Все поля создаются с COMMENT, содержащим описание из Bitrix24
- **Enum-значения**: Для пользовательских полей (префикс `uf_crm_`) автоматически извлекаются возможные значения из `ref_enum_values`
- **В API**: `get_tables_info()` возвращает поле `description` для каждой колонки, включающее:
  - Комментарий из БД (если есть)
  - Список возможных значений для enum-полей (первые 10 значений)
- **В AI-контексте**: `get_schema_context()` передаёт расширенную информацию для генерации более точных описаний

#### ReferenceSyncService — синхронизация справочников:

```python
class ReferenceSyncService:
    async def sync_reference(ref_name: str) -> dict      # Синхронизация одного справочника
    async def sync_all_references() -> dict               # Синхронизация всех справочников
    async def sync_enum_userfields(entity_type, userfields) -> dict  # Синхронизация значений enum-полей
```

Справочные таблицы:

| Справочник | API метод | Таблица БД | Уникальный ключ |
|---|---|---|---|
| Статусы/стадии | `crm.status.list` | `ref_crm_statuses` | `(status_id, entity_id, category_id)` |
| Воронки сделок | `crm.dealcategory.list` | `ref_crm_deal_categories` | `(id)` |
| Валюты | `crm.currency.list` | `ref_crm_currencies` | `(currency)` |
| Значения enum-полей | из `userfield.list` → `LIST` | `ref_enum_values` | `(field_name, entity_type, item_id)` |

При `full_sync` CRM-сущности автоматически синхронизируются связанные справочники и значения enumeration-полей пользовательских полей (best-effort).

#### SelectorService — селекторы (фильтры) дашбордов:

```python
class SelectorService:
    # CRUD селекторов
    async def create_selector(dashboard_id, name, label, selector_type, operator, config?, mappings?) -> dict
    async def get_selector_by_id(selector_id) -> dict
    async def get_selectors_for_dashboard(dashboard_id) -> list[dict]
    async def update_selector(selector_id, **kwargs) -> dict
    async def delete_selector(selector_id) -> bool

    # CRUD маппингов (селектор → чарт + колонка)
    async def add_mapping(
        selector_id, dashboard_chart_id, target_column, target_table?, operator_override?,
        post_filter_resolve_table?, post_filter_resolve_column?, post_filter_resolve_id_column?,
    ) -> dict
    async def remove_mapping(mapping_id) -> bool

    # Построение фильтров для apply_filters()
    # - Резолвит date-токены (TODAY/LAST_30_DAYS/...) через date_tokens.resolve_filter_value
    # - Прокидывает post_filter_* поля в filter dict для двухшагового фильтра
    async def build_filters_for_chart(dashboard_id, dc_id, filter_values) -> list[dict]

    # Опции для dropdown/multi_select
    async def get_selector_options(selector_id) -> list  # SELECT DISTINCT или static_options; если config содержит label_table/label_column/label_value_column — LEFT JOIN с label-таблицей, возвращает [{value, label}]
    async def get_all_selector_options(dashboard_id) -> dict[int, list]  # Batch для всех селекторов
```

**Типы селекторов:** `date_range`, `single_date`, `dropdown`, `multi_select`, `text`

**Операторы:** `equals`, `not_equals`, `in`, `not_in`, `between`, `gt`, `lt`, `gte`, `lte`, `like`, `not_like`

**Механизм фильтрации (Approach A: WHERE Clause Injection):**
1. Пользователь на публичном дашборде меняет значения в селекторах (auto-apply с debounce, без кнопки).
2. Frontend отправляет `POST /public/dashboard/{slug}/chart/{dc_id}/data` с массивом фильтров.
3. Backend через `SelectorService.build_filters_for_chart()` находит маппинги для данного чарта и резолвит date-токены через `date_tokens.resolve_filter_value`.
4. `ChartService.apply_filters()` инъектирует `WHERE`/`AND` условия в SQL с bind-параметрами:
   - **Top-level scan**: WHERE/GROUP BY/ORDER BY ищутся только на depth=0 (учитывая скобки и string literals), чтобы не путать подзапросы и JOIN ON-clauses.
   - **Alias resolution**: `target_table` автоматически резолвится в реальный alias из SQL (`crm_deals` → `cd` если `FROM crm_deals cd`).
   - **End-of-day**: для `between`/`lte` дата-only значения (`YYYY-MM-DD`) автоматически расширяются до `YYYY-MM-DD 23:59:59`.
   - **post_filter сабзапрос**: при наличии `post_filter` в filter dict генерируется `WHERE col IN (SELECT id_col FROM resolve_table WHERE resolve_col <op> :p)`.
5. Модифицированный SQL выполняется через `execute_chart_query(sql, bind_params)`.
6. Если у чарта есть `chart_config.label_resolvers`, результат пропускается через `ChartService.resolve_labels_in_data()` для замены сырых ID на читаемые имена.

#### date_tokens — резолв динамических дат

```python
# app/domain/services/date_tokens.py
DATE_TOKENS: frozenset[str]  # TODAY, YESTERDAY, TOMORROW, LAST_7_DAYS, LAST_14_DAYS,
                             # LAST_30_DAYS, LAST_90_DAYS, THIS_MONTH_START, LAST_MONTH_START,
                             # THIS_QUARTER_START, LAST_QUARTER_START, THIS_YEAR_START,
                             # LAST_YEAR_START, YEAR_START

def is_date_token(value) -> bool
def is_date_only(value) -> bool       # Match ^\d{4}-\d{2}-\d{2}$
def resolve_token(value) -> str       # TODAY → "2026-04-06"; pass-through иначе
def resolve_filter_value(selector_type, value)  # Walk dict/list/scalar и резолвит токены
def extend_to_end_of_day(value)       # "2026-04-06" → "2026-04-06 23:59:59"
```

**Зеркало на frontend**: `frontend/src/utils/dateTokens.ts` содержит идентичные константы и функции (`DATE_TOKENS`, `resolveDateToken`, `resolveFilterValue`, `tokenLabel`). Бэкенд резолвит токены в `build_filters_for_chart`, фронт — в `SelectorBar` перед отправкой запроса (для отображения и опционального быстрого пути).

#### Сущность Call (Телефония)

Синхронизация истории звонков из Bitrix24 Voximplant:

| Параметр | Значение |
|---|---|
| API метод | `voximplant.statistic.get` |
| Таблица БД | `bitrix_calls` |
| Уникальный ключ | `CALL_ID` → `bitrix_id` |
| Инкрементальная синхронизация | По полю `CALL_START_DATE` |
| Пользовательские поля (UF_*) | Не поддерживаются |
| Webhooks | Не поддерживаются (нет событий изменения) |
| Определения полей | Захардкожены в `CALL_FIELD_TYPES` (нет API `.fields`) |

#### Сущность StageHistory (История движения по стадиям)

Синхронизация истории движения сделок и лидов по стадиям/статусам:

| Параметр | Значение |
|---|---|
| API метод | `crm.stagehistory.list` |
| Таблицы БД | `stage_history_deals`, `stage_history_leads` |
| Уникальный ключ | `ID` → `history_id` |
| Инкрементальная синхронизация | По полю `CREATED_TIME` |
| Пользовательские поля (UF_*) | Не поддерживаются |
| Webhooks | Не поддерживаются напрямую (можно использовать `onCrmDealUpdate`/`onCrmLeadUpdate` как триггер) |
| Определения полей | Захардкожены в `STAGE_HISTORY_FIELD_TYPES` (нет API `.fields`) |
| Особенности | Использует `get_all()` для автоматической пагинации. Для сделок используются поля `STAGE_*`, для лидов — `STATUS_*` |
| Типы записей (TYPE_ID) | 1=создание элемента, 2=промежуточная стадия, 3=финальная стадия, 5=смена воронки |
| Semantic ID | P=промежуточная стадия, S=успешная, F=провальная |

### 3. Infrastructure Layer (`app/infrastructure/`)

```
app/infrastructure/
├── bitrix/
│   └── client.py            # BitrixClient с retry и rate limiting
├── database/
│   ├── connection.py        # AsyncEngine, get_session, get_dialect()
│   ├── models.py            # SQLAlchemy модели (SyncConfig, SyncLog, SyncState, AIChart, SchemaDescription, ChartPromptTemplate, PublishedDashboard, DashboardChart, DashboardLink, DashboardSelector, SelectorChartMapping)
│   └── dynamic_table.py     # Динамическое создание таблиц (кросс-БД, с комментариями полей)
└── scheduler/
    └── scheduler.py         # APScheduler для периодической синхронизации

alembic/
├── env.py                   # Alembic environment (async)
└── versions/
    ├── 001_create_system_tables.py  # Initial migration (кросс-БД)
    ├── 002_create_ai_charts_table.py  # Таблица ai_charts для сохранённых чартов
    ├── 003_create_schema_descriptions_table.py  # Таблица schema_descriptions для истории генерации схем
    ├── 004_create_dashboards_tables.py  # Таблицы published_dashboards, dashboard_charts
    ├── 005_add_refresh_interval.py  # Добавление refresh_interval_minutes в published_dashboards
    ├── 006_create_dashboard_links_table.py  # Таблица dashboard_links (связи между дашбордами)
    ├── 007_create_dashboard_selectors_tables.py  # Таблицы dashboard_selectors, selector_chart_mappings
    ├── 008_create_stage_history_tables.py  # Таблицы stage_history_deals, stage_history_leads (история движения по стадиям)
    ├── 009_create_chart_prompts_table.py  # Таблица chart_prompt_templates с дефолтным Bitrix-промптом
    ├── 010_add_records_fetched_to_sync_logs.py
    ├── 011_create_reports_tables.py
    ├── 012_create_published_reports_tables.py
    ├── 013_add_llm_prompt_to_report_runs.py
    ├── 014_stub.py
    ├── 015_stub.py
    ├── 016_add_post_filter_to_mappings.py  # post_filter_resolve_table/_column/_id_column в selector_chart_mappings
    ├── 017_add_dashboard_heading_items.py  # Полиморфные элементы dashboard_charts: item_type, heading_config, nullable chart_id
    ├── 018_add_tab_label_to_dashboards.py  # Колонка tab_label в published_dashboards
    └── 019_add_hide_title_to_dashboard_charts.py  # Колонка hide_title в dashboard_charts
```

#### connection.py — ключевые функции:

```python
async def init_db() -> None       # Инициализация engine по DATABASE_URL
def get_engine()                   # Получить AsyncEngine
def get_dialect() -> str           # "postgresql" или "mysql"
async def get_session()            # Dependency для FastAPI
```

### 4. Core Layer (`app/core/`)

```
app/core/
├── auth.py                  # JWT валидация (опциональная)
├── exceptions.py            # Кастомные исключения (AppException, AIServiceError, ChartServiceError и др.)
├── logging.py               # Structlog конфигурация
└── webhooks.py              # Парсинг Bitrix24 webhooks

backend/
├── entrypoint.sh           # Docker entrypoint с проверкой БД через SQLAlchemy
├── Dockerfile              # Контейнер с поддержкой PG и MySQL
└── alembic.ini             # Alembic конфигурация
```

## Конфигурация

### Переменные окружения

```python
class Settings(BaseSettings):
    # Application
    app_name: str = "Bitrix Sync Service"
    debug: bool = False
    environment: Literal["development", "staging", "production"]

    # Database (PostgreSQL или MySQL)
    database_url: str          # postgresql+asyncpg://... или mysql+aiomysql://...
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Bitrix24
    bitrix_webhook_url: str    # https://xxx.bitrix24.ru/rest/1/xxx/

    # Sync
    sync_batch_size: int = 50
    sync_default_interval_minutes: int = 30

    # AI / LLM Provider
    # Поддерживаются OpenAI и любой OpenAI-compatible провайдер (например OpenRouter).
    llm_provider: Literal["openai", "openrouter"] = "openai"
    openai_api_key: str = ""           # API key для выбранного провайдера
    openai_model: str = "gpt-4o-mini"  # Для OpenRouter — qualified id, e.g. "openai/gpt-4o-mini"
    openai_timeout_seconds: int = 300
    llm_base_url: str = ""             # Override; auto = api.openai.com / openrouter.ai/api
    openrouter_app_url: str = ""       # HTTP-Referer для OpenRouter dashboard
    openrouter_app_title: str = ""     # X-Title для OpenRouter dashboard

    @property
    def resolved_llm_base_url(self) -> str
        # openai     → https://api.openai.com/v1
        # openrouter → https://openrouter.ai/api/v1
        # llm_base_url переопределяет авто-выбор

    # Charts
    chart_query_timeout_seconds: int = 5
    chart_max_rows: int = 10000

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

    @property
    def db_dialect(self) -> str  # Автоопределение: "postgresql" или "mysql"
```

## Docker Compose

```yaml
services:
  backend:     # FastAPI + SQLAlchemy (подключается к внешней БД по DATABASE_URL)
  frontend:    # React (Vite + nginx)
```

БД **не входит** в docker-compose — используется внешняя PostgreSQL или MySQL.

## Системные таблицы

### schema_descriptions

Таблица для хранения истории AI-генерации описаний схемы БД:

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | BIGINT (PK) | Уникальный идентификатор |
| `markdown` | TEXT | Сгенерированная документация в формате Markdown |
| `entity_filter` | TEXT (nullable) | Список таблиц через запятую (для фильтрации) |
| `include_related` | BOOLEAN | Флаг включения связанных справочных таблиц |
| `created_at` | TIMESTAMP | Дата создания |
| `updated_at` | TIMESTAMP | Дата последнего обновления |

### ai_charts

Таблица для хранения сохранённых чартов:

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | BIGINT (PK) | Уникальный идентификатор |
| `title` | VARCHAR(255) | Название чарта |
| `description` | TEXT (nullable) | Описание |
| `user_prompt` | TEXT | Исходный промпт пользователя |
| `chart_type` | VARCHAR(50) | Тип чарта (bar/line/pie/area/scatter/indicator/table/funnel/horizontal_bar) |
| `chart_config` | JSON | Конфигурация чарта (см. поля ниже) |
| `sql_query` | TEXT | SQL-запрос для получения данных |
| `is_pinned` | BOOLEAN | Флаг закрепления |
| `created_by` | VARCHAR(255) (nullable) | Автор |
| `created_at` | TIMESTAMP | Дата создания |
| `updated_at` | TIMESTAMP | Дата последнего обновления |

**`chart_config` JSON** (свободная схема, ключевые поля):

| Ключ | Назначение |
|---|---|
| `x`, `y`, `colors` | Data keys и палитра |
| `legend`, `grid`, `xAxis`, `yAxis`, `line`, `area`, `pie`, `indicator`, `table`, `funnel`, `horizontal_bar`, `cardStyle`, `general`, `designLayout` | Visual config (см. `frontend/src/services/api.ts:ChartDisplayConfig`) |
| `label_resolvers` | Опциональный массив правил пост-обработки результата чарта: `[{column, resolve_table, resolve_value_column?, resolve_label_column}]`. Backend (`ChartService.resolve_labels_in_data`) загружает `SELECT value, label FROM resolve_table` один раз на resolver и заменяет сырые ID в указанной колонке `column` на читаемые имена. Полезно когда SQL чарта возвращает `assigned_by_id`, а пользователь хочет видеть имя менеджера |

### chart_prompt_templates

Таблица для хранения системных промптов для AI-генерации чартов:

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | BIGINT (PK) | Уникальный идентификатор |
| `name` | VARCHAR(100) (unique) | Имя промпта (например, `bitrix_context`) |
| `content` | TEXT | Содержимое промпта с инструкциями для AI |
| `is_active` | BOOLEAN | Флаг активности промпта |
| `created_at` | TIMESTAMP | Дата создания |
| `updated_at` | TIMESTAMP | Дата последнего обновления |

**Назначение**: Хранит пользовательские инструкции для AI при генерации чартов. Промпт `bitrix_context` содержит специфичные инструкции по работе с данными Bitrix24 (например, как рассчитывать конверсию по стадиям, получать воронку продаж, анализировать время в стадиях). При первом запуске автоматически создается стандартный промпт. Пользователь может редактировать его через API.

### dashboard_charts

Полиморфная таблица элементов дашборда: одна строка может быть либо ссылкой на чарт (`item_type='chart'`), либо текстовым заголовком (`item_type='heading'`).

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | BIGINT (PK) | Уникальный идентификатор элемента дашборда |
| `dashboard_id` | BIGINT (FK → published_dashboards) | Дашборд-владелец (CASCADE delete) |
| `chart_id` | BIGINT (FK → ai_charts) **NULLable** | Ссылка на сохранённый чарт. NULL для `item_type='heading'`. CASCADE delete |
| `item_type` | VARCHAR(20) | Тип элемента: `chart` (по умолчанию) или `heading` |
| `heading_config` | JSON (nullable) | Параметры заголовка для `item_type='heading'`: `{text, level (1-6), align ('left'|'center'|'right'), color, bg_color, divider}`. NULL для `item_type='chart'` |
| `title_override` | VARCHAR(255) (nullable) | Переопределение заголовка чарта на дашборде |
| `description_override` | TEXT (nullable) | Переопределение описания чарта на дашборде |
| `hide_title` | BOOLEAN NOT NULL DEFAULT FALSE | Скрыть заголовок элемента (полезно для индикаторов) |
| `layout_x` | INTEGER | Координата X в grid-layout |
| `layout_y` | INTEGER | Координата Y в grid-layout |
| `layout_w` | INTEGER | Ширина (column units) |
| `layout_h` | INTEGER | Высота (row units) |
| `sort_order` | INTEGER | Порядок отображения |
| `created_at` | TIMESTAMP | Дата создания |

**Полиморфность**: чарт и heading хранятся в одной таблице, чтобы единый layout (`layout_x/y/w/h`) и порядок (`sort_order`) могли применяться к обоим типам элементов. Запросы данных (`/chart/{dc_id}/data`) валидируют `item_type='chart'` и возвращают 400 для heading. Frontend ветвится по `item_type` при рендере (`HeadingItem` vs `ChartCard`).

### dashboard_selectors

Таблица селекторов (фильтров) дашбордов:

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | BIGINT (PK) | Уникальный идентификатор |
| `dashboard_id` | BIGINT (FK → published_dashboards) | Дашборд-владелец |
| `name` | VARCHAR(100) | Внутреннее имя (unique per dashboard) |
| `label` | VARCHAR(255) | Отображаемое название |
| `selector_type` | VARCHAR(30) | Тип: date_range / single_date / dropdown / multi_select / text |
| `operator` | VARCHAR(30) | Оператор по умолчанию: equals / between / in / like и др. |
| `config` | JSON (nullable) | Конфигурация селектора (см. ниже) |
| `sort_order` | INTEGER | Порядок отображения |
| `is_required` | BOOLEAN | Обязательность фильтра |
| `created_at` | TIMESTAMP | Дата создания |

**UNIQUE** constraint: `(dashboard_id, name)`

**`config` JSON** — поля:

| Ключ | Назначение |
|---|---|
| `static_values` | Массив `[{value, label}]` для статичного dropdown / multi_select |
| `source_table` + `source_column` | DB-источник опций для dropdown / multi_select (`SELECT DISTINCT`) |
| `label_table` + `label_column` + `label_value_column` | LEFT JOIN для подстановки labels к опциям из source_table |
| `default_value` | Дефолтное значение, применяется на frontend при инициализации `SelectorBar`. Для `date_range` — `{from, to}` где значения могут быть **date-токенами** (`TODAY`, `LAST_30_DAYS`, ...). Для `single_date`/`dropdown`/`text` — строка. Резолв токенов выполняется backend'ом в `build_filters_for_chart` и frontend'ом в `dateTokens.resolveFilterValue` |
| `placeholder` | Подсказка для UI |

### selector_chart_mappings

Маппинг селекторов на колонки чартов:

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | BIGINT (PK) | Уникальный идентификатор |
| `selector_id` | BIGINT (FK → dashboard_selectors) | Родительский селектор |
| `dashboard_chart_id` | BIGINT (FK → dashboard_charts) | Целевой чарт на дашборде |
| `target_column` | VARCHAR(255) | Колонка в SQL чарта (date_create, closedate и др.) |
| `target_table` | VARCHAR(255) (nullable) | Таблица для disambiguation в JOIN. `apply_filters` автоматически резолвит её в реальный alias из SQL чарта |
| `operator_override` | VARCHAR(30) (nullable) | Переопределение оператора для этого чарта |
| `post_filter_resolve_table` | VARCHAR(255) (nullable) | Двухшаговая фильтрация: вспомогательная таблица для резолва значения селектора. Если задано — `apply_filters` генерирует `WHERE target_column IN (SELECT post_filter_resolve_id_column FROM post_filter_resolve_table WHERE post_filter_resolve_column <op> :p)` |
| `post_filter_resolve_column` | VARCHAR(255) (nullable) | Колонка в `post_filter_resolve_table`, по которой фильтруется значение селектора |
| `post_filter_resolve_id_column` | VARCHAR(255) (nullable) | Колонка в `post_filter_resolve_table`, чьи значения подставляются в `target_column`. Default — `id` |
| `created_at` | TIMESTAMP | Дата создания |

**UNIQUE** constraint: `(selector_id, dashboard_chart_id)` — один маппинг на пару селектор-чарт

**Пример post_filter** — у чарта `SELECT count(*) FROM stage_history_deals` нет колонки `assigned_by_id`, но есть `owner_id`. Чтобы фильтр менеджера работал, маппинг указывает: `target_column = "owner_id"`, `post_filter_resolve_table = "crm_deals"`, `post_filter_resolve_column = "assigned_by_id"`, `post_filter_resolve_id_column = "id"`. Сгенерированный SQL:
```sql
WHERE owner_id IN (SELECT id FROM crm_deals WHERE assigned_by_id = :sf0)
```

## Маппинг типов Bitrix24 → Database

| Bitrix24 Type | SQLAlchemy Type | SQL Type |
|---------------|-----------------|----------|
| `string` | `String` | `VARCHAR(255)` |
| `text` | `Text` | `TEXT` |
| `integer` | `BigInteger` | `BIGINT` |
| `double` | `Float` | `FLOAT` |
| `boolean` | `Boolean` | `BOOLEAN` |
| `datetime` | `DateTime` | `TIMESTAMP` |
| `enumeration` | `String` | `VARCHAR(255)` |
| `crm_multifield` | `String` | `VARCHAR(255)` |
| multiple fields | `Text` | `TEXT` (JSON) |

## Зависимости

### Основные

| Пакет | Версия | Назначение |
|-------|--------|------------|
| fastapi | ≥0.115.0 | Web framework |
| uvicorn | ≥0.32.0 | ASGI server |
| sqlalchemy | ≥2.0.0 | ORM + async |
| asyncpg | ≥0.30.0 | PostgreSQL async driver |
| aiomysql | ≥0.2.0 | MySQL async driver |
| alembic | ≥1.13.0 | Database migrations |
| fast-bitrix24 | ≥1.8.0 | Bitrix24 API client |
| pydantic-settings | ≥2.0.0 | Settings management |
| python-jose | ≥3.3.0 | JWT handling |
| apscheduler | ≥3.10.0 | Task scheduling |
| tenacity | ≥8.2.0 | Retry logic |
| structlog | ≥24.0.0 | Structured logging |
| httpx | ≥0.27.0 | Async HTTP client |
| openai | ≥1.0 | OpenAI API client |

### Frontend

| Пакет | Версия | Назначение |
|-------|--------|------------|
| react | ^18.3.0 | UI framework |
| react-router-dom | ^6.26.0 | Routing |
| @tanstack/react-query | ^5.51.0 | Server state management |
| axios | ^1.7.0 | HTTP client |
| zustand | ^4.5.0 | Client state management |
| recharts | ^2.12.0 | Chart library (SVG, responsive) |
| react-markdown | ^9.0.0 | Markdown rendering |
| tailwindcss | ^3.4.0 | CSS framework |

## Frontend Architecture

```
frontend/src/
├── App.tsx                    # Роутинг (/charts, /schema, /config, /monitoring, /validation)
├── components/
│   ├── Layout.tsx             # Навигация (Dashboard, AI Charts, Configuration, Monitoring, Validation, Schema)
│   ├── SyncCard.tsx           # Карточка синхронизации CRM-сущности
│   ├── ReferenceCard.tsx      # Карточка справочника (статусы, воронки, валюты)
│   ├── charts/
│   │   ├── ChartRenderer.tsx  # Универсальный рендер чарта (bar/line/pie/area/scatter/funnel/horizontal_bar через Recharts, indicator — KPI-карточка, table — таблица с итогами и сортировкой). Опциональный проп fontScale?: number — масштабирует ticks, axis labels, legend, data labels, pie label, indicator value и table cells через helper fs(base)=max(8, round(base*fontScale)). При fontScale==null — IndicatorRenderer использует py-8, TableRenderer сохраняет text-sm на <table> (non-TV режим байт-стабилен относительно master)
│   │   ├── ChartSettingsPanel.tsx # Панель настроек отображения чарта (цвета, оси, legend, grid, настройки для каждого типа)
│   │   ├── ChartCard.tsx      # Карточка сохранённого чарта с действиями (pin/refresh/settings/SQL/edit-SQL/embed/delete). Кнопка "Изменить" открывает SqlEditorModal
│   │   ├── SqlEditorModal.tsx # Модалка редактирования SQL сохранённого чарта: textarea с текущим SQL, панель AI "Что изменить?" (POST /charts/{id}/refine-sql-ai вставляет результат в редактор), кнопка "Предпросмотр" (POST /charts/execute-sql, таблица первых 50 строк), "Сохранить" (PATCH /charts/{id}/sql)
│   │   ├── PromptEditorModal.tsx  # Модальное окно редактирования Bitrix-промпта для AI (markdown-редактор)
│   │   └── AvailableChartTypesModal.tsx # Модальное окно со списком всех доступных типов графиков (bar, horizontal_bar, line, area, pie, scatter, funnel, indicator, table) с описанием и примером промпта для каждого типа. Открывается из ChartsPage кнопкой "Доступные графики"
│   ├── dashboards/
│   │   ├── DashboardCard.tsx  # Карточка дашборда в списке
│   │   ├── PasswordGate.tsx   # Форма ввода пароля для публичного дашборда
│   │   ├── PublishModal.tsx   # Модальное окно публикации дашборда
│   │   ├── HeadingItem.tsx    # Полиморфный элемент-заголовок дашборда: динамический тег h1-h6, выравнивание, цвет текста и фона, разделитель. В editable режиме — inline-edit текста (input, blur/Enter/Esc) и popover ⚙ с настройками level/align/color/bg/divider. Read-only в embed. Опциональный fontScale?: number — при значении != 1 применяет inline fontSize = baseRem[level] * fontScale rem (Tailwind text-3xl..text-sm остаётся как fallback); при undefined/1 — mergedTitleStyle === titleStyle (не-TV режим байт-стабилен).
│   │   └── TvModeGrid.tsx     # TV-режим публичного дашборда: интерактивный react-grid-layout (24 колонки, адаптивный rowHeight = max(20, innerHeight/24)), merge layout из localStorage[tv_layout_<storageKey>] и дефолта из dc.layout_* (миграция 12→24: x*2, w*2). Внутренний TvCellMeasurer через useElementSize вычисляет fontScale = clamp(0.4, 2.5, sqrt(w*h)/350) и chartHeight = max(60, h-44), прокидывает в renderChart/renderHeading колбэки родителя. Persist layout в localStorage обёрнут в try/catch. Использует useContainerWidth + mounted гард. Все элементы имеют minW=1, minH=1 (без maxH) — даже headings — чтобы в TV-режиме можно было ужимать без ограничений.
│   └── selectors/
│       ├── SelectorBar.tsx        # Панель фильтров: auto-apply (debounce 250 мс / text 500 мс), инициализация дефолтов из config.default_value (резолв date-токенов), кнопка Reset. Опционально linkedSlug — берёт опции через linked endpoint
│       ├── DateRangeSelector.tsx  # Два input[date] (from/to) + token-based пресеты (TODAY/LAST_7_DAYS/LAST_30_DAYS/THIS_QUARTER_START)
│       ├── SingleDateSelector.tsx # Один input[date], при value-токене резолвит через resolveDateToken
│       ├── DropdownSelector.tsx   # select с опциями из API или static
│       ├── MultiSelectSelector.tsx # Multi-select с чекбоксами и dropdown
│       ├── TextSelector.tsx       # input[text] с placeholder и debounce
│       ├── SelectorBoardDialog.tsx # ReactFlow-редактор маппингов: типы, источник данных, default value (token dropdown), edge popup с post_filter_resolve_table/_column/_id_column
│       ├── SelectorEditorSection.tsx # CRUD селекторов на DashboardEditorPage + кнопка "AI: сгенерировать" с превью и выборочным принятием
│       ├── SelectorConfigPanel.tsx # Левая панель редактора селектора (тип, имя, label, источник, labels)
│       ├── SqlPreviewPanel.tsx     # Превью оригинального и фильтрованного SQL
│       └── nodes/                  # SelectorNode, ChartNode, MappingEdge для ReactFlow
├── pages/
│   ├── DashboardPage.tsx      # Обзор синхронизации
│   ├── ChartsPage.tsx         # AI-генерация чартов + список сохранённых
│   ├── SchemaPage.tsx         # AI-описание схемы + редактирование + копирование + сырая структура таблиц с описаниями
│   ├── ConfigPage.tsx         # Настройки синхронизации
│   ├── MonitoringPage.tsx     # Мониторинг
│   ├── ValidationPage.tsx     # Валидация данных
│   ├── EmbedDashboardPage.tsx # Публичный дашборд: аутентификация, вкладки (linked-дашборды), авто-обновление, per-tab селекторы и per-tab filterValuesByTab (фильтры главного и вторичных табов хранятся раздельно). Полиморфный рендер dashboard.charts: ветка item_type==='heading' рендерит HeadingItem (read-only) в позицию gridStyle, остальные — DashboardChartCard. Фильтрует heading из fetchAllChartData/fetchLinkedChartData чтобы не делать запросы /chart/{id}/data. TV-режим (?tv=1 через useTvMode): чекбокс «Режим ТВ» и кнопка «Сбросить макет» в шапке (handleTvReset чистит localStorage[tv_layout_<storageKey>] и инкрементит tvKey для remount); при tvMode внешний контейнер становится fullscreen (p-2 / w-full, description скрыт); inline-функции renderTvChartCard(dc, fontScale, chartHeight) и renderTvHeading(dc, fontScale) повторяют логику DashboardChartCard/HeadingItem с inline fontSize=Math.round(14*fontScale)px и прокидывают fontScale в ChartRenderer/HeadingItem; условный рендер: tvMode → <TvModeGrid key={tvKey + '_' + tvStorageKey} storageKey charts chartData renderChart renderHeading />, иначе исходный CSS-grid без изменений. tvStorageKey = activeTab === 'main' ? slug : activeTab — каждый linked-таб хранит свой layout отдельно.
│   └── DashboardEditorPage.tsx # Редактор дашборда: grid-layout, override, ссылки, SelectorEditorSection (CRUD фильтров + маппинги + AI генерация). Toolbar кнопки "+ Чарт" (открывает AddChartPickerModal — модалка через createPortal со списком сохранённых чартов от chartsApi.list, поиск, фильтр уже добавленных, handleAddChart через useAddDashboardChart) и "+ Заголовок" (handleAddHeading через useAddDashboardHeading). Полиморфный рендер dashboard.charts: ветка item_type==='heading' использует EditorHeadingCard (HeadingItem editable + кнопка удаления), остальные — EditorChartCard. gridLayout для heading элементов задаёт minH=1, minW=2, maxH=4 (chart остаётся minW=2, minH=2). Загрузка chart-данных пропускает heading элементы. TV-режим (?tv=1 через useTvMode): чекбокс «Режим ТВ» в шапке делегирует рендер грида к <TvModeGrid> (24 колонки, adaptive rowHeight, localStorage layout под storageKey=dashboard.slug) чтобы editor-preview был байт-идентичен публичному дашборду в TV-режиме. Inline-функции renderTvChartCard/renderTvHeading зеркалят EmbedDashboardPage. tvPreviewCharts наложены из gridLayout (несохранённые drag-изменения видны в preview). В non-TV режиме используется локальный ReactGridLayout (12 колонок, ROW_HEIGHT=120) для in-place редактирования. EditorChartCard/EditorHeadingCard рендерятся только в non-TV (TV использует единый рендер с публичным).
├── hooks/
│   ├── useSync.ts             # React Query хуки для синхронизации и справочников
│   ├── useCharts.ts           # React Query хуки для чартов, схемы, истории генерации и промптов (useChartPromptTemplate, useUpdateChartPromptTemplate, useUpdateChartConfig, useUpdateChartSql для PATCH /sql, useRefineChartSqlWithAi для POST /refine-sql-ai)
│   ├── useDashboards.ts       # React Query хуки для CRUD дашбордов, layout, ссылок, паролей. Heading-хуки: useAddDashboardHeading, useUpdateDashboardHeading (инвалидируют ['dashboard', dashboardId]). Chart-add-хук: useAddDashboardChart (инвалидирует ['dashboard', dashboardId] и ['dashboards'])
│   ├── useSelectors.ts        # React Query хуки для CRUD селекторов, маппингов, опций, AI-генерации, колонок чартов
│   ├── useAuth.ts             # Хук авторизации
│   ├── useElementSize.ts      # Generic ResizeObserver-хук: возвращает {ref,width,height} для любого HTMLElement, useLayoutEffect, contentRect, disconnect on unmount (используется TvModeGrid)
│   └── useTvMode.ts           # Синхронизация булевого tvMode ↔ URL ?tv=1 (lazy init, history.replaceState, popstate-listener; без react-router) — для TV-режима EmbedDashboardPage
├── utils/
│   ├── dateTokens.ts          # Зеркало backend date_tokens.py: DATE_TOKENS, resolveDateToken, resolveFilterValue, isDateOnly, isDateToken, tokenLabel
│   └── clipboard.ts           # copyToClipboard(text): обёртка над navigator.clipboard.writeText с fallback на document.execCommand('copy') через off-screen textarea — работает на HTTP и в браузерах без Clipboard API
├── services/
│   └── api.ts                 # Axios клиент, типы, API-объекты (syncApi, referencesApi, chartsApi, schemaApi, dashboardsApi, publicApi). Типы DashboardSelector, SelectorMapping (с post_filter_resolve_*), LabelResolver, FilterValue. Полиморфный DashboardChart (item_type='chart'|'heading', chart_id?, heading_config?). Heading-типы: HeadingConfig (text, level 1-6, align, color, bg_color, divider), HeadingCreateRequest, HeadingUpdateRequest. Endpoints: dashboardsApi.generateSelectors(dashboardId, userRequest?, chartIds?) — chartIds ограничивает AI-генерацию подмножеством чартов, dashboardsApi.addHeading, dashboardsApi.updateHeading, publicApi.getLinkedPublicSelectorOptionsBatch
└── store/
    ├── authStore.ts           # Zustand store авторизации
    └── syncStore.ts           # Zustand store синхронизации
```

## Date Tokens

Динамические токены, которые можно использовать в `selector.config.default_value` или в любом значении фильтра при ручной отправке. Backend (`date_tokens.resolve_filter_value`) и frontend (`utils/dateTokens.ts`) резолвят их идентично — список и реализация должны оставаться синхронными.

| Токен | Резолв |
|---|---|
| `TODAY` | Сегодня |
| `YESTERDAY` | Вчера |
| `TOMORROW` | Завтра |
| `LAST_7_DAYS` | -7 дней от сегодня |
| `LAST_14_DAYS` | -14 дней |
| `LAST_30_DAYS` | -30 дней |
| `LAST_90_DAYS` | -90 дней |
| `THIS_MONTH_START` | 1-е число текущего месяца |
| `LAST_MONTH_START` | 1-е число прошлого месяца |
| `THIS_QUARTER_START` | 1-е число текущего квартала |
| `LAST_QUARTER_START` | 1-е число прошлого квартала |
| `THIS_YEAR_START` / `YEAR_START` | 1 января текущего года |
| `LAST_YEAR_START` | 1 января прошлого года |

**Пример selector config:**
```json
{
  "default_value": { "from": "LAST_30_DAYS", "to": "TODAY" }
}
```

**End-of-day**: для `between`/`lte` дата-only значения (`YYYY-MM-DD`) в `apply_filters` автоматически расширяются до `YYYY-MM-DD 23:59:59`, чтобы фильтр включал весь день.

## Nginx (frontend container)

`frontend/nginx.conf` проксирует `/api/` на `http://backend:8080`. AI-генерация и анализ отчётов могут занимать длительное время, поэтому установлены увеличенные таймауты:

```nginx
proxy_connect_timeout 10s;
proxy_send_timeout    600s;
proxy_read_timeout    600s;
```

Это синхронизировано с `openai_timeout_seconds = 300` в backend, чтобы клиент не получал 504 от nginx раньше, чем backend получит ответ от LLM.

## Примеры использования API

### Получение схемы для конкретной сущности с автоматическим включением справочников

**Получить схему только для сделок (включая все связанные справочники):**
```bash
GET /api/v1/schema/tables?entity_tables=crm_deals&include_related=true
```
Вернёт таблицы: `crm_deals`, `ref_crm_statuses`, `ref_crm_deal_categories`, `ref_crm_currencies`, `ref_enum_values`

**Получить AI-описание схемы для нескольких сущностей:**
```bash
GET /api/v1/schema/describe?entity_tables=crm_deals,crm_contacts&include_related=true
```
Вернёт описание для: `crm_deals`, `crm_contacts` + все связанные справочники

**Получить markdown-описание схемы без AI (быстро, из метаданных БД):**
```bash
GET /api/v1/schema/describe-raw?entity_tables=crm_deals&include_related=true
```
Вернёт markdown с таблицами полей, типов и описаний. Сохраняется в `schema_descriptions`.

**Получить только основные таблицы без справочников:**
```bash
GET /api/v1/schema/tables?entity_tables=crm_deals&include_related=false
```
Вернёт только: `crm_deals`

### Генерация чартов

Генерация чартов использует:
1. **Описание схемы БД** из `schema_descriptions` (последнее сохранённое)
2. **Bitrix-промпт** из `chart_prompt_templates` (инструкции по работе с данными Bitrix24)

Если описание схемы ещё не было сгенерировано, endpoint вернёт ошибку 400 с просьбой сначала вызвать `GET /api/v1/schema/describe`.

**Создать чарт:**
```json
POST /api/v1/charts/generate
{
  "prompt": "Количество сделок по стадиям воронки"
}
```
AI получит markdown из последней генерации описания схемы + Bitrix-промпт с инструкциями как контекст для построения SQL-запроса.

**Получить текущий промпт:**
```bash
GET /api/v1/charts/prompt-template/bitrix-context
```

**Обновить промпт:**
```json
PUT /api/v1/charts/prompt-template/bitrix-context
{
  "content": "# Ваши инструкции для AI\n..."
}
```
После обновления промпта все последующие генерации чартов будут использовать новые инструкции.
