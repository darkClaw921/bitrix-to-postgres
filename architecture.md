# Архитектура проекта

## Общее описание
Проект — коннектор для синхронизации данных из Bitrix24 CRM в PostgreSQL/MySQL с AI-аналитикой (генерация чартов, описание схемы) и публикацией дашбордов.

---

## Старая версия (корень проекта)

### Основные файлы:
- **workClickHouse.py** — модуль для работы с ClickHouse (устаревшая версия)
  - Создание таблиц, добавление/удаление столбцов
  - Вставка, обновление, удаление записей
  - Конвертация типов данных

---

## Новая версия (`new_version/`)

### Backend (`new_version/backend/`)

Архитектура: Clean Architecture (API → Domain → Infrastructure)

#### Конфигурация и ядро
- **app/config.py** — Pydantic Settings: DB URL, Bitrix webhook, OpenAI, charts, dashboards (secret_key, token_expiry)
- **app/core/logging.py** — structlog с JSON/pretty форматированием
- **app/core/exceptions.py** — иерархия исключений:
  - `AppException` (base), `BitrixAPIError`, `BitrixRateLimitError`, `BitrixAuthError`
  - `DatabaseError`, `SyncError`, `AuthenticationError`, `AuthorizationError`
  - `AIServiceError` (502), `ChartServiceError` (400)
  - `DashboardServiceError` (400), `DashboardAuthError` (401)

#### Bitrix24 API клиент
- **app/infrastructure/bitrix/client.py** — `BitrixClient`: обёртка над fast-bitrix24 с retry/rate limiting
  - CRM сущности: `crm.{entity}.list`, `crm.{entity}.get`, `crm.{entity}.fields`, `crm.{entity}.userfield.list`
  - Users: `user.get`, `user.fields` (+ `USER_FIELD_TYPES` mapping для типов полей), `user.userfield.list`
  - Tasks: `tasks.task.list`, `tasks.task.get`, `tasks.task.getFields` (UF-поля внутри getFields)

#### База данных
- **app/infrastructure/database/connection.py** — SQLAlchemy async engine (asyncpg/aiomysql), session factory
- **app/infrastructure/database/models.py** — ORM модели:
  - `SyncConfig` — конфигурация синхронизации по entity_type
  - `SyncLog` — история синхронизаций
  - `SyncState` — состояние инкрементальной синхронизации
  - `AIChart` — сохранённые AI-чарты
  - `PublishedDashboard` — опубликованные дашборды (slug, password_hash, is_active)
  - `DashboardChart` — чарты в дашборде (layout позиции, title/description override)

#### Миграции (`alembic/versions/`)
- **001_create_system_tables.py** — sync_config, sync_logs, sync_state + default config
- **002_create_ai_charts_table.py** — ai_charts
- **003_create_schema_descriptions_table.py** — schema_descriptions
- **004_create_dashboards_tables.py** — published_dashboards, dashboard_charts (FK cascade)

#### Доменные сервисы (`app/domain/services/`)
- **chart_service.py** — `ChartService`:
  - SQL валидация (`validate_sql_query`, `validate_table_names`, `ensure_limit`)
  - Контекст схемы (`get_schema_context`, `get_allowed_tables`, `get_tables_info`)
  - Выполнение запросов (`execute_chart_query`) с таймаутом
  - CRUD чартов (`save_chart`, `get_charts`, `get_chart_by_id`, `delete_chart`, `toggle_pin`, `update_chart_config`)
  - CRUD описаний схемы (`save_schema_description`, `get_latest_schema_description`, etc.)
- **ai_service.py** — `AIService`:
  - `generate_chart_spec(prompt, schema_context)` → JSON спецификация чарта
  - `generate_schema_description(schema_context)` → Markdown документация
- **sync_service.py** — `SyncService`: полная/инкрементальная синхронизация сущностей (CRM, users, tasks)
  - Инкрементальная синхронизация: `DATE_MODIFY` (CRM), `TIMESTAMP_X` (users), `CHANGED_DATE` (tasks)
- **reference_sync_service.py** — `ReferenceSyncService`: синхронизация справочников
- **dashboard_service.py** — `DashboardService`:
  - `create_dashboard(title, chart_ids)` → slug + bcrypt password
  - `get_dashboards(page, per_page)`, `get_dashboard_by_id/slug` → с join charts
  - `verify_password(slug, password)` → bcrypt verify
  - `generate_token(slug)` / `verify_token(token)` → JWT (HS256, python-jose)
  - `update_dashboard`, `update_layout`, `update_chart_override`
  - `remove_chart`, `change_password`, `delete_dashboard`

