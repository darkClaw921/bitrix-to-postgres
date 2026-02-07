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
│   ├── __init__.py          # Роутер версии API (sync, webhooks, status, charts, schema, references)
│   ├── endpoints/
│   │   ├── sync.py          # Эндпоинты синхронизации
│   │   ├── webhooks.py      # Обработка webhooks от Bitrix24
│   │   ├── status.py        # Статус и health checks
│   │   ├── charts.py        # AI-генерация и CRUD чартов
│   │   ├── schema_description.py  # AI-описание и raw-описание схемы БД
│   │   └── references.py    # Синхронизация справочных данных (статусы, воронки, валюты)
│   └── schemas/
│       ├── sync.py          # Pydantic схемы для sync
│       ├── webhooks.py      # Схемы webhooks
│       ├── common.py        # Общие схемы
│       ├── charts.py        # Схемы чартов (ChartSpec, ChartGenerateRequest/Response и др.)
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
| `POST` | `/api/v1/charts/save` | Сохранение чарта |
| `GET` | `/api/v1/charts/list` | Список сохранённых чартов |
| `GET` | `/api/v1/charts/{id}/data` | Обновление данных чарта |
| `DELETE` | `/api/v1/charts/{id}` | Удаление чарта |
| `POST` | `/api/v1/charts/{id}/pin` | Закрепить/открепить чарт |
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
│   └── reference.py         # Реестр справочных типов (ReferenceType, ReferenceFieldDef)
├── services/
│   ├── sync_service.py      # Основная логика синхронизации (+ авто-синхронизация справочников)
│   ├── reference_sync_service.py  # Синхронизация справочных таблиц (статусы, воронки, валюты)
│   ├── field_mapper.py      # Маппинг полей Bitrix → DB (кросс-БД совместимый)
│   ├── ai_service.py        # Взаимодействие с OpenAI API (генерация чартов, описание схемы)
│   └── chart_service.py     # SQL-валидация, выполнение запросов, CRUD чартов
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
    async def generate_chart_spec(prompt: str, schema_context: str) -> dict
    async def generate_schema_description(schema_context: str) -> str
```

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
    async def get_allowed_tables() -> list[str]  # Включает crm_* и ref_* таблицы
    async def generate_schema_markdown(table_filter?, include_related=True) -> str  # Генерация markdown из метаданных БД (без AI)

    # Выполнение запросов
    async def execute_chart_query(sql: str) -> tuple[list[dict], float]

    # CRUD чартов
    async def save_chart(data: dict) -> dict
    async def get_charts(page, per_page) -> tuple[list[dict], int]
    async def delete_chart(chart_id: int) -> bool
    async def toggle_pin(chart_id: int) -> dict

    # CRUD описаний схемы
    async def get_any_latest_schema_description() -> dict | None  # Последнее описание без фильтров (для генерации чартов)
    async def save_schema_description(markdown, entity_filter?, include_related?) -> dict
    async def get_latest_schema_description(entity_filter?, include_related?) -> dict | None
    async def get_schema_description_by_id(desc_id: int) -> dict | None
    async def update_schema_description(desc_id: int, markdown: str) -> dict
```

**Автоматическое включение связанных таблиц:**

При запросе схемы для конкретной сущности автоматически включаются связанные справочные таблицы:

| Основная таблица | Связанные справочники |
|---|---|
| `crm_deals` | `ref_crm_statuses`, `ref_crm_deal_categories`, `ref_crm_currencies`, `ref_enum_values` |
| `crm_contacts` | `ref_crm_statuses`, `ref_enum_values` |
| `crm_leads` | `ref_crm_statuses`, `ref_enum_values` |
| `crm_companies` | `ref_crm_statuses`, `ref_enum_values` |

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

### 3. Infrastructure Layer (`app/infrastructure/`)

```
app/infrastructure/
├── bitrix/
│   └── client.py            # BitrixClient с retry и rate limiting
├── database/
│   ├── connection.py        # AsyncEngine, get_session, get_dialect()
│   ├── models.py            # SQLAlchemy модели (SyncConfig, SyncLog, SyncState, AIChart, SchemaDescription)
│   └── dynamic_table.py     # Динамическое создание таблиц (кросс-БД, с комментариями полей)
└── scheduler/
    └── scheduler.py         # APScheduler для периодической синхронизации

alembic/
├── env.py                   # Alembic environment (async)
└── versions/
    ├── 001_create_system_tables.py  # Initial migration (кросс-БД)
    ├── 002_create_ai_charts_table.py  # Таблица ai_charts для сохранённых чартов
    └── 003_create_schema_descriptions_table.py  # Таблица schema_descriptions для истории генерации схем
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

    # AI / OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

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
| `chart_type` | VARCHAR(50) | Тип чарта (bar/line/pie/area/scatter) |
| `chart_config` | JSON | Конфигурация чарта |
| `sql_query` | TEXT | SQL-запрос для получения данных |
| `is_pinned` | BOOLEAN | Флаг закрепления |
| `created_by` | VARCHAR(255) (nullable) | Автор |
| `created_at` | TIMESTAMP | Дата создания |
| `updated_at` | TIMESTAMP | Дата последнего обновления |

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
│   └── charts/
│       ├── ChartRenderer.tsx  # Универсальный рендер чарта (bar/line/pie/area/scatter через Recharts)
│       └── ChartCard.tsx      # Карточка сохранённого чарта с действиями
├── pages/
│   ├── DashboardPage.tsx      # Обзор синхронизации
│   ├── ChartsPage.tsx         # AI-генерация чартов + список сохранённых
│   ├── SchemaPage.tsx         # AI-описание схемы + редактирование + копирование + сырая структура таблиц с описаниями
│   ├── ConfigPage.tsx         # Настройки синхронизации
│   ├── MonitoringPage.tsx     # Мониторинг
│   └── ValidationPage.tsx     # Валидация данных
├── hooks/
│   ├── useSync.ts             # React Query хуки для синхронизации и справочников
│   ├── useCharts.ts           # React Query хуки для чартов, схемы и истории генерации
│   └── useAuth.ts             # Хук авторизации
├── services/
│   └── api.ts                 # Axios клиент, типы, API-объекты (syncApi, referencesApi, chartsApi, schemaApi)
└── store/
    ├── authStore.ts           # Zustand store авторизации
    └── syncStore.ts           # Zustand store синхронизации
```

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

Генерация чартов использует последнее сохранённое AI-описание схемы БД (`schema_descriptions`) в качестве контекста для AI. Если описание схемы ещё не было сгенерировано, endpoint вернёт ошибку 400 с просьбой сначала вызвать `GET /api/v1/schema/describe`.

**Создать чарт:**
```json
POST /api/v1/charts/generate
{
  "prompt": "Количество сделок по стадиям воронки"
}
```
AI получит markdown из последней генерации описания схемы как контекст для построения SQL-запроса.
