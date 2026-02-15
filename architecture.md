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
- **app/config.py** — Pydantic Settings: DB URL, Bitrix webhook, OpenAI, charts, dashboards (secret_key, token_expiry), auth (auth_login, auth_password, auth_token_expiry_minutes)
- **app/core/auth.py** — JWT аутентификация:
  - `create_access_token(email)` — генерация JWT с `type: "access"`, секрет `dashboard_secret_key`
  - `get_current_user()` — валидация Bearer JWT, проверка `type == "access"` (изоляция от dashboard-токенов)
  - `CurrentUser` — типизированная зависимость для protected routes
- **app/core/logging.py** — structlog с JSON/pretty форматированием
- **app/core/exceptions.py** — иерархия исключений:
  - `AppException` (base), `BitrixAPIError`, `BitrixRateLimitError`, `BitrixAuthError`, `BitrixOperationTimeLimitError`
  - `DatabaseError`, `SyncError`, `AuthenticationError`, `AuthorizationError`
  - `AIServiceError` (502), `ChartServiceError` (400)
  - `DashboardServiceError` (400), `DashboardAuthError` (401)
  - `ReportServiceError` (400), `PublishedReportAuthError` (401)

#### Bitrix24 API клиент
- **app/infrastructure/bitrix/client.py** — `BitrixClient`: обёртка над fast-bitrix24 с retry/rate limiting
  - CRM сущности: `crm.{entity}.list`, `crm.{entity}.get`, `crm.{entity}.fields`, `crm.{entity}.userfield.list`
  - Users: `user.get`, `user.fields` (+ `USER_FIELD_TYPES` mapping для типов полей), `user.userfield.list`
  - Tasks: `tasks.task.list`, `tasks.task.get`, `tasks.task.getFields` (UF-поля внутри getFields)
  - Вспомогательные функции: `_camel_to_upper_snake()` — конвертация camelCase → UPPER_SNAKE_CASE для нормализации ключей задач; `_normalize_task_records()` — пакетная нормализация ключей списка задач

#### База данных
- **app/infrastructure/database/connection.py** — SQLAlchemy async engine (asyncpg/aiomysql), session factory
- **app/infrastructure/database/models.py** — ORM модели:
  - `SyncConfig` — конфигурация синхронизации по entity_type
  - `SyncLog` — история синхронизаций
  - `SyncState` — состояние инкрементальной синхронизации
  - `AIChart` — сохранённые AI-чарты
  - `ReportPromptTemplate` — системные промпты для AI отчётов
  - `AIReport` — определение AI-отчёта (title, user_prompt, status, schedule_type, schedule_config, sql_queries, report_template, is_pinned)
  - `AIReportRun` — результат выполнения отчёта (status, trigger_type, result_markdown, result_data, sql_queries_executed, execution_time_ms, llm_prompt)
  - `AIReportConversation` — история диалога генерации отчёта (session_id, role, content, metadata)
  - `PublishedDashboard` — опубликованные дашборды (slug, password_hash, is_active, refresh_interval_minutes)
  - `DashboardChart` — чарты в дашборде (layout позиции, title/description override)
  - `DashboardLink` — связи между дашбордами для табов (dashboard_id → linked_dashboard_id, sort_order, label)
  - `PublishedReport` — опубликованные отчёты (slug, title, description, report_id FK → ai_reports, password_hash, is_active)
  - `PublishedReportLink` — связи между опубликованными отчётами для табов (published_report_id → linked_published_report_id, sort_order, label)

