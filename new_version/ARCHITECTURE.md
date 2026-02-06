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
│   └── field_mapper.py      # Маппинг полей Bitrix → DB (кросс-БД совместимый)
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

### 3. Infrastructure Layer (`app/infrastructure/`)

```
app/infrastructure/
├── bitrix/
│   └── client.py            # BitrixClient с retry и rate limiting
├── database/
│   ├── connection.py        # AsyncEngine, get_session, get_dialect()
│   ├── models.py            # SQLAlchemy модели (SyncConfig, SyncLog, SyncState)
│   └── dynamic_table.py     # Динамическое создание таблиц (кросс-БД)
└── scheduler/
    └── scheduler.py         # APScheduler для периодической синхронизации

alembic/
├── env.py                   # Alembic environment (async)
└── versions/
    └── 001_create_system_tables.py  # Initial migration (кросс-БД)
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
├── exceptions.py            # Кастомные исключения
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