#### Доменные сущности (`app/domain/entities/`)
- **base.py** — `BitrixEntity` базовый класс, `EntityType` enum (deal, contact, lead, company, user, task)
  - CRM сущности (deal, contact, lead, company): API namespace `crm.*`, таблицы `crm_{entity}s`
  - User: API namespace `user.*`, таблица `bitrix_users`
  - Task: API namespace `tasks.task.*`, таблица `bitrix_tasks`
  - `is_crm()` — проверка принадлежности к CRM namespace
- **deal.py** — Pydantic модель сделки (TITLE, STAGE_ID, OPPORTUNITY, etc.)
- **contact.py** — Pydantic модель контакта (NAME, PHONE, EMAIL, etc.)
- **lead.py** — Pydantic модель лида (TITLE, STATUS_ID, OPPORTUNITY, etc.)
- **company.py** — Pydantic модель компании (TITLE, INDUSTRY, REVENUE, etc.)
- **user.py** — Pydantic модель пользователя (NAME, EMAIL, WORK_POSITION, PERSONAL_*, WORK_*, etc.)
- **task.py** — Pydantic модель задачи (TITLE, DESCRIPTION, STATUS, PRIORITY, DEADLINE, RESPONSIBLE_ID, etc.)
- **reference.py** — `ReferenceType` (crm_status, crm_deal_category, crm_currency)

#### API (`app/api/v1/`)
- **__init__.py** — регистрация роутеров (sync, webhooks, status, charts, schema, references, dashboards, public)

##### Схемы (`app/api/v1/schemas/`)
- **common.py** — `HealthResponse`, `ErrorResponse`, `SuccessResponse`, `PaginationParams`
- **charts.py** — `ChartGenerateRequest`, `ChartConfigUpdateRequest`, `ChartSpec`, `ChartGenerateResponse`, `ChartResponse`, `ChartListResponse`, `ChartDataResponse`
- **dashboards.py** — `DashboardPublishRequest`, `DashboardUpdateRequest`, `LayoutItem`, `DashboardLayoutUpdateRequest`, `ChartOverrideUpdateRequest`, `DashboardAuthRequest`, `IframeCodeRequest`, `DashboardChartResponse`, `DashboardResponse`, `DashboardListResponse`, `DashboardPublishResponse`, `DashboardAuthResponse`, `PasswordChangeResponse`, `IframeCodeResponse`
- **schema_description.py** — `ColumnInfo`, `TableInfo`, `SchemaTablesResponse`, `SchemaDescriptionResponse`
- **sync.py** — `SyncConfigItem`, `SyncStartRequest/Response`, `SyncStatusItem/Response`, `SyncHistoryResponse`
- **webhooks.py** — `WebhookEventData`, `WebhookResponse`, `WebhookRegistration`

##### Эндпоинты (`app/api/v1/endpoints/`)
- **charts.py** — POST `/generate`, POST `/save`, GET `/list`, GET `/{id}/data`, PATCH `/{id}/config`, DELETE `/{id}`, POST `/{id}/pin`
- **dashboards.py** (internal):
  - POST `/publish`, GET `/list`, GET `/{id}`, PUT `/{id}`, DELETE `/{id}`
  - PUT `/{id}/layout`, PUT `/{id}/charts/{dc_id}`, DELETE `/{id}/charts/{dc_id}`
  - POST `/{id}/change-password`, POST `/iframe-code`
- **public.py** (no app auth):
  - GET `/chart/{id}/meta`, GET `/chart/{id}/data`
  - POST `/dashboard/{slug}/auth`, GET `/dashboard/{slug}`, GET `/dashboard/{slug}/chart/{dc_id}/data`
- **schema_description.py** — GET `/describe`, GET `/tables`, GET `/history`, PATCH `/{id}`, GET `/list`
- **sync.py** — GET `/config`, PUT `/config`, POST `/start/{entity}`, GET `/status`, GET `/running`
- **webhooks.py** — POST `/register`, DELETE `/unregister`, GET `/registered`
- **references.py** — GET `/types`, GET `/status`, POST `/sync/{ref_name}`, POST `/sync-all`
- **status.py** — GET `/health`, GET `/stats`, GET `/history`, GET `/scheduler`

