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
│   ├── __init__.py          # Роутер версии API (sync, webhooks, status, charts, schema)
│   ├── endpoints/
│   │   ├── sync.py          # Эндпоинты синхронизации
│   │   ├── webhooks.py      # Обработка webhooks от Bitrix24
│   │   ├── status.py        # Статус и health checks
│   │   ├── charts.py        # AI-генерация и CRUD чартов
│   │   └── schema_description.py  # AI-описание схемы БД
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
| `GET` | `/api/v1/schema/describe` | AI-описание схемы БД (markdown) |
| `GET` | `/api/v1/schema/tables` | Список таблиц с колонками |
| `GET` | `/health` | Health check |

### 2. Domain Layer (`app/domain/`)

```
app/domain/
├── entities/
│   ├── base.py              # BitrixEntity, EntityType
│   ├── deal.py              # Модель сделки
│   ├── contact.py           # Модель контакта
│   ├── lead.py              # Модель лида
│   └── company.py           # Модель компании
├── services/
│   ├── sync_service.py      # Основная логика синхронизации
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
    @staticmethod def validate_sql_query(sql: str) -> None
    @staticmethod def validate_table_names(sql: str, allowed: list[str]) -> None
    @staticmethod def ensure_limit(sql: str, max_rows: int) -> str
    async def get_schema_context(table_filter?) -> str
    async def get_tables_info() -> list[dict]
    async def execute_chart_query(sql: str) -> tuple[list[dict], float]
    async def save_chart(data: dict) -> dict
    async def get_charts(page, per_page) -> tuple[list[dict], int]
    async def delete_chart(chart_id: int) -> bool
    async def toggle_pin(chart_id: int) -> dict
```

### 3. Infrastructure Layer (`app/infrastructure/`)

```
app/infrastructure/
├── bitrix/
│   └── client.py            # BitrixClient с retry и rate limiting
├── database/
│   ├── connection.py        # AsyncEngine, get_session, get_dialect()
│   ├── models.py            # SQLAlchemy модели (SyncConfig, SyncLog, SyncState, AIChart)
│   └── dynamic_table.py     # Динамическое создание таблиц (кросс-БД)
└── scheduler/
    └── scheduler.py         # APScheduler для периодической синхронизации

alembic/
├── env.py                   # Alembic environment (async)
└── versions/
    ├── 001_create_system_tables.py  # Initial migration (кросс-БД)
    └── 002_create_ai_charts_table.py  # Таблица ai_charts для сохранённых чартов
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
│   ├── SyncCard.tsx           # Карточка синхронизации
│   └── charts/
│       ├── ChartRenderer.tsx  # Универсальный рендер чарта (bar/line/pie/area/scatter через Recharts)
│       └── ChartCard.tsx      # Карточка сохранённого чарта с действиями
├── pages/
│   ├── DashboardPage.tsx      # Обзор синхронизации
│   ├── ChartsPage.tsx         # AI-генерация чартов + список сохранённых
│   ├── SchemaPage.tsx         # AI-описание схемы + сырая структура таблиц
│   ├── ConfigPage.tsx         # Настройки синхронизации
│   ├── MonitoringPage.tsx     # Мониторинг
│   └── ValidationPage.tsx     # Валидация данных
├── hooks/
│   ├── useSync.ts             # React Query хуки для синхронизации
│   ├── useCharts.ts           # React Query хуки для чартов и схемы
│   └── useAuth.ts             # Хук авторизации
├── services/
│   └── api.ts                 # Axios клиент, типы, API-объекты (syncApi, chartsApi, schemaApi)
└── store/
    ├── authStore.ts           # Zustand store авторизации
    └── syncStore.ts           # Zustand store синхронизации
```
