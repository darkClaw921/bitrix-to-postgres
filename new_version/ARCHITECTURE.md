# Архитектура Bitrix24 Sync Service

## Обзор системы

Bitrix24 Sync Service — это микросервис для односторонней синхронизации данных CRM из Bitrix24 в PostgreSQL. Система построена на принципах Clean Architecture и обеспечивает надежную, масштабируемую синхронизацию с поддержкой real-time обновлений через webhooks.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              ВНЕШНИЕ СИСТЕМЫ                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐          ┌─────────────┐          ┌─────────────┐          │
│  │  Bitrix24   │          │   Supabase  │          │   Frontend  │          │
│  │  REST API   │          │    Auth     │          │   (React)   │          │
│  └──────┬──────┘          └──────┬──────┘          └──────┬──────┘          │
│         │                        │                        │                  │
│         │ webhooks               │ JWT                    │ HTTP             │
│         ▼                        ▼                        ▼                  │
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
│  │   Bitrix24 API  │   │   PostgreSQL    │                                  │
│  │  (External)     │   │   (Supabase)    │                                  │
│  └─────────────────┘   └─────────────────┘                                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Слои приложения

### 1. API Layer (`app/api/`)

Отвечает за HTTP интерфейс приложения.

```
app/api/
├── v1/
│   ├── __init__.py          # Роутер версии API
│   ├── endpoints/
│   │   ├── sync.py          # Эндпоинты синхронизации
│   │   ├── webhooks.py      # Обработка webhooks от Bitrix24
│   │   └── status.py        # Статус и health checks
│   └── schemas/
│       ├── sync.py          # Pydantic схемы для sync
│       ├── webhooks.py      # Схемы webhooks
│       └── common.py        # Общие схемы
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
| `GET` | `/health` | Health check |

### 2. Domain Layer (`app/domain/`)

Содержит бизнес-логику, независимую от внешних систем.

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
│   └── field_mapper.py      # Маппинг полей Bitrix → PostgreSQL
└── interfaces/              # Абстракции (для DI)
```

#### SyncService — основные методы:

```python
class SyncService:
    async def full_sync(entity_type: str) -> dict
    """Полная синхронизация: получить все записи, создать/обновить таблицу, UPSERT"""

    async def incremental_sync(entity_type: str) -> dict
    """Инкрементальная: синхронизировать только изменённые записи (DATE_MODIFY)"""

    async def sync_entity_by_id(entity_type: str, entity_id: str) -> dict
    """Синхронизация одной записи (для webhooks)"""

    async def delete_entity_by_id(entity_type: str, entity_id: str) -> dict
    """Удаление записи (для delete webhooks)"""
```

### 3. Infrastructure Layer (`app/infrastructure/`)

Интеграция с внешними системами.

```
app/infrastructure/
├── bitrix/
│   └── client.py            # BitrixClient с retry и rate limiting
├── database/
│   ├── connection.py        # AsyncEngine, get_session
│   ├── models.py            # SQLAlchemy модели (SyncConfig, SyncLog, SyncState)
│   └── dynamic_table.py     # Динамическое создание таблиц
└── scheduler/
    └── scheduler.py         # APScheduler для периодической синхронизации
```

#### BitrixClient

```python
class BitrixClient:
    """Async клиент для Bitrix24 REST API с:
    - Автоматическим retry (tenacity) при rate limit
    - Экспоненциальным backoff
    - Обработкой ошибок аутентификации
    """

    @retry(retry=retry_if_exception_type(BitrixRateLimitError), ...)
    async def _call(method: str, items: dict) -> dict

    async def get_entities(entity_type: str, filter_params: dict) -> list
    async def get_entity(entity_type: str, entity_id: str) -> dict
    async def get_entity_fields(entity_type: str) -> dict
    async def get_userfields(entity_type: str) -> list
```

#### DynamicTableBuilder

```python
class DynamicTableBuilder:
    """Динамическое управление схемой БД на основе полей Bitrix24"""

    @staticmethod
    async def create_table_from_fields(table_name: str, fields: list[FieldInfo])

    @staticmethod
    async def ensure_columns_exist(table_name: str, fields: list[FieldInfo]) -> list

    @staticmethod
    async def table_exists(table_name: str) -> bool
```

### 4. Core Layer (`app/core/`)

Общие утилиты и конфигурация.