#### Зависимости (`pyproject.toml`)
- FastAPI, SQLAlchemy[asyncio], asyncpg, aiomysql
- fast-bitrix24, python-jose[cryptography], passlib[bcrypt]
- openai, structlog, alembic, httpx, tenacity, apscheduler

---

### Frontend (`new_version/frontend/`)

React 18 + TypeScript + Vite + Tailwind CSS

#### Сервисы и хуки
- **src/services/api.ts** — axios HTTP клиент, все типы и API объекты:
  - `syncApi`, `statusApi`, `webhooksApi`, `referencesApi`, `chartsApi` (с `updateConfig` для PATCH), `schemaApi`
  - `dashboardsApi` — publish, list, get, update, delete, updateLayout, updateChartOverride, removeChart, changePassword, getIframeCode
  - `publicApi` — getChartMeta, getChartData, authenticateDashboard, getDashboard, getDashboardChartData
- **src/hooks/useSync.ts** — хуки синхронизации и справочников
- **src/hooks/useCharts.ts** — хуки чартов (`useUpdateChartConfig` для PATCH config) и описаний схемы
- **src/hooks/useDashboards.ts** — `usePublishDashboard`, `useDashboardList`, `useDashboard`, `useUpdateDashboard`, `useDeleteDashboard`, `useUpdateDashboardLayout`, `useUpdateChartOverride`, `useRemoveChartFromDashboard`, `useChangeDashboardPassword`, `useIframeCode`
- **src/hooks/useAuth.ts** — хук авторизации

#### Страницы (`src/pages/`)
- **DashboardPage.tsx** — обзор статистики и сущностей
- **ConfigPage.tsx** — управление конфигурацией синхронизации
- **MonitoringPage.tsx** — мониторинг и логи синхронизации
- **ValidationPage.tsx** — валидация данных
- **ChartsPage.tsx** — AI генерация чартов, сохранённые чарты, кнопка "Publish Dashboard", список опубликованных дашбордов
- **SchemaPage.tsx** — браузер схемы БД с AI описанием
- **LoginPage.tsx** — авторизация
- **EmbedChartPage.tsx** — standalone embed одного чарта (без навигации, публичный)
- **EmbedDashboardPage.tsx** — публичный дашборд с password gate, JWT в sessionStorage, grid чартов
- **DashboardEditorPage.tsx** — редактор дашборда: drag & drop + resize чартов (react-grid-layout v2), inline редактирование title/description, удаление чартов, смена пароля, копирование ссылки

#### Компоненты (`src/components/`)
- **Layout.tsx** — навигация, health индикатор, outlet
- **SyncCard.tsx** — карточка синхронизации сущности
- **ReferenceCard.tsx** — карточка справочника
- **charts/ChartRenderer.tsx** — рендер чартов (bar, line, pie, area, scatter) через recharts с поддержкой настроек отображения (legend, grid, axes, line/area/pie параметры)
- **charts/ChartSettingsPanel.tsx** — панель настроек чарта (visual, data format, line/area/pie settings) с PATCH сохранением в chart_config
- **charts/ChartCard.tsx** — карточка сохранённого чарта (pin, refresh, settings, SQL, embed, delete)
- **charts/IframeCopyButton.tsx** — кнопка "Embed" для копирования iframe HTML
- **dashboards/PublishModal.tsx** — модалка публикации дашборда (выбор чартов, title, description → пароль + URL)
- **dashboards/DashboardCard.tsx** — карточка дашборда в списке (open, edit, link, delete)
- **dashboards/PasswordGate.tsx** — форма ввода пароля для публичного дашборда

#### State Management
- **src/store/authStore.ts** — Zustand store авторизации
- **src/store/syncStore.ts** — Zustand store текущих синхронизаций

#### Маршрутизация (`src/App.tsx`)
- `/embed/chart/:chartId` → EmbedChartPage (вне Layout)
- `/embed/dashboard/:slug` → EmbedDashboardPage (вне Layout)
- `/` → DashboardPage, `/config`, `/monitoring`, `/validation`, `/charts`, `/schema` (внутри Layout)
- `/dashboards/:id/edit` → DashboardEditorPage (внутри Layout)

#### Зависимости (`package.json`)
- @tanstack/react-query, axios, react, react-dom, react-router-dom
- recharts, react-markdown, zustand, react-grid-layout