#### Миграции (`alembic/versions/`)
- **001_create_system_tables.py** — sync_config, sync_logs, sync_state + default config
- **002_create_ai_charts_table.py** — ai_charts
- **003_create_schema_descriptions_table.py** — schema_descriptions
- **004_create_dashboards_tables.py** — published_dashboards, dashboard_charts (FK cascade)
- **005_add_refresh_interval.py** — добавление refresh_interval_minutes в published_dashboards
- **006_create_dashboard_links_table.py** — dashboard_links (FK → published_dashboards CASCADE, unique constraint)
- **007_create_dashboard_selectors_tables.py** — dashboard_selectors (FK → published_dashboards CASCADE, config JSON, sort_order, is_required), selector_chart_mappings (FK → dashboard_selectors CASCADE, FK → dashboard_charts CASCADE, target_column, target_table, operator_override)
- **007_create_chart_prompt_templates.py** — chart_prompt_templates
- **008_add_sql_history.py** — sql_query_history
- **009_create_chart_prompts_table.py** — chart_prompt_templates (промпт-шаблоны для чартов)
- **010_add_records_fetched_to_sync_logs.py** — добавление records_fetched в sync_logs
- **011_create_reports_tables.py** — report_prompt_templates, ai_reports, ai_report_runs, ai_report_conversations (PG/MySQL dual dialect, default report_context промпт)
- **012_create_published_reports_tables.py** — published_reports (slug, report_id FK, password_hash), published_report_links (PG/MySQL dual dialect)
- **013_add_llm_prompt_to_report_runs.py** — добавление колонки llm_prompt (Text, nullable) в ai_report_runs для хранения полного промпта отправленного в LLM

#### Очередь синхронизаций (`app/infrastructure/queue/`)
- **sync_queue.py** — `SyncQueue`: центральная очередь с двумя каналами:
  - Heavy Queue (`asyncio.PriorityQueue`) — full/incremental/reference синхронизации, один worker (строго последовательно)
  - Webhook Queue (`asyncio.Queue`) — webhook-обработка, worker с `Semaphore(3)` (до 3 параллельно)
  - `SyncPriority(IntEnum)` — WEBHOOK=0, MANUAL=10, REFERENCE=20, SCHEDULED=30
  - `SyncTaskType(Enum)` — FULL, INCREMENTAL, WEBHOOK, WEBHOOK_DELETE, REFERENCE, REFERENCE_ALL
  - `SyncTask(dataclass)` — задача с приоритетом, дедупликацией по `dedup_key`
  - `get_sync_queue()` — singleton
  - Дедупликация: задача с тем же `dedup_key` не ставится в очередь повторно
  - `_execute_task()` — диспетчер: создаёт BitrixClient и вызывает SyncService/ReferenceSyncService

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
  - `generate_report_step(conversation_history, schema_context)` → шаг диалога генерации отчёта (вопрос или готовая спецификация)
  - `analyze_report_data(report_title, sql_results, analysis_prompt, user_prompt, report_context)` → tuple[str, str] (markdown-отчёт, полный промпт отправленный в LLM)
  - `_get_report_context()` → системный промпт из report_prompt_templates
- **report_service.py** — `ReportService`:
  - Диалог: `save_conversation_message()`, `get_conversation_history()`, `generate_session_id()`
  - CRUD: `save_report()`, `get_reports()`, `get_report_by_id()`, `delete_report()`, `update_report()`, `update_schedule()`, `toggle_pin()`
  - Выполнение: `execute_report(report_id, trigger_type)` — SQL запросы + LLM анализ → ai_report_runs
  - Запуски: `get_runs()`, `get_run_by_id()`
  - Промпт: `get_report_prompt_template()`, `update_report_prompt_template()`
  - Расписание: `get_active_scheduled_reports()`
  - Переиспользует ChartService для SQL валидации и выполнения
  - Публикация: `publish_report()`, `get_published_reports()`, `get_published_report_by_id()`, `delete_published_report()`, `change_published_report_password()`
  - Публичный доступ: `verify_published_report_password()`, `get_published_report_by_slug()` (с runs + links), `get_published_report_runs()`
  - Токены: `generate_report_token(slug)` / `verify_report_token(token)` → JWT с `type: "report"`
  - Связи: `add_published_report_link()`, `remove_published_report_link()`, `get_published_report_links()`, `update_published_report_link_order()`, `verify_published_report_linked_access()`
  - Переиспользует `DashboardService._hash_password`, `_generate_slug`, `_generate_password`, `_verify_password`
- **sync_service.py** — `SyncService`: полная/инкрементальная синхронизация сущностей (CRM, users, tasks)
  - Инкрементальная синхронизация: `DATE_MODIFY` (CRM), `TIMESTAMP_X` (users), `CHANGED_DATE` (tasks)