```
app/core/
├── auth.py                  # JWT валидация (Supabase)
├── exceptions.py            # Кастомные исключения
├── logging.py               # Structlog конфигурация
└── webhooks.py              # Парсинг Bitrix24 webhooks
```

#### Исключения

```python
class AppException(Exception): ...
class BitrixAPIError(AppException): ...
class BitrixRateLimitError(BitrixAPIError): ...  # Триггерит retry
class BitrixAuthError(BitrixAPIError): ...       # Не триггерит retry
class SyncError(AppException): ...
class DatabaseError(AppException): ...
```

## Потоки данных

### 1. Full Sync Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FULL SYNC FLOW                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. API Request                                                          │
│     POST /api/v1/sync/start/deal {"sync_type": "full"}                  │
│                          │                                               │
│                          ▼                                               │
│  2. Background Task      ┌──────────────────┐                           │
│     запускается          │   SyncService    │                           │
│                          │   .full_sync()   │                           │
│                          └────────┬─────────┘                           │
│                                   │                                      │
│  3. Fetch Fields         ┌───────▼────────┐                             │
│                          │ BitrixClient   │                             │
│                          │ .get_fields()  │──────▶ Bitrix24 API         │
│                          │ .get_userfields│                             │
│                          └───────┬────────┘                             │
│                                  │                                       │
│  4. Map Fields           ┌───────▼────────┐                             │
│                          │  FieldMapper   │                             │
│                          │ .prepare_...() │                             │
│                          └───────┬────────┘                             │
│                                  │                                       │
│  5. Create/Update Table  ┌───────▼────────┐                             │
│                          │ DynamicTable   │                             │
│                          │   Builder      │──────▶ PostgreSQL           │
│                          └───────┬────────┘        CREATE/ALTER TABLE   │
│                                  │                                       │
│  6. Fetch Records        ┌───────▼────────┐                             │
│                          │ BitrixClient   │                             │
│                          │ .get_entities()│──────▶ Bitrix24 API         │
│                          └───────┬────────┘        (batch requests)     │
│                                  │                                       │
│  7. UPSERT Records       ┌───────▼────────┐                             │
│                          │  _upsert_      │                             │
│                          │   records()    │──────▶ PostgreSQL           │
│                          └───────┬────────┘        ON CONFLICT UPDATE   │
│                                  │                                       │
│  8. Update State         ┌───────▼────────┐                             │
│                          │ sync_state     │                             │
│                          │ sync_logs      │──────▶ PostgreSQL           │
│                          └────────────────┘                             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2. Incremental Sync Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       INCREMENTAL SYNC FLOW                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. Get Last Sync Date   ┌──────────────────┐                           │
│                          │   sync_state     │◀────── PostgreSQL         │
│                          │ last_modified    │                           │
│                          └────────┬─────────┘                           │
│                                   │                                      │
│  2. Fetch Modified       ┌───────▼────────┐                             │
│     Records              │ BitrixClient   │                             │
│                          │ .get_entities( │                             │
│                          │   filter={     │──────▶ Bitrix24 API         │
│                          │     ">DATE_MODIFY": last_date               │
│                          │   })           │                             │
│                          └───────┬────────┘                             │
│                                  │                                       │
│  3. UPSERT Changed       ┌───────▼────────┐                             │
│     Records Only         │  _upsert_      │──────▶ PostgreSQL           │
│                          │   records()    │                             │
│                          └────────────────┘                             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3. Webhook Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          WEBHOOK FLOW                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. Bitrix24 Event       event=ONCRMDEALUPDATE&data[FIELDS][ID]=123     │
│                                   │                                      │
│                                   ▼                                      │
│  2. Parse Webhook        ┌──────────────────┐                           │
│                          │ parse_nested_    │                           │
│                          │   query()        │                           │
│                          │ extract_event_   │                           │
│                          │   info()         │                           │
│                          └────────┬─────────┘                           │
│                                   │                                      │
│  3. Return 200 OK        ─────────┼─────────▶ Bitrix24                  │
│     (async processing)            │          (немедленный ответ)        │
│                                   │                                      │
│  4. Background Task      ┌───────▼────────┐                             │
│                          │ process_webhook│                             │
│                          │   _event()     │                             │
│                          └───────┬────────┘                             │
│                                  │                                       │
│              ┌───────────────────┼───────────────────┐                  │
│              │ ADD/UPDATE        │                   │ DELETE           │
│              ▼                   │                   ▼                  │
│  ┌───────────────────┐          │        ┌───────────────────┐         │
│  │ sync_entity_by_id │          │        │delete_entity_by_id│         │
│  │ → fetch from      │          │        │ → DELETE FROM     │         │
│  │   Bitrix24        │          │        │   table           │         │
│  │ → UPSERT to DB    │          │        └───────────────────┘         │
│  └───────────────────┘          │                                       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Схема базы данных