- **reference_sync_service.py** — `ReferenceSyncService`: синхронизация справочников
- **dashboard_service.py** — `DashboardService`:
  - `create_dashboard(title, chart_ids, refresh_interval_minutes)` → slug + bcrypt password
  - `get_dashboards(page, per_page)`, `get_dashboard_by_id/slug` → с join charts
  - `get_dashboard_id_by_slug(slug)` — лёгкий запрос только ID (без charts/selectors)
  - `get_chart_sql_by_slug(slug, dc_id)` — лёгкий запрос SQL одного чарта (1 JOIN, без загрузки всего дашборда)
  - `verify_password(slug, password)` → bcrypt verify
  - `generate_token(slug)` / `verify_token(token)` → JWT (HS256, python-jose)
  - `update_dashboard`, `update_layout`, `update_chart_override`
  - `remove_chart`, `change_password`, `delete_dashboard`
  - `add_link(dashboard_id, linked_dashboard_id, label?, sort_order?)` — связывание дашбордов для табов
  - `remove_link(link_id)`, `get_links(dashboard_id)`, `update_link_order(dashboard_id, links)`
  - `verify_linked_access(main_slug, linked_slug)` — проверка связи + активности обоих дашбордов
  - `_get_selectors(dashboard_id)` — загрузка селекторов через SelectorService (lazy import)
- **selector_service.py** — `SelectorService`:
  - CRUD: `create_selector()`, `get_selector_by_id()`, `get_selectors_for_dashboard()`, `update_selector()`, `delete_selector()`
  - `get_selectors_for_dashboard()` — один JOIN-запрос (selectors + mappings), без N+1
  - Маппинги: `add_mapping()`, `remove_mapping()`, `_replace_mappings()` — полная перезапись маппингов
  - Фильтрация: `build_filters_for_chart(dashboard_id, dc_id, filter_values, selectors?)` → список фильтров для `ChartService.apply_filters()`, принимает предзагруженные селекторы
  - Опции: `get_selector_options(selector_id)`, `get_all_selector_options(dashboard_id)` (batch), `_resolve_options(selector)` — SELECT DISTINCT с опциональным LEFT JOIN для label-таблицы, или static_values из config
  - Колонки: `get_chart_columns(dc_id)` → column names через LIMIT 0 subquery
  - Preview: `preview_filter(dc_id, target_column, operator, target_table?, sample_value?)` → original_sql, filtered_sql, where_clause для визуализации на доске

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
- **__init__.py** — регистрация роутеров с разделением на public и protected:
  - Публичные (без auth): auth, webhooks, public
  - Защищённые (JWT `Depends(get_current_user)`): sync, status, charts, schema, references, dashboards, selectors, reports

##### Схемы (`app/api/v1/schemas/`)
- **common.py** — `HealthResponse`, `ErrorResponse`, `SuccessResponse`, `PaginationParams`
- **charts.py** — `ChartGenerateRequest`, `ChartConfigUpdateRequest`, `ChartSpec`, `ChartGenerateResponse`, `ChartResponse`, `ChartListResponse`, `ChartDataResponse`
- **dashboards.py** — `DashboardPublishRequest`, `DashboardUpdateRequest`, `LayoutItem`, `DashboardLayoutUpdateRequest`, `ChartOverrideUpdateRequest`, `DashboardAuthRequest`, `IframeCodeRequest`, `DashboardLinkRequest`, `DashboardLinkOrderItem`, `DashboardLinkUpdateRequest`, `DashboardChartResponse`, `DashboardLinkResponse`, `DashboardResponse` (с `linked_dashboards`, `selectors`), `DashboardListResponse`, `DashboardPublishResponse`, `DashboardAuthResponse`, `PasswordChangeResponse`, `IframeCodeResponse`
- **selectors.py** — `SelectorCreateRequest`, `SelectorUpdateRequest`, `MappingCreateRequest`, `FilterValue`, `FilterRequest`, `SelectorResponse`, `MappingResponse`, `SelectorListResponse`, `SelectorOptionItem`, `SelectorOptionsResponse`, `ChartColumnsResponse`, `ChartTablesResponse`, `FilterPreviewRequest`, `FilterPreviewResponse`
- **schema_description.py** — `ColumnInfo`, `TableInfo`, `SchemaTablesResponse`, `SchemaDescriptionResponse`
- **sync.py** — `SyncConfigItem`, `BitrixFilter`, `SyncStartRequest/Response` (с optional filter), `SyncStatusItem/Response`, `SyncHistoryResponse`
- **webhooks.py** — `WebhookEventData`, `WebhookResponse`, `WebhookRegistration`
- **reports.py** — `ReportConversationRequest/Response`, `ReportPreview`, `ReportSaveRequest`, `ReportScheduleUpdateRequest`, `ReportUpdateRequest`, `ReportResponse`, `ReportListResponse`, `ReportRunResponse`, `ReportRunListResponse`, `ReportPromptTemplateResponse/UpdateRequest`, `SqlQueryItem`, `DataResultItem`, `PublishReportRequest/Response`, `PublishedReportAuthRequest/Response`, `PublishedReportResponse`, `PublishedReportListItem/Response`, `PublishedReportLinkRequest/Response/OrderItem/UpdateRequest`, `PublicReportRunResponse`, `PublicReportResponse`