### Системные таблицы

```sql
-- Конфигурация синхронизации для каждого типа сущности
CREATE TABLE sync_config (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) UNIQUE NOT NULL,  -- deal, contact, lead, company
    enabled BOOLEAN DEFAULT true,
    sync_interval_minutes INTEGER DEFAULT 30,
    webhook_enabled BOOLEAN DEFAULT true,
    last_sync_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Состояние синхронизации
CREATE TABLE sync_state (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) UNIQUE NOT NULL,
    last_modified_date TIMESTAMP,            -- Для инкрементальной синхронизации
    total_records INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Логи синхронизации
CREATE TABLE sync_logs (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    sync_type VARCHAR(20) NOT NULL,          -- full, incremental, webhook
    status VARCHAR(20) NOT NULL,             -- running, completed, failed
    records_processed INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
```

### Динамические таблицы CRM

Таблицы создаются автоматически на основе полей Bitrix24:

```sql
-- Пример: crm_deals (создаётся динамически)
CREATE TABLE crm_deals (
    id SERIAL PRIMARY KEY,
    bitrix_id VARCHAR(50) UNIQUE NOT NULL,   -- ID из Bitrix24

    -- Стандартные поля (из crm.deal.fields)
    title TEXT,
    stage_id VARCHAR(50),
    opportunity NUMERIC,
    currency_id VARCHAR(10),
    contact_id VARCHAR(50),
    company_id VARCHAR(50),
    assigned_by_id VARCHAR(50),
    created_by_id VARCHAR(50),
    date_create TIMESTAMP,
    date_modify TIMESTAMP,

    -- Пользовательские поля (UF_*)
    uf_crm_custom_field TEXT,
    uf_crm_number_field NUMERIC,

    -- Служебные поля
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_crm_deals_bitrix_id ON crm_deals(bitrix_id);
CREATE INDEX idx_crm_deals_date_modify ON crm_deals(date_modify);
```

## Маппинг типов Bitrix24 → PostgreSQL

| Bitrix24 Type | PostgreSQL Type |
|---------------|-----------------|
| `string` | `TEXT` |
| `integer` | `INTEGER` |
| `double` | `NUMERIC` |
| `boolean` | `BOOLEAN` |
| `datetime` | `TIMESTAMP` |
| `date` | `DATE` |
| `enumeration` | `TEXT` |
| `crm_status` | `TEXT` |
| `crm_currency` | `VARCHAR(10)` |
| `user` | `VARCHAR(50)` |
| `crm_contact` | `VARCHAR(50)` |
| `crm_company` | `VARCHAR(50)` |
| `file` | `JSONB` |
| `*` (default) | `TEXT` |

## Конфигурация

### Переменные окружения

```python
class Settings(BaseSettings):
    # Application
    app_name: str = "Bitrix Sync Service"
    debug: bool = False
    environment: Literal["development", "staging", "production"]

    # Database
    database_url: PostgresDsn               # postgresql+asyncpg://...
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Supabase Auth
    supabase_url: str
    supabase_key: str
    supabase_jwt_secret: str

    # Bitrix24
    bitrix_webhook_url: str                 # https://xxx.bitrix24.ru/rest/1/xxx/

    # Sync
    sync_batch_size: int = 50
    sync_default_interval_minutes: int = 30

    # Server
    host: str = "0.0.0.0"
    port: int = 8080
```

## Обработка ошибок

### Retry Strategy (Bitrix24 API)

```python
@retry(
    retry=retry_if_exception_type(BitrixRateLimitError),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    reraise=True,
)
async def _call(self, method: str, items: dict) -> dict:
    ...
```

### Error Flow

```
BitrixRateLimitError  ──▶ Retry (до 5 раз с exponential backoff)
                              │
                              ▼ (исчерпаны попытки)
                         SyncError ──▶ sync_logs.status = 'failed'
                              │
                              ▼
                         Логирование (structlog)

BitrixAuthError ──▶ Немедленная ошибка (без retry)
                         │
                         ▼
                    SyncError ──▶ sync_logs

BitrixAPIError ──▶ SyncError ──▶ sync_logs
```