##### Эндпоинты (`app/api/v1/endpoints/`)
- **auth.py** — POST `/login` — single-user аутентификация (email + password из .env), возвращает JWT access token
- **charts.py** — POST `/generate`, POST `/save`, GET `/list`, GET `/{id}/data`, PATCH `/{id}/config`, DELETE `/{id}`, POST `/{id}/pin`
- **dashboards.py** (internal):
  - POST `/publish`, GET `/list`, GET `/{id}`, PUT `/{id}`, DELETE `/{id}`
  - PUT `/{id}/layout`, PUT `/{id}/charts/{dc_id}`, DELETE `/{id}/charts/{dc_id}`
  - POST `/{id}/change-password`, POST `/iframe-code`
  - POST `/{id}/links`, DELETE `/{id}/links/{link_id}`, PUT `/{id}/links` — управление связями дашбордов
- **public.py** (no app auth):
  - GET `/chart/{id}/meta`, GET `/chart/{id}/data`
  - POST `/dashboard/{slug}/auth`, GET `/dashboard/{slug}`, GET `/dashboard/{slug}/chart/{dc_id}/data`
  - GET `/dashboard/{slug}/linked/{linked_slug}` — получение связанного дашборда (JWT главного)
  - GET `/dashboard/{slug}/linked/{linked_slug}/chart/{dc_id}/data` — данные чарта связанного дашборда
  - POST `/report/{slug}/auth` — авторизация паролем → JWT с `type: "report"`
  - GET `/report/{slug}` — данные опубликованного отчёта (runs + linked_reports, JWT)
  - GET `/report/{slug}/linked/{linked_slug}` — данные связанного отчёта (JWT главного)
  - POST `/dashboard/{slug}/chart/{dc_id}/data` — данные чарта с фильтрами (FilterRequest body, JWT)
  - POST `/dashboard/{slug}/linked/{linked_slug}/chart/{dc_id}/data` — данные чарта linked дашборда с фильтрами
  - GET `/dashboard/{slug}/selectors` — список селекторов публичного дашборда (JWT)
  - GET `/dashboard/{slug}/selector/{selector_id}/options` — опции для dropdown/multi-select (JWT)
  - GET `/dashboard/{slug}/selector-options` — batch-опции всех селекторов дашборда за один запрос (JWT)
- **selectors.py** (internal, prefix `/dashboards`):
  - POST `/{dashboard_id}/selectors` — создание селектора с маппингами
  - GET `/{dashboard_id}/selectors` — список селекторов дашборда
  - PUT `/{dashboard_id}/selectors/{selector_id}` — обновление (включая полную перезапись маппингов)
  - DELETE `/{dashboard_id}/selectors/{selector_id}` — удаление
  - GET `/{dashboard_id}/selectors/{selector_id}/options` — опции dropdown
  - GET `/{dashboard_id}/charts/{dc_id}/columns` — колонки SQL-запроса чарта
  - GET `/{dashboard_id}/charts/{dc_id}/tables` — таблицы из SQL-запроса чарта (FROM/JOIN)
  - POST `/{dashboard_id}/charts/{dc_id}/preview-filter` — превью SQL с фильтром (FilterPreviewRequest → FilterPreviewResponse)