## Scheduler (APScheduler)

```python
# Инициализация при старте приложения
@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    await schedule_sync_jobs()  # Загрузка из sync_config
    yield
    stop_scheduler()

# Динамическое обновление расписания
async def reschedule_entity(entity_type: str, interval_minutes: int):
    """Вызывается при изменении sync_config"""
    scheduler.reschedule_job(
        f"sync_{entity_type}",
        trigger=IntervalTrigger(minutes=interval_minutes)
    )
```

## Безопасность

### JWT Authentication (Supabase)

```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials,
) -> dict:
    payload = jwt.decode(
        credentials.credentials,
        settings.supabase_jwt_secret,
        algorithms=["HS256"],
        audience="authenticated",
    )
    return {
        "id": payload["sub"],
        "email": payload.get("email"),
        "role": payload.get("role"),
    }
```

### Webhook Verification

Bitrix24 webhooks проверяются по:
1. Формату данных (URL-encoded nested query)
2. Наличию обязательных полей (event, data[FIELDS][ID])
3. Соответствию поддерживаемым событиям

## Масштабирование

### Горизонтальное масштабирование

```
┌─────────────────────────────────────────────────────────────────┐
│                    Load Balancer (nginx)                         │
└─────────────────────────────┬───────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   Backend 1   │    │   Backend 2   │    │   Backend 3   │
│  (API only)   │    │  (API only)   │    │  (API only)   │
└───────────────┘    └───────────────┘    └───────────────┘
                              │
                              ▼
                    ┌───────────────┐
                    │   Backend     │
                    │  (Scheduler)  │    ◀── Только один экземпляр
                    │   APScheduler │        запускает scheduler
                    └───────────────┘
                              │
                              ▼
                    ┌───────────────┐
                    │  PostgreSQL   │
                    │  (Primary)    │
                    └───────────────┘
```

### Рекомендации

1. **Scheduler**: Запускать только на одном экземпляре (использовать лидер-выборы или отдельный worker)
2. **Webhooks**: Можно обрабатывать на любом экземпляре (stateless)
3. **Background tasks**: Рассмотреть Celery/Redis для distributed task queue при высокой нагрузке
4. **Database**: Использовать connection pooling (PgBouncer)

## Мониторинг

### Health Check

```json
GET /health

{
  "status": "healthy",
  "version": "1.0.0",
  "scheduler": {
    "running": true,
    "jobs_count": 4
  }
}
```

### Логирование (structlog)

```python
logger.info(
    "Sync completed",
    entity_type="deal",
    records_processed=150,
    duration_seconds=12.5,
)
```

### Метрики для мониторинга

| Метрика | Источник |
|---------|----------|
| Количество синхронизированных записей | `sync_logs.records_processed` |
| Время синхронизации | `sync_logs.completed_at - started_at` |
| Ошибки синхронизации | `sync_logs WHERE status='failed'` |
| Активные синхронизации | `/api/v1/sync/running` |
| Rate limit errors | Логи (structlog) |

## Зависимости

### Основные

| Пакет | Версия | Назначение |
|-------|--------|------------|
| fastapi | ≥0.115.0 | Web framework |
| uvicorn | ≥0.32.0 | ASGI server |
| sqlalchemy | ≥2.0.0 | ORM + async |
| asyncpg | ≥0.30.0 | PostgreSQL async driver |
| fast-bitrix24 | ≥1.8.0 | Bitrix24 API client |
| pydantic-settings | ≥2.0.0 | Settings management |
| python-jose | ≥3.3.0 | JWT handling |
| apscheduler | ≥3.10.0 | Task scheduling |
| tenacity | ≥8.2.0 | Retry logic |
| structlog | ≥24.0.0 | Structured logging |
| httpx | ≥0.27.0 | Async HTTP client |

### Dev

| Пакет | Версия | Назначение |
|-------|--------|------------|
| pytest | ≥8.0.0 | Testing |
| pytest-asyncio | ≥0.23.0 | Async test support |
| pytest-cov | ≥4.0.0 | Coverage |
| ruff | ≥0.4.0 | Linter + formatter |
| mypy | ≥1.10.0 | Type checking |