- **schema_description.py** — GET `/describe`, GET `/tables`, GET `/history`, PATCH `/{id}`, GET `/list`
- **sync.py** — GET `/config`, PUT `/config`, POST `/start/{entity}`, GET `/status`, GET `/running`
- **webhooks.py** — POST `/register`, DELETE `/unregister`, GET `/registered`
- **references.py** — GET `/types`, GET `/status`, POST `/sync/{ref_name}`, POST `/sync-all`
- **reports.py** — POST `/converse`, POST `/save`, GET `/list`, GET `/{id}`, DELETE `/{id}`, PATCH `/{id}` (update report fields), PATCH `/{id}/schedule`, POST `/{id}/run`, POST `/{id}/pin`, GET `/{id}/runs`, GET `/{id}/runs/{run_id}`, GET `/prompt-template/report-context`, PUT `/prompt-template/report-context`, POST `/publish`, GET `/published`, GET `/published/{id}`, POST `/published/{id}/change-password`, DELETE `/published/{id}`, POST `/published/{id}/links`, DELETE `/published/{id}/links/{link_id}`, PUT `/published/{id}/links`
- **status.py** — GET `/health`, GET `/stats`, GET `/history`, GET `/scheduler`

#### Планировщик (`app/infrastructure/scheduler/`)
- **scheduler.py** — APScheduler:
  - Синхронизация: `IntervalTrigger` задачи для инкрементальных синков
  - Отчёты: `report_execution_job(report_id)` — запуск отчёта по расписанию
  - `build_report_trigger(schedule_type, schedule_config)` — создание CronTrigger
  - `schedule_report_jobs()` — загрузка активных отчётов из БД и создание задач
  - `reschedule_report(report_id, ...)` / `remove_report_job(report_id)` — управление задачами

#### Зависимости (`pyproject.toml`)
- FastAPI, SQLAlchemy[asyncio], asyncpg, aiomysql
- fast-bitrix24, python-jose[cryptography], passlib[bcrypt]
- openai, structlog, alembic, httpx, tenacity, apscheduler

---

### Frontend (`new_version/frontend/`)

React 18 + TypeScript + Vite + Tailwind CSS

#### Сервисы и хуки
- **src/services/api.ts** — axios HTTP клиент (с 401 interceptor → redirect на /login), все типы и API объекты:
  - `syncApi`, `statusApi`, `webhooksApi`, `referencesApi`, `chartsApi` (с `updateConfig` для PATCH), `schemaApi`
  - `dashboardsApi` — publish, list, get, update, delete, updateLayout, updateChartOverride, removeChart, changePassword, getIframeCode, addLink, removeLink, updateLinks, listSelectors, createSelector, updateSelector, deleteSelector, getSelectorOptions, getChartColumns, getChartTables, previewFilter
  - `reportsApi` — converse, save, list, get, delete, update, updateSchedule, run, togglePin, getRuns, getRun, getPromptTemplate, updatePromptTemplate
  - `publishedReportsApi` — publish, list, get, delete, changePassword, addLink, removeLink, updateLinks
  - `publicApi` — getChartMeta, getChartData, authenticateDashboard, getDashboard, getDashboardChartData, getLinkedDashboard, getLinkedDashboardChartData, getDashboardChartDataFiltered, getLinkedDashboardChartDataFiltered, getPublicSelectors, getPublicSelectorOptions, authenticateReport, getPublicReport, getLinkedReport
- **src/hooks/useSync.ts** — хуки синхронизации и справочников
- **src/hooks/useCharts.ts** — хуки чартов (`useUpdateChartConfig` для PATCH config) и описаний схемы
- **src/hooks/useDashboards.ts** — `usePublishDashboard`, `useDashboardList`, `useDashboard`, `useUpdateDashboard`, `useDeleteDashboard`, `useUpdateDashboardLayout`, `useUpdateChartOverride`, `useRemoveChartFromDashboard`, `useChangeDashboardPassword`, `useIframeCode`, `useAddDashboardLink`, `useRemoveDashboardLink`, `useUpdateDashboardLinks`
- **src/hooks/useReports.ts** — хуки отчётов: `useReportConverse`, `useReportSave`, `useReports`, `useDeleteReport`, `useUpdateReport`, `useUpdateReportSchedule`, `useRunReport`, `useToggleReportPin`, `useReportRuns`, `useReportPromptTemplate`, `useUpdateReportPromptTemplate`, `usePublishReport`, `usePublishedReport`, `usePublishedReports`, `useDeletePublishedReport`, `useChangePublishedReportPassword`, `useAddPublishedReportLink`, `useRemovePublishedReportLink`
- **src/hooks/useSelectors.ts** — `useDashboardSelectors`, `useCreateSelector`, `useUpdateSelector`, `useDeleteSelector`, `useSelectorOptions`, `useChartColumns`, `useFilterPreview`
- **src/hooks/useAuth.ts** — хук авторизации

#### Страницы (`src/pages/`)
- **DashboardPage.tsx** — обзор статистики и сущностей
- **ConfigPage.tsx** — управление конфигурацией синхронизации
- **MonitoringPage.tsx** — мониторинг и логи синхронизации
- **ValidationPage.tsx** — валидация данных
- **ChartsPage.tsx** — AI генерация чартов, сохранённые чарты, кнопка "Publish Dashboard", список опубликованных дашбордов (подтаб AISubTabs)
- **ReportsPage.tsx** — AI отчёты: чат-интерфейс генерации, сохранение отчёта (title/description), список сохранённых отчётов с карточками, секция опубликованных отчётов с кнопкой "Опубликовать" и списком PublishedReportCard, редактор промпта
- **SchemaPage.tsx** — браузер схемы БД с AI описанием
- **LoginPage.tsx** — авторизация
- **EmbedChartPage.tsx** — standalone embed одного чарта (без навигации, публичный)
- **EmbedDashboardPage.tsx** — публичный дашборд с password gate, JWT в sessionStorage, grid чартов, auto-refresh по интервалу (setInterval), индикатор обновления и "last updated", табы для связанных дашбордов (кеширование загруженных табов, auto-refresh для активного таба), SelectorBar с фильтрами (POST с FilterValue[] при активных фильтрах, сброс при переключении таба), footer с версией UI
- **EmbedReportPage.tsx** — публичная страница опубликованного отчёта: PasswordGate → JWT в sessionStorage, header (title + description), табы для связанных отчётов (кеш), список runs в виде аккордеона (ReactMarkdown + remarkGfm + markdownTableComponents для таблиц с рамками)
- **DashboardEditorPage.tsx** — редактор дашборда: drag & drop + resize чартов (react-grid-layout v2), inline редактирование title/description, удаление чартов, смена пароля, копирование ссылки, секция SelectorEditorSection (CRUD селекторов через wizard-модалку из 3 шагов), секция "Linked Dashboards" (добавление/удаление/перестановка связей)

#### Компоненты (`src/components/`)
- **Layout.tsx** — навигация, health индикатор, outlet, footer с версией UI
- **SyncCard.tsx** — карточка синхронизации сущности с обнаружением OPERATION_TIME_LIMIT и интеграцией FilterDialog
- **FilterDialog.tsx** — модальное окно фильтра для повторной синхронизации с ограничением по дате (поле, оператор, значение)
- **ReferenceCard.tsx** — карточка справочника
- **charts/ChartRenderer.tsx** — рендер чартов (bar, line, pie, area, scatter) через recharts с поддержкой настроек отображения (legend, grid, axes, line/area/pie параметры)
- **charts/ChartSettingsPanel.tsx** — панель настроек чарта (visual, data format, line/area/pie settings) с PATCH сохранением в chart_config
- **charts/ChartCard.tsx** — карточка сохранённого чарта (pin, refresh, settings, SQL, embed, delete)
- **charts/IframeCopyButton.tsx** — кнопка "Embed" для копирования iframe HTML
- **dashboards/PublishModal.tsx** — модалка публикации дашборда (выбор чартов, title, description, refresh interval → пароль + URL)
- **dashboards/DashboardCard.tsx** — карточка дашборда в списке (open, edit, link, delete)
- **dashboards/PasswordGate.tsx** — форма ввода пароля для публичного дашборда
- **ai/AISubTabs.tsx** — горизонтальные подтабы "Графики" | "Отчёты" (используется в ChartsPage и ReportsPage)
- **reports/ReportChat.tsx** — чат-интерфейс диалога с LLM: список сообщений, поле ввода, индикатор генерации, кнопка нового чата
- **reports/ReportCard.tsx** — карточка отчёта: статус, расписание, кнопки (запустить, результаты, SQL, Prompt, расписание, закрепить, удалить), просмотр/редактирование SQL-запросов и промпта
- **reports/ScheduleSelector.tsx** — редактор расписания: тип (once/daily/weekly/monthly), время, день недели/месяца, статус
- **reports/ReportRunViewer.tsx** — просмотр запусков отчёта: список с бейджами статуса, 4 таба (Markdown через react-markdown + remarkGfm + markdownTableComponents, SQL запросы, сырые данные, полный промпт)
- **reports/markdownComponents.tsx** — общие кастомные компоненты ReactMarkdown для таблиц с рамками (table, thead, th, td)
- **reports/ReportPromptEditorModal.tsx** — модалка редактирования системного промпта для отчётов
- **reports/PublishReportModal.tsx** — модалка публикации отчёта (выбор отчёта, title, description → URL + пароль)
- **reports/PublishedReportCard.tsx** — карточка опубликованного отчёта (title, report_title, кнопки open/link/связи/смена пароля/delete), управление связями (linked reports): список текущих связей с удалением, dropdown для добавления новых; смена пароля с отображением нового
- **selectors/SelectorBar.tsx** — горизонтальная полоса фильтров для публичного дашборда: загрузка опций, 5 типов виджетов, кнопки "Применить"/"Сбросить"
- **selectors/SelectorEditorSection.tsx** — секция управления селекторами в редакторе дашборда: список с сортировкой, кнопки edit/delete, открытие SelectorBoardDialog
- **selectors/SelectorModal.tsx** — (legacy) wizard из 3 шагов: основные настройки (тип, имя, оператор), источник данных (static/DB с JOIN), привязка к графикам (чекбоксы + выбор колонки)
- **selectors/SelectorBoardDialog.tsx** — интерактивная доска (React Flow) для настройки маппингов фильтра к графикам: drag-to-connect от селектора к колонкам чартов, edge popup для operator_override, SQL preview
- **selectors/SelectorConfigPanel.tsx** — левая панель 280px: настройки типа, имени, оператора, источника данных (static/database) — всё на одном экране
- **selectors/SqlPreviewPanel.tsx** — нижняя сворачиваемая панель: оригинальный и модифицированный SQL с подсветкой WHERE clause
- **selectors/nodes/SelectorNode.tsx** — кастомный React Flow node: голубая карточка селектора с label, type, operator, source handle справа
- **selectors/nodes/ChartNode.tsx** — кастомный React Flow node: белая карточка чарта с заголовком и списком колонок, каждая колонка — target handle слева
- **selectors/nodes/MappingEdge.tsx** — кастомный React Flow edge (Bezier) с label на середине: target_column + operator_override, кнопка удаления при выделении
- **selectors/DropdownSelector.tsx** — select с кнопкой очистки
- **selectors/MultiSelectSelector.tsx** — dropdown с чекбоксами, поиском, select all/deselect all
- **selectors/DateRangeSelector.tsx** — два input[date] + пресеты (сегодня, 7 дней, месяц, квартал)
- **selectors/SingleDateSelector.tsx** — input[date] с кнопкой очистки
- **selectors/TextSelector.tsx** — input[text] с debounce 300ms
#### Версионирование UI
- **src/version.ts** — константа `UI_VERSION`, обновляется при каждом изменении UI

#### State Management
- **src/store/authStore.ts** — Zustand store авторизации
- **src/store/syncStore.ts** — Zustand store текущих синхронизаций

#### Маршрутизация (`src/App.tsx`)
- `/login` → LoginPage (публичный)
- `/embed/chart/:chartId` → EmbedChartPage (вне Layout, публичный)
- `/embed/dashboard/:slug` → EmbedDashboardPage (вне Layout, публичный)
- `/embed/report/:slug` → EmbedReportPage (вне Layout, публичный)
- `/` → DashboardPage, `/config`, `/monitoring`, `/validation`, `/schema` (внутри Layout, ProtectedRoute)
- `/ai/charts` → ChartsPage, `/ai/reports` → ReportsPage, `/ai` → redirect на `/ai/charts`
- `/dashboards/:id/edit` → DashboardEditorPage (внутри Layout, ProtectedRoute)
- `ProtectedRoute` — auth guard: проверяет isAuthenticated, редиректит на /login

#### Локализация (`src/i18n/`)
- **types.ts** — типизированные ключи переводов: nav, common, dashboard, config, monitoring, validation, charts, schema, references, dashboards, ai, reports, embedReport, selectors, footer
- **locales/ru.ts** / **locales/en.ts** — русские и английские переводы

#### Зависимости (`package.json`)
- @tanstack/react-query, axios, react, react-dom, react-router-dom
- recharts, react-markdown, remark-gfm, zustand, react-grid-layout
