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
│   ├── __init__.py          # Роутер версии API (sync, webhooks, status, charts, schema, references, dashboards, selectors, reports, plans, departments, public)
│   ├── endpoints/
│   │   ├── sync.py          # Эндпоинты синхронизации
│   │   ├── webhooks.py      # Обработка webhooks от Bitrix24
│   │   ├── status.py        # Статус и health checks
│   │   ├── charts.py        # AI-генерация и CRUD чартов
│   │   ├── schema_description.py  # AI-описание и raw-описание схемы БД
│   │   ├── references.py    # Синхронизация справочных данных (статусы, воронки, валюты)
│   │   ├── dashboards.py    # CRUD дашбордов, layout, ссылки, пароли. Heading-эндпоинты: POST/PUT /headings (создание и обновление heading items). Chart-add эндпоинт: POST /charts (добавление существующего AI-чарта в дашборд)
│   │   ├── selectors.py     # CRUD селекторов (фильтров) дашбордов и маппингов
│   │   ├── plans.py         # CRUD планов (/api/v1/plans), batch-create, CRUD plan_templates, template expand+apply, plan-vs-actual, AI-generate (Phase 3) и meta-эндпоинты (/meta/tables, /meta/numeric-fields, /meta/managers). Тонкий HTTP-слой над PlanService + PlanTemplateService + PlansAIService. _raise_for_service_error: PlanNotFoundError→404, PlanConflictError→409, PlanValidationError→400. _raise_for_template_error: PlanTemplateNotFoundError→404, PlanTemplateConflictError/ValidationError→400 (builtin-блокировки через 400, не 409). POST /ai-generate: 503 если API-key пустой, 400 если не создано описание схемы (через ChartService.get_any_latest_schema_description), 502 на AIServiceError
│   │   ├── departments.py   # Эндпоинты отделов (/api/v1/departments): GET / (плоский список), GET /tree (иерархия), POST /sync (BackgroundTasks + 409 при активной sync), GET /{id}/managers?recursive=true (активные менеджеры отдела и, опционально, всех подотделов). Тонкий слой над DepartmentService/DepartmentSyncService
│   │   └── public.py        # Публичные эндпоинты: чарты, дашборды, аутентификация, фильтрованные данные. Chart data endpoints возвращают 400 если dc_id принадлежит heading
│   └── schemas/
│       ├── sync.py          # Pydantic схемы для sync
│       ├── webhooks.py      # Схемы webhooks
│       ├── common.py        # Общие схемы
│       ├── charts.py        # Схемы чартов (ChartSpec, ChartGenerateRequest/Response и др.). ChartSpec (ответ LLM) содержит опциональное chart_config: dict — через него от LLM до /save пробрасывается plan_fact и любые другие free-form ключи. ChartConfig (extra='allow') — типизированная обёртка над ai_charts.chart_config JSON с опциональным plan_fact. PlanFactConfig (extra='forbid') — конфиг post-enrichment план/факт: table_name, field_name, date_column (обязательные), group_by_column (опц.), plan_key (default 'plan')
│       ├── dashboards.py    # Схемы дашбордов (DashboardResponse включает selectors). Полиморфный DashboardChartResponse (item_type='chart'|'heading', chart_id Optional, heading_config Optional). Heading-схемы: HeadingConfig, HeadingCreateRequest, HeadingUpdateRequest. Chart-add: ChartAddRequest (chart_id + опциональный layout)
│       ├── selectors.py     # Схемы селекторов (SelectorCreateRequest, SelectorResponse, FilterValue и др.)
│       ├── plans.py         # Схемы планов: PlanCreateRequest (с model_validator для period-mode: fixed month|quarter|year+period_value vs custom+date_from/date_to), PlanUpdateRequest (plan_value/description), PlanResponse, PlanVsActualResponse (plan/actual/variance/variance_pct + period_effective_from/to), NumericFieldInfo/NumericFieldsResponse, TableInfo/TablesResponse, plan_row_to_response helper. Схемы plan_templates: PlanTemplateCreateRequest (field_validator'ы для period_mode/assignees_mode + model_validator для кросс-полей — period_type обязателен при custom_period, department_name при assignees_mode='department', specific_manager_ids при 'specific'), PlanTemplateUpdateRequest (все optional), PlanTemplateResponse, PlanTemplateExpandRequest (overrides table_name/field_name/period_value), PlanTemplateApplyRequest (template_id + entries: list[PlanDraft] + overrides). Драфты: PlanDraft (assigned_by_id/name + target + period + plan_value + warnings list). Batch: PlanBatchCreateRequest (plans: list[PlanCreateRequest], min_length=1). AI-генерация (для Phase 3): PlanAIGenerateRequest/Response. Мета: PlanManagerInfo/PlanManagersResponse. Константы ALL_PERIOD_MODES, ALL_ASSIGNEES_MODES
│       ├── departments.py   # Схемы отделов: DepartmentResponse (плоский DTO), DepartmentTreeNode (self-ref children), DepartmentTreeResponse, DepartmentSyncResponse, ManagerInfo, ManagersListResponse
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
| `POST` | `/api/v1/plans` | Создать план (PlanCreateRequest → PlanResponse, 201). Валидация: существование table_name.field_name в information_schema и numeric-тип; период — fixed (month/quarter/year + period_value) или custom (date_from + date_to); проверка логического дубликата (409) |
| `GET` | `/api/v1/plans` | Список планов с query-фильтрами table_name, field_name, assigned_by_id, period_type → list[PlanResponse] |
| `GET` | `/api/v1/plans/{plan_id}` | Получить план по id (404 если не найден) |
| `PUT` | `/api/v1/plans/{plan_id}` | Обновить plan_value/description (PlanUpdateRequest). Логический ключ read-only — для его смены удалить и создать заново |
| `DELETE` | `/api/v1/plans/{plan_id}` | Удалить план (204, 404 если не найден) |
| `GET` | `/api/v1/plans/{plan_id}/vs-actual` | Plan vs Actual снапшот: plan_value/actual_value/variance/variance_pct + period_effective_from/to. Факт считается как SUM(field) по периоду с учётом assigned_by_id |
| `GET` | `/api/v1/plans/meta/tables` | Список таблиц-целей (префиксы crm_/ref_/bitrix_/stage_history_, исключая саму plans) из information_schema |
| `GET` | `/api/v1/plans/meta/numeric-fields?table_name=...` | Список числовых колонок указанной таблицы (фильтр по NUMERIC_DATA_TYPES из PlanService) |
| `POST` | `/api/v1/plans/batch` | Транзакционный batch-create (`PlanBatchCreateRequest` → `list[PlanResponse]`, 201). Все `PlanCreateRequest` проходят валидацию numeric-column + period-mode + дубликатов (в батче и в БД). Любая ошибка → rollback всего батча; `created_by_id` берётся из JWT |
| `GET` | `/api/v1/plans/templates` | Список всех шаблонов (включая builtin) — `list[PlanTemplateResponse]` |
| `POST` | `/api/v1/plans/templates` | Создание user-defined шаблона (is_builtin всегда False; created_by_id из JWT). 400 на ошибки валидации |
| `GET` | `/api/v1/plans/templates/{id}` | Получить шаблон по id (404 если не найден) |
| `PUT` | `/api/v1/plans/templates/{id}` | Partial update шаблона. Для builtin блокируется изменение name/period_mode/assignees_mode (400) |
| `DELETE` | `/api/v1/plans/templates/{id}` | Удаление шаблона (204). 400 для builtin, 404 если не найден |
| `POST` | `/api/v1/plans/templates/{id}/expand` | Развернуть шаблон в `list[PlanDraft]` — превью для UI. Body `PlanTemplateExpandRequest` (optional table_name/field_name/period_value overrides; обязательны для builtin с NULL-target). Для assignees_mode='department' резолвит department_name → bitrix_id через bitrix_departments, затем DepartmentService.collect_descendant_ids + list_managers_in_departments |
| `POST` | `/api/v1/plans/templates/{id}/apply` | Применить шаблон с уже отредактированными `entries` — `PlanTemplateApplyRequest` маппится в `list[PlanCreateRequest]` и уходит в `PlanService.batch_create_plans` (всё или ничего). 400 если template_id в path и body не совпадают или если builtin без table_name/field_name override |
| `GET` | `/api/v1/plans/meta/managers?department_id=...&recursive=true` | Активные менеджеры. Без department_id — все `bitrix_users.active='Y'`. С department_id — делегирует в DepartmentService (recursive=true собирает подотделы) |
| `POST` | `/api/v1/plans/ai-generate` | **Phase 3**: превью AI-сгенерированных черновиков планов. Body `PlanAIGenerateRequest {description, table_name?, field_name?}` → `PlanAIGenerateResponse {plans: list[PlanDraft], warnings: list[str]}`. НЕ пишет в БД — пользователь после правок отправляет в `POST /plans/batch`. Коды ответов: 503 если `OPENAI_API_KEY` пустой, 400 если не создано описание схемы (нужно сначала `GET /api/v1/schema/describe`), 502 при невалидном JSON/ошибке LLM. Auth required (JWT). Реализация через `PlansAIService.generate_and_expand` (LLM + expand спец-значений assigned_by_id + валидация drafts через PlanService) |
| `GET` | `/api/v1/departments` | Плоский список всех отделов (`list[DepartmentResponse]`, сортировка по (sort, bitrix_id)) |
| `GET` | `/api/v1/departments/tree` | Иерархическое дерево отделов (`DepartmentTreeResponse`, корневые узлы с вложенными children) |
| `POST` | `/api/v1/departments/sync` | Запуск фоновой синхронизации отделов через BackgroundTasks (`DepartmentSyncService.full_sync`). Возвращает 409 если синхронизация уже идёт (проверка через `DepartmentSyncService.is_running()`) |
| `GET` | `/api/v1/departments/{id}/managers?recursive=true&active_only=true` | Менеджеры отдела (опц. включая подотделы). `recursive=true` (default) собирает все потомки через `collect_descendant_ids` и делает один JOIN `bitrix_user_departments + bitrix_users` |
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
│   ├── reference.py         # Реестр справочных типов (ReferenceType, ReferenceFieldDef)
│   ├── plan.py              # PlanEntity (Pydantic) — доменная обёртка над строкой таблицы plans; PeriodType = month|quarter|year|custom
│   ├── plan_template.py     # PlanTemplateEntity (Pydantic) — доменная обёртка над строкой plan_templates. Literal-типы PeriodMode (current_month|current_quarter|current_year|custom_period), AssigneesMode (all_managers|department|specific|global), TemplatePeriodType (month|quarter|year|custom). specific_manager_ids уже распарсен из JSON в list[str]|None. default_plan_value: Decimal|None, is_builtin: bool
│   └── department.py        # DepartmentEntity (dataclass) — доменная обёртка над строкой bitrix_departments: bitrix_id, name, parent_id, sort (default 500), uf_head
├── services/
│   ├── sync_service.py      # Основная логика синхронизации (+ авто-синхронизация справочников)
│   ├── reference_sync_service.py  # Синхронизация справочных таблиц (статусы, воронки, валюты)
│   ├── plan_service.py      # PlanService: CRUD планов (create/list/get/update/delete) с валидацией числовых колонок через information_schema и проверкой режима периода; _insert_plan_in_conn(conn, payload) — общий INSERT-хелпер для single и batch; batch_create_plans(plans, created_by_id) — транзакционный all-or-nothing batch с pre-validate (numeric column + period-mode + intra-batch & DB duplicate check) и единым engine.begin() для INSERT'ов; compute_actual() для SUM по периоду с whitelist идентификаторов; get_plan_vs_actual() с резолвом period_value -> [date_from, date_to); get_plans_llm_context() — markdown-блок для системного промпта AIService
│   ├── plan_template_service.py  # PlanTemplateService: CRUD plan_templates (list/get/create/update/delete) + expand_template(id, overrides) → list[PlanDraft]. Update блокирует изменение is_builtin; для builtin-шаблонов также защищены name/period_mode/assignees_mode. Delete блокирует is_builtin=True (PlanTemplateConflictError → 400). expand_template: (1) маппит period_mode → (period_type, period_value) — current_month='%Y-%m', current_quarter='YYYY-QN' (quarter=(m-1)//3+1), current_year='%Y', custom_period берёт template-поля; (2) по assignees_mode: all_managers → SELECT bitrix_users active='Y', department → резолв department_name → bitrix_id в bitrix_departments + DepartmentService.collect_descendant_ids + list_managers_in_departments, specific → JSON parse specific_manager_ids + _fetch_users_by_ids с warning'ами для inactive/missing, global → 1 draft с assigned_by_id=NULL; (3) применяет overrides table_name/field_name/period_value. JSON round-trip specific_manager_ids: json.dumps при write / json.loads при read с fallback '[]' на malformed. Ошибки: PlanTemplateNotFoundError, PlanTemplateConflictError, PlanTemplateValidationError
│   ├── field_mapper.py      # Маппинг полей Bitrix → DB (кросс-БД совместимый)
│   ├── ai_service.py        # Взаимодействие с LLM API (OpenAI/OpenRouter): чарты, схема, селекторы, отчёты, планы (Phase 3: PLANS_GENERATION_PROMPT + generate_plans_from_description — JSON {plans, warnings} с спец-значениями assigned_by_id=all_managers/department:Name/bitrix_id/null)
│   ├── plans_ai_service.py  # PlansAIService (Phase 3): агрегирует AIService+PlanService+DepartmentService для POST /plans/ai-generate. expand_ai_drafts(raw_plans) разворачивает all_managers (fetch active bitrix_users) / department:Name (case-insensitive search в bitrix_departments + collect_descendant_ids + list_managers_in_departments active_only) / конкретный bitrix_id (verify existence) / null (global); валидирует каждый draft через PlanService._validate_numeric_column + _validate_period (БЕЗ INSERT); невалидные отбрасываются с warning. generate_and_expand(description, schema_context, hints) — endpoint-level entry point
│   ├── chart_service.py     # SQL-валидация, выполнение запросов, CRUD чартов, apply_filters(), resolve_labels_in_data()
│   ├── dashboard_service.py # CRUD дашбордов, JWT-аутентификация, layout, ссылки (загружает selectors). Поддержка полиморфных элементов dashboard_charts (chart|heading): _get_dashboard_charts (LEFT JOIN ai_charts), add_heading, update_heading; update_layout/remove_chart работают по dashboard_charts.id для обоих типов; get_chart_sql_by_slug использует LEFT JOIN ai_charts и возвращает dc.item_type для отделения headings
│   ├── selector_service.py  # CRUD селекторов и маппингов, build_filters_for_chart() (с резолвом date-токенов и post_filter), get_selector_options() (поддержка JOIN с label-таблицей)
│   ├── date_tokens.py       # Резолв date-токенов (TODAY, LAST_30_DAYS, ...) и end-of-day для BETWEEN
│   ├── department_sync_service.py  # DepartmentSyncService: full_sync() — get_all('department.get') + UPSERT в bitrix_departments (dialect-aware: ON CONFLICT / ON DUPLICATE KEY). Класс-level _running_syncs dedup, запись в sync_logs c entity_type='ref:department'. Нормализация пустых PARENT/UF_HEAD → NULL
│   └── department_service.py       # DepartmentService (read-only): list_departments(), get_department(bitrix_id), build_tree() (in-memory BFS, cross-DB), collect_descendant_ids(root_bitrix_id) (iterative BFS с cycle guard), list_managers_in_departments(ids, active_only) (DISTINCT JOIN bitrix_user_departments + bitrix_users с expanding bindparam для IN)
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
    def __init__(self, plan_service: PlanService | None = None)  # Опциональная инъекция PlanService; при None создаётся дефолтный PlanService() — используется в _get_bitrix_context для обогащения LLM-контекста markdown-блоком планов
    async def _complete(system: str, input_, max_output_tokens: int) -> str
    @staticmethod def _to_chat_messages(system: str, input_) -> list[dict]  # Конвертация в chat.completions формат

    async def _get_bitrix_context() -> str  # Загружает активный Bitrix-промпт из chart_prompt_templates и конкатенирует его с PlanService.get_plans_llm_context() (markdown-блок таблицы plans) через "\n\n"; обе части best-effort — ошибка загрузки не блокирует LLM-вызов
    async def _get_report_context() -> str  # Загружает активный report-промпт из report_prompt_templates

    async def generate_chart_spec(prompt: str, schema_context: str) -> dict  # Автоматически подгружает Bitrix-контекст
    async def refine_chart_sql(current_sql: str, instruction: str, schema_context: str) -> str  # AI-рефайн SQL существующего чарта по текстовой инструкции; использует CHART_SQL_REFINE_PROMPT; возвращает только sql_query
    async def generate_schema_description(schema_context: str) -> str
    async def generate_selectors(charts_context: str, schema_context: str, user_request: str | None = None) -> list[dict]  # AI-генерация селекторов с поддержкой токенов, post_filter и опционального текстового пожелания пользователя. Endpoint generate_selectors дополнительно фильтрует charts по chart_ids перед формированием charts_context
    async def generate_report_step(conversation_history: list[dict], schema_context: str) -> dict
    async def analyze_report_data(report_title, sql_results, analysis_prompt, ...) -> tuple[str, str]
    async def generate_plans_from_description(description: str, schema_context: str, hints: dict | None = None) -> dict  # Phase 3. Формирует PLANS_GENERATION_PROMPT c подстановкой schema_context + PlanService.get_plans_llm_context() + current_date + hints ("таблица=X; поле=Y" или "не указаны"), вызывает _complete(max_output_tokens=3000), парсит JSON через _extract_json, возвращает {plans: raw list, warnings: list[str]}. Спец-значения assigned_by_id в сырых plans ("all_managers", "department:Name") разворачивает PlansAIService, а не сам AIService
```

**Phase 3 plans prompt**: [`PLANS_GENERATION_PROMPT`](backend/app/domain/services/ai_service.py) — системный промпт на русском для декомпозиции пользовательского запроса в JSON-черновики планов. Placeholder'ы: `{schema_context}`, `{current_date}`, `{hints}`. Правила: использовать только существующие числовые поля, period_value формат зависит от period_type (YYYY-MM / YYYY-QN / YYYY / null для custom), assigned_by_id ∈ {bitrix_id | "all_managers" | "department:Название" | null}, все неоднозначности → warnings, strict JSON без markdown.

**PlansAIService — AI-генерация планов (Phase 3)**:

```python
class PlansAIService:
    # Агрегатор AIService + PlanService + DepartmentService для POST /plans/ai-generate
    def __init__(ai_service=None, plan_service=None, department_service=None)

    async def expand_ai_drafts(raw_plans: list, warnings=None) -> tuple[list[PlanDraft], list[str]]
        # Для каждого сырого plan:
        #   - нормализует (coerce plan_value → Decimal, date_from/to → date, проверяет period_type в ALL_PERIOD_TYPES)
        #   - expand assigned_by_id: all_managers (bitrix_users active='Y') / department:Name (LOWER(name)=LOWER search + descendants + active managers) / конкретный bitrix_id (_fetch_user_by_id, warning если не найден) / null (single global draft)
        #   - валидирует через PlanService._validate_numeric_column + _validate_period (без INSERT)
        #   - невалидные пропускает с warning; валидные в результат
    async def generate_and_expand(description, schema_context, hints=None) -> PlanAIGenerateResponse  # End-to-end: LLM вызов + expand + validate
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

#### Модуль «План/Факт»

Модуль позволяет пользователю задавать плановые значения для любого числового поля любой бизнес-таблицы (`crm_*`, `ref_*`, `bitrix_*`, `stage_history_*`) и сравнивать их с фактическим `SUM(field)` за период. Планы хранятся в таблице `plans`. Чарты «план vs факт» работают через **post-enrichment**: LLM генерирует SQL только по факту (без `JOIN plans`) и помечает чарт флагом `chart_config.plan_fact` (`PlanFactConfig`: `table_name`/`field_name`/`date_column`/опц. `group_by_column`/`plan_key`); после выполнения SQL backend вызывает `PlanService.enrich_rows_with_plan`, который подтягивает подходящие строки из `plans` с учётом уже резолвнутых селекторов дашборда (фильтр менеджеров + диапазон дат) и добавляет в каждую строку результата колонку `plan` рядом с фактом. Старые чарты без флага `plan_fact` продолжают работать без enrichment.

**Таблица `plans`** (миграция [`022_create_plans_table.py`](backend/alembic/versions/022_create_plans_table.py)):

| Колонка | Тип | Назначение |
|---|---|---|
| `id` | PK | Идентификатор плана |
| `table_name` | VARCHAR | Целевая таблица (валидация через `information_schema`) |
| `field_name` | VARCHAR | Числовое поле таблицы (валидация по `NUMERIC_DATA_TYPES`) |
| `assigned_by_id` | BIGINT NULL | Менеджер (опционально); NULL = план на всю таблицу |
| `period_type` | VARCHAR | `month` \| `quarter` \| `year` \| `custom` |
| `period_value` | VARCHAR NULL | Для fixed: `YYYY-MM` (month) / `YYYY-Q1..Q4` (quarter) / `YYYY` (year) |
| `date_from` / `date_to` | DATE NULL | Для `period_type='custom'` — явный диапазон |
| `plan_value` | NUMERIC | Плановое значение |
| `description` | TEXT NULL | Комментарий |
| `uq_plan_key` | UNIQUE | `(table_name, field_name, assigned_by_id, period_type, period_value, date_from, date_to)` — защита от логических дублей |

Период задаётся одним из двух режимов: **fixed** (`period_type ∈ {month,quarter,year}` + `period_value`) или **custom** (`period_type='custom'` + `date_from`/`date_to`). Поле `assigned_by_id` опционально: если не задано, план считается по всей таблице без фильтра по менеджеру.

**Backend-файлы:**

- SQLAlchemy модель [`Plan`](backend/app/infrastructure/database/models.py) в `models.py`
- Доменная сущность [`PlanEntity`](backend/app/domain/entities/plan.py) (Pydantic, `PeriodType = month|quarter|year|custom`)
- Сервис [`PlanService`](backend/app/domain/services/plan_service.py) — основные методы:
  - `create_plan` / `list_plans` / `get_plan` / `update_plan` / `delete_plan` — CRUD с валидацией таблицы/поля через `information_schema` и проверкой режима периода; логический дубль → `PlanConflictError`
  - `_insert_plan_in_conn(conn, payload) → int` — общий INSERT-хелпер (cross-dialect: PG `RETURNING id` / MySQL `lastrowid`), переиспользуется в `create_plan` и `batch_create_plans`; не делает валидацию (она happens до вызова) — чистый INSERT поверх уже открытого соединения
  - `batch_create_plans(plans, created_by_id=None) → list[dict]` — транзакционный batch: (1) pre-validate ALL записей (numeric column + period-mode + intra-batch duplicate через `(table,field,assigned,period,...)`-ключ + existing-DB duplicate через `_find_duplicate`), (2) если всё ок — один `engine.begin()` и цикл `_insert_plan_in_conn` для каждой. Любая ошибка внутри `begin()` → rollback всего батча (atomic). `created_by_id` из JWT применяется ко всем записям единообразно
  - `compute_actual(table_name, field_name, assigned_by_id, date_from, date_to)` — безопасный `SUM(field)` по периоду с whitelist идентификаторов (защита от SQL-injection)
  - `get_plan_vs_actual(plan_id)` — резолв fixed `period_value` → `[date_from, date_to)` и вычисление `plan/actual/variance/variance_pct`
  - `_resolve_period_bounds(period_type, period_value, date_from, date_to) → (date, date)` — общий хелпер конвертации fixed/custom периода в полузакрытый `[start, end)`; переиспользуется `get_plan_vs_actual` и post-enrichment
  - **Post-enrichment (plan/fact без JOIN):**
    - `enrich_rows_with_plan(rows, plan_fact_cfg, resolved_filters) → list[dict]` — основной метод: принимает результат `execute_chart_query` и типизированный `PlanFactConfig` из `chart_config.plan_fact`, извлекает сигналы селекторов (`assigned_by_id`-фильтр + `between`-диапазон дат), загружает подходящие планы (параметризованный `text()` с `bindparam(..., expanding=True)` для `IN`), фильтрует по пересечению периодов, агрегирует по `group_by_column` или как скаляр и мержит значение в `row[plan_key]`. Общие планы (`assigned_by_id IS NULL`) включаются всегда и добавляются к каждой группе
    - `_extract_selector_signals(resolved_filters) → (list[str]|None, (date,date)|None)` — парсит список фильтров из `SelectorService.build_filters_for_chart` (поля `column`/`operator`/`value`); находит фильтр менеджеров по `column == 'assigned_by_id'` (скаляр или список) и диапазон дат по `operator == 'between'` (dict `{from,to}` или двухэлементный list)
    - `_period_intersects(plan_row, range_from, range_to) → bool` — проверка пересечения полузакрытого периода плана (через `_resolve_period_bounds`) с диапазоном селектора (`plan_from < range_to AND plan_to > range_from`); `True` при отсутствии диапазона; битые планы безопасно пропускаются с warning
    - `_norm_group_key(value) → str` / `_coerce_date(value) → date|None` — утилиты для единообразного сравнения ключей групп (int↔str) и парсинга дат из резолвнутых фильтров
  - `get_plans_llm_context()` — markdown-блок с описанием таблицы `plans` и правилами post-enrichment (LLM обязана возвращать `chart_config.plan_fact` вместо `JOIN plans`); включает markdown-таблицу активных планов для выбора пары `(table_name, field_name)`. Подмешивается в системный промпт LLM через `AIService._get_bitrix_context()`
- Схемы [`api/v1/schemas/plans.py`](backend/app/api/v1/schemas/plans.py): `PlanCreateRequest` (с `model_validator` для period-mode), `PlanUpdateRequest`, `PlanResponse`, `PlanVsActualResponse`, `PlanBatchCreateRequest` (plans: list[PlanCreateRequest], min 1), `NumericFieldInfo`/`NumericFieldsResponse`, `TableInfo`/`TablesResponse`, `plan_row_to_response` helper. Шаблоны: `PlanTemplateCreateRequest` / `PlanTemplateUpdateRequest` / `PlanTemplateResponse` / `PlanTemplateExpandRequest` / `PlanTemplateApplyRequest`, `PlanDraft`, AI-генерация Phase 3: `PlanAIGenerateRequest`/`PlanAIGenerateResponse`, meta: `PlanManagerInfo`/`PlanManagersResponse`. Константы `ALL_PERIOD_MODES`, `ALL_ASSIGNEES_MODES`
- Эндпоинты [`api/v1/endpoints/plans.py`](backend/app/api/v1/endpoints/plans.py) — 17 маршрутов: CRUD plans (`POST`/`GET`/`GET {id}`/`PUT {id}`/`DELETE {id}`), `GET /plans/{id}/vs-actual`, `GET /plans/meta/tables` / `numeric-fields` / `managers`, batch + templates (`POST /plans/batch`, `GET`/`POST /plans/templates`, `GET`/`PUT`/`DELETE /plans/templates/{id}`, `POST /plans/templates/{id}/expand`, `POST /plans/templates/{id}/apply`) — полный список в таблице эндпоинтов выше. Порядок роутов: специфичные пути (`/batch`, `/templates`, `/meta/*`) объявлены ДО `/{plan_id}`, чтобы литеральные пути не перехватывались int-конвертером
- Регистрация роутера: `router.include_router(plans.router, prefix="/plans", tags=["plans"], dependencies=_auth)` в [`api/v1/__init__.py`](backend/app/api/v1/__init__.py)

**Точки вызова post-enrichment (call sites):**

- [`api/v1/endpoints/public.py`](backend/app/api/v1/endpoints/public.py) — хелпер `_extract_plan_fact_cfg(chart_info)` парсит `chart_config.plan_fact` из строки чарта в типизированный `PlanFactConfig` (возвращает `None` при отсутствии ключа или невалидной схеме, логируя warning). В `_execute_filtered_chart` после `chart_service.execute_chart_query` вызов `plan_service.enrich_rows_with_plan(data, plan_fact_cfg, filters)` передаёт уже построенный `build_filters_for_chart`-список (с применённым `date_tokens.resolve_filter_value`) — это ключевой момент: enrichment получает уже резолвнутые значения селекторов и сам извлекает из них сигналы менеджеров и диапазона дат. Ошибки enrichment best-effort: логируются и возвращают исходные `rows` без `plan`
- [`api/v1/endpoints/charts.py`](backend/app/api/v1/endpoints/charts.py) — симметричный вызов в `get_chart_data` (не-embed путь: страница AI-чартов и предпросмотр в редакторе дашборда). Поскольку этот путь не проходит через селекторы, enrichment вызывается с пустым списком фильтров `[]` — `_extract_selector_signals` вернёт `(None, None)` и план посчитается как «весь диапазон/все менеджеры» (fallback). Оба call site идентичны по логике; TODO-комментарий упоминает возможную экстракцию в общий хелпер `ChartService._maybe_enrich_plan_fact`, когда появится третий call site

**Интеграция с AIService:** конструктор `AIService(plan_service: PlanService | None = None)` принимает `PlanService` (или создаёт дефолтный). В `_get_bitrix_context()` результат `PlanService.get_plans_llm_context()` конкатенируется с активным `bitrix_context` из `chart_prompt_templates` через `"\n\n"` — LLM получает описание таблицы `plans` и правила post-enrichment автоматически. В `CHART_SYSTEM_PROMPT` добавлено поле `chart_config` (опц.) с описанием `plan_fact` и явным правилом «для плана/факта возвращай `chart_config.plan_fact` без `JOIN plans`, `data_keys` включает `['actual','plan']`». `ChartSpec` ([`schemas/charts.py`](backend/app/api/v1/schemas/charts.py)) содержит опциональное поле `chart_config: dict[str, Any]`, чтобы `plan_fact` проходил от LLM через `generate_chart_spec` к сохранению чарта без потери ключа. `ChartConfig` (`extra='allow'`) и `PlanFactConfig` (`extra='forbid'`, поля `table_name`/`field_name`/`date_column` обязательные, `group_by_column` опц., `plan_key` default `'plan'`) дают типизированный доступ к `plan_fact` из call site. Backward compat: старые чарты без `chart_config.plan_fact` работают без enrichment — условие `if plan_fact_cfg is not None` полностью пропускает ветку post-enrichment, и чарт отдаёт ровно те `rows`, что вернул `execute_chart_query` (включая SQL со старым `LEFT JOIN plans`, если он был сгенерирован до перехода на post-enrichment).

**Flow сводка:** `LLM` → `ChartSpec{sql_query(actual only), chart_config.plan_fact}` → сохранение в `ai_charts` → при открытии чарта: `build_filters_for_chart` → `apply_filters` → `execute_chart_query` (rows по факту) → `_extract_plan_fact_cfg` → `PlanService.enrich_rows_with_plan(rows, cfg, filters)` → `_extract_selector_signals` из фильтров → `SELECT ... FROM plans WHERE table_name=:t AND field_name=:f AND (assigned_by_id IS NULL OR assigned_by_id IN :ids)` → `_period_intersects` для каждой строки → агрегация по `group_by_column` (или скаляр) → merge `row[plan_key] = plan_value` → ответ клиенту с колонками `actual` + `plan`.

**Frontend:**

- Страница [`PlansPage.tsx`](frontend/src/pages/PlansPage.tsx) — таблица планов с колонками таблица/поле/менеджер/период/план/факт/отклонение, батчевая загрузка `vs-actual` через `Promise.allSettled`, человекочитаемый период (`Апрель 2026`, `2026 — Q2`, custom-диапазон). В action-баре 3 кнопки: «+ Добавить план» (открывает `PlanFormModal`), «✨ Сгенерировать через AI» (открывает `AIGeneratePlansModal`) и «⭐ Избранные» (открывает `PlanTemplatesDrawer` → по клику «Применить» открывает `ApplyTemplateModal`). После любого create/apply — `loadPlans()` и toast. Предзагружает `users` (через `chartsApi.executeSql`) и `managers` (через `plansApi.listManagers`) для резолвинга имён в табличках
- Компонент [`components/plans/PlanFormModal.tsx`](frontend/src/components/plans/PlanFormModal.tsx) — модалка создания/редактирования плана. В create-режиме 4 таба назначения: «Один менеджер» (single select `users` → `plansApi.create`), «Несколько» (multi-select → `plansApi.batchCreate` с N копиями), «Отдел» (select из `departmentsApi.getTree()` + чекбокс «Включая подотделы» → live-preview менеджеров через `departmentsApi.getManagers` → `plansApi.batchCreate`), «Общий» (один план с `assigned_by_id=null`). В edit-режиме табы скрыты и сохраняется обратная совместимость (single update). Зависимые селекты `table_name → numeric_fields`, fixed/custom period-mode (`month`/`quarter`/`year` либо date-range)
- Компонент [`components/plans/PlanDraftsTable.tsx`](frontend/src/components/plans/PlanDraftsTable.tsx) — переиспользуемая таблица `PlanDraft[]` с inline-редактированием `plan_value`/`description`, крестиком удаления строки, жёлтой подсветкой строк с `warnings[]` (иконка `⚠` с tooltip) и красной подсветкой невалидных сумм. Поддерживает `readOnlyFields` и `managers` для резолвинга `assigned_by_id → имя`. Используется в `AIGeneratePlansModal` и `ApplyTemplateModal`
- Компонент [`components/plans/AIGeneratePlansModal.tsx`](frontend/src/components/plans/AIGeneratePlansModal.tsx) — модалка AI-генерации: textarea (мин. 5 симв., плейсхолдер с примером), collapsible hints (optional `table_name`/`field_name` select из `plansApi.getTables`/`getNumericFields`), кнопка «✨ Сгенерировать» → `plansApi.aiGenerate` (таймаут до 5 мин), показывает warnings + `PlanDraftsTable` с редактируемыми drafts, «Сохранить все (N)» → `plansApi.batchCreate` с фильтром невалидных. Обработка 502/503 → «AI-сервис временно недоступен»
- Компонент [`components/plans/PlanTemplatesDrawer.tsx`](frontend/src/components/plans/PlanTemplatesDrawer.tsx) — side drawer справа (width 520) со списком шаблонов из `plansApi.listTemplates`. Каждый шаблон: имя, description, бейдж «⭐ builtin» для `is_builtin`, мета-инфа (period_mode, assignees_mode, table.field). Действия: «Применить» (вызывает `onApply(templateId)` пропс), «Редактировать» (открывает `PlanTemplateFormModal`), «Удалить» (disabled+tooltip для builtin; `window.confirm` перед `plansApi.deleteTemplate`). Кнопка «+ Новый шаблон» открывает `PlanTemplateFormModal` в create-режиме
- Компонент [`components/plans/PlanTemplateFormModal.tsx`](frontend/src/components/plans/PlanTemplateFormModal.tsx) — форма создания/редактирования шаблона: name (required, заморожен для builtin), description, optional `table_name`/`field_name`, radio `period_mode` (+ конкретные поля при `custom_period`), radio `assignees_mode` (с select отдела из `departmentsApi.getTree()` для `department` и multi-select менеджеров из `plansApi.listManagers` для `specific`), `default_plan_value`. Для builtin скрывает/блокирует `name`/`period_mode`/`assignees_mode` (backend enforce 400)
- Компонент [`components/plans/ApplyTemplateModal.tsx`](frontend/src/components/plans/ApplyTemplateModal.tsx) — применение шаблона: грузит `plansApi.getTemplate(id)` по открытию; если `table_name`/`field_name` в шаблоне пусты — обязательные селекторы override (из `plansApi.getTables`/`getNumericFields`); опциональный period override (для builtin `current_*` режимов); default-bulk-value input с кнопкой «Заполнить всем» (массово проставляет `plan_value`); «Подготовить превью» → `plansApi.expandTemplate(id, overrides)` → `PlanDraftsTable` для редактирования; «Сохранить все» → `plansApi.applyTemplate(id, {table_name, field_name, period_value_override, entries})`. Ошибки expand (нет менеджеров, отдел не найден) отображаются в red alert
- API-клиент `plansApi` в [`services/api.ts`](frontend/src/services/api.ts): CRUD `/plans` + `/plans/{id}/vs-actual` + `/plans/meta/tables` + `/plans/meta/numeric-fields` + batch/AI/templates — `batchCreate` (`POST /plans/batch`), `aiGenerate` (`POST /plans/ai-generate`, таймаут `AI_REQUEST_TIMEOUT` = 5 мин как у `chartsApi.generate`), `listTemplates`/`getTemplate`/`createTemplate`/`updateTemplate`/`deleteTemplate` (CRUD шаблонов), `expandTemplate`/`applyTemplate` (`POST /plans/templates/{id}/expand`|`apply`), `listManagers` (`GET /plans/meta/managers?department_id&recursive`); TS-типы `Plan`, `PlanCreateRequest`, `PlanUpdateRequest`, `PlanVsActual`, `PlanPeriodType`, `NumericFieldInfo`, `PlanTableInfo`, `PlanTemplate`, `PlanTemplateCreateRequest`/`UpdateRequest`/`ExpandRequest`/`ApplyRequest`, `PlanDraft`, `PlanBatchCreateRequest`, `PlanAIGenerateRequest`/`Response`, `PlanManagerInfo`, `PlanManagersResponse`, literal-типы `PlanPeriodMode` (`current_month`\|`current_quarter`\|`current_year`\|`custom_period`) и `PlanAssigneesMode` (`all_managers`\|`department`\|`specific`\|`global`)
- API-клиент `departmentsApi` в [`services/api.ts`](frontend/src/services/api.ts): `list()` (`GET /departments`), `getTree()` (`GET /departments/tree`), `triggerSync()` (`POST /departments/sync`, 409 если sync уже идёт), `getManagers(id, {recursive?, active_only?})` (`GET /departments/{id}/managers` — DTO `PlanManagersResponse`, тот же, что у `/plans/meta/managers`); TS-типы `Department`, `DepartmentTreeNode` (self-ref), `DepartmentTreeResponse`, `DepartmentSyncResponse`
- Роут `/ai/plans` → `<PlansPage />` в [`App.tsx`](frontend/src/App.tsx) (находится внутри группы AI вместе с `/ai/charts` и `/ai/reports`)
- Вкладка «Планы» в компоненте [`components/ai/AISubTabs.tsx`](frontend/src/components/ai/AISubTabs.tsx) рядом с «Графики» и «Отчёты»; `PlansPage` рендерит `<AISubTabs />` в шапке
- i18n-ключ `ai.plansTab` в [`i18n/locales/ru.ts`](frontend/src/i18n/locales/ru.ts) («Планы») и [`i18n/locales/en.ts`](frontend/src/i18n/locales/en.ts) («Plans»); типизация в [`i18n/types.ts`](frontend/src/i18n/types.ts)

**Таблица `plan_templates`** (миграция [`024_create_plan_templates_table.py`](backend/alembic/versions/024_create_plan_templates_table.py)):

Шаблоны массового создания планов — описывают «режим периода» (`period_mode`) + «режим получателей» (`assignees_mode`) и дефолтное `plan_value`. Фронт разворачивает шаблон в набор `PlanDraft` через `POST /plans/templates/{id}/expand`, даёт пользователю отредактировать значения и отправляет обратно в `POST /plans/templates/{id}/apply`, который мапит их в `PlanCreateRequest` и вызывает `PlanService.batch_create_plans` (all-or-nothing).

| Колонка | Тип | Назначение |
|---|---|---|
| `id` | BIGINT PK autoincrement | Идентификатор шаблона |
| `name` | VARCHAR(255) NOT NULL | Название шаблона (видно в UI) |
| `description` | TEXT NULL | Пояснительный комментарий |
| `table_name` | VARCHAR(64) NULL | Целевая таблица (nullable для builtin без привязки) |
| `field_name` | VARCHAR(128) NULL | Целевое числовое поле (nullable для builtin) |
| `period_mode` | VARCHAR(32) NOT NULL | `current_month` \| `current_quarter` \| `current_year` \| `custom_period` |
| `period_type` | VARCHAR(16) NULL | Для `custom_period`: `month` \| `quarter` \| `year` \| `custom` |
| `period_value` | VARCHAR(16) NULL | Для `custom_period` + fixed period_type: `YYYY-MM` / `YYYY-QN` / `YYYY` |
| `date_from` / `date_to` | DATE NULL | Для `custom_period` + `period_type='custom'` |
| `assignees_mode` | VARCHAR(32) NOT NULL | `all_managers` \| `department` \| `specific` \| `global` |
| `department_name` | VARCHAR(255) NULL | Для `assignees_mode='department'`: имя отдела (резолвится в bitrix_id через `bitrix_departments.name` при expand) |
| `specific_manager_ids` | TEXT NULL | JSON array bitrix_id менеджеров (для `specific`); сериализация через `json.dumps`, десериализация в `list[str]` в сервисе |
| `default_plan_value` | NUMERIC(18,2) NULL | Значение плана по умолчанию (может быть переопределено в UI) |
| `is_builtin` | BOOLEAN DEFAULT FALSE | Защищённый системный шаблон (нельзя удалить; name/period_mode/assignees_mode заморожены) |
| `created_by_id` | VARCHAR(32) NULL | JWT-id пользователя, создавшего шаблон |
| `created_at` / `updated_at` | DATETIME default `NOW()` | Время создания / последнего обновления |
| Индекс | `ix_plan_templates_is_builtin` | Быстрая фильтрация builtin / custom |

Seed-запись (в той же миграции 024): `(name='Все менеджеры на текущий месяц', description='Создать индивидуальный план для каждого активного менеджера на текущий календарный месяц', period_mode='current_month', assignees_mode='all_managers', is_builtin=TRUE)`. Вставка через `op.execute(sa.text(...).bindparams(...))` — cross-dialect PG/MySQL.

**Backend-файлы plan_templates:**

- Доменная сущность [`PlanTemplateEntity`](backend/app/domain/entities/plan_template.py) (Pydantic, Literal-типы `PeriodMode`/`AssigneesMode`/`TemplatePeriodType`, `specific_manager_ids: list[str] | None` уже распарсен из JSON)
- Сервис [`PlanTemplateService`](backend/app/domain/services/plan_template_service.py):
  - CRUD `list_templates` / `get_template` / `create_template(payload, created_by_id)` / `update_template(id, payload)` / `delete_template(id)` — для builtin: `update_template` блокирует изменение `name`/`period_mode`/`assignees_mode` (через `PlanTemplateConflictError`), `delete_template` блокирует удаление целиком
  - `expand_template(template_id, overrides) → list[PlanDraft]`:
    1. `_resolve_period(template, period_value_override)` → `(period_type, period_value, date_from, date_to)`: `current_month` → `(month, '%Y-%m', None, None)`, `current_quarter` → `(quarter, 'YYYY-QN', None, None)` (`quarter = (month-1)//3 + 1`), `current_year` → `(year, '%Y', None, None)`, `custom_period` → поля template как есть;
    2. по `assignees_mode`: `all_managers` → `_fetch_all_active_managers()` (`SELECT * FROM bitrix_users WHERE active='Y'`), `department` → `_resolve_department_ids(department_name)` ищет отдел в `bitrix_departments.name` + `DepartmentService.collect_descendant_ids` + `list_managers_in_departments(active_only=True)`, `specific` → `_fetch_users_by_ids(specific_manager_ids)` с warning-ами для inactive/missing юзеров, `global` → 1 draft с `assigned_by_id=None`;
    3. overrides `table_name`/`field_name` обязательны для builtin (иначе `PlanTemplateValidationError`), `period_value` переопределяет вычисленное значение
  - `_parse_specific_ids` / `_serialize_specific_ids` — JSON round-trip с fallback `[]` на malformed
  - Ошибки: `PlanTemplateNotFoundError` (404), `PlanTemplateConflictError` (400 для builtin-блокировок), `PlanTemplateValidationError` (400)
- Эндпоинты (`api/v1/endpoints/plans.py`): `POST /plans/batch`, `GET`/`POST /plans/templates`, `GET`/`PUT`/`DELETE /plans/templates/{id}`, `POST /plans/templates/{id}/expand`, `POST /plans/templates/{id}/apply`, `GET /plans/meta/managers?department_id=...&recursive=true` (см. полный список в таблице эндпоинтов выше). Хелпер `_raise_for_template_error` маппит service-exceptions → HTTPException. Endpoint `apply` валидирует совпадение `template_id` в path и body, пропускает drafts через effective-resolution (override → draft → template) и делегирует в `PlanService.batch_create_plans` для атомарного INSERT всех записей

#### Модуль «Отделы»

Модуль предоставляет иерархию отделов Bitrix24 (`department.get`) и связь юзеров с отделами (через `UF_DEPARTMENT` из `user.get`). Основа для групповых планов по отделу и для механизма раскрытия шаблонов задач на всех подчинённых руководителя.

**Таблица `bitrix_departments`** (миграция [`023_create_bitrix_departments_table.py`](backend/alembic/versions/023_create_bitrix_departments_table.py)):

| Колонка | Тип | Назначение |
|---|---|---|
| `id` | BIGINT PK autoincrement | Внутренний суррогатный ключ |
| `bitrix_id` | VARCHAR(32) UNIQUE | ID отдела в Bitrix24 (target для UPSERT) |
| `name` | VARCHAR(255) NULL | Название отдела |
| `parent_id` | VARCHAR(32) NULL, индекс `ix_bitrix_departments_parent` | ID родителя; NULL у корня |
| `sort` | INT default 500 | Порядок сортировки (как в Bitrix24) |
| `uf_head` | VARCHAR(32) NULL | `bitrix_id` пользователя-руководителя |
| `created_at` / `updated_at` | DATETIME default `NOW()` | Время первого/последнего UPSERT |

**Таблица `bitrix_user_departments`** (junction, та же миграция):

| Колонка | Тип | Назначение |
|---|---|---|
| `user_id` | VARCHAR(32) | `bitrix_id` пользователя (из `bitrix_users`) |
| `department_id` | VARCHAR(32) | `bitrix_id` отдела (из `bitrix_departments`) |
| PK | `(user_id, department_id)` | Естественный UNIQUE |
| Индексы | `ix_bud_user` по `user_id`, `ix_bud_dept` по `department_id` | Быстрая выборка «отделы юзера» и «юзеры отдела» |

Таблица без FK на стороне БД (намеренно, для устойчивости к рассинхрону порядка синхронизаций); целостность поддерживается sync-слоем: DELETE-then-INSERT всех связей юзера при каждой синхронизации его записи.

**Backend-файлы:**

- Доменная сущность [`DepartmentEntity`](backend/app/domain/entities/department.py) (dataclass, поля `bitrix_id/name/parent_id/sort/uf_head`)
- Сервис [`DepartmentSyncService`](backend/app/domain/services/department_sync_service.py) — одно публичное API: `full_sync()`. Вызывает `BitrixClient.get_all('department.get')`, UPSERT в `bitrix_departments` по `bitrix_id` (dialect-aware), пишет в `sync_logs` с `entity_type='ref:department'`. Класс-level `_running_syncs: dict` + `is_running()` — дедуп для HTTP-триггеров. Нормализация: пустые `PARENT`/`UF_HEAD` → NULL, `bitrix_id` всегда строка.
- Сервис [`DepartmentService`](backend/app/domain/services/department_service.py) (read-only) — основные методы:
  - `list_departments()` — плоский SELECT по `sort, bitrix_id` → `list[DepartmentEntity]`
  - `get_department(bitrix_id)` — одна запись или `None`
  - `build_tree()` → `list[dict]` — сначала `list_departments`, затем `_build_tree_in_memory` (группировка по `parent_id`, сортировка детей и корней по `(sort, id)`). Возвращает корни с вложенными `children`. Сироты (родитель не найден) поднимаются на верхний уровень
  - `collect_descendant_ids(root_bitrix_id)` — BFS по in-memory карте parent→children; root включён в ответ, дубликатов нет, цикл защищён `visited`-set'ом. Если root не существует → `[]`
  - `list_managers_in_departments(department_ids, active_only=True)` — один SELECT с `DISTINCT` и `JOIN bitrix_users ON bitrix_id=user_id` + `WHERE department_id IN :ids` (через `bindparam(..., expanding=True)`). Если `active_only=True`, фильтр по `bitrix_users.active='Y'` (или NULL — для записей без поля)
- Схемы [`api/v1/schemas/departments.py`](backend/app/api/v1/schemas/departments.py): `DepartmentResponse`, `DepartmentTreeNode` (self-ref children через `model_rebuild`), `DepartmentTreeResponse`, `DepartmentSyncResponse`, `ManagerInfo`, `ManagersListResponse`
- Эндпоинты [`api/v1/endpoints/departments.py`](backend/app/api/v1/endpoints/departments.py) — 4 маршрута: `GET /departments`, `GET /departments/tree`, `POST /departments/sync` (через `BackgroundTasks`; 409 если `DepartmentSyncService.is_running()`), `GET /departments/{id}/managers?recursive=true&active_only=true` (recursive default `true` — UI-friendly)
- Регистрация роутера: `router.include_router(departments.router, prefix="/departments", tags=["departments"], dependencies=_auth)` в [`api/v1/__init__.py`](backend/app/api/v1/__init__.py)

**Интеграция с SyncService (user sync):**

В [`sync_service.py`](backend/app/domain/services/sync_service.py) добавлены:

- `_sync_user_departments(conn, user_id, uf_department)` — статический хелпер, пишет связи в `bitrix_user_departments` внутри уже открытой транзакции (`conn` от `engine.begin()`): сначала `DELETE FROM bitrix_user_departments WHERE user_id=:user_id`, затем `INSERT` по каждому ID из `UF_DEPARTMENT`. Нормализация: list/tuple/scalar/None → итерируемая коллекция; каждый элемент конвертируется через `int(raw) → str`; дубликаты внутри одной записи пропускаются (`seen`-set)
- В `_upsert_records` после UPSERT каждой записи пользователя (когда `table_name == bitrix_users`) вызывается `_sync_user_departments(conn, data['bitrix_id'], record.get('UF_DEPARTMENT'))`. `UF_DEPARTMENT` читается из исходного `record` до JSON-сериализации, чтобы получить оригинальный list
- В `_sync_related_references` для `entity_type == 'user'` добавлен best-effort прямой вызов `DepartmentSyncService.full_sync()` — отделы синхронизируются вместе с юзерами. Не через `SyncQueue` (нет `REFERENCE` task_type для department), дедуп через `_running_syncs` самого сервиса

Таким образом при вызове `POST /api/v1/sync/start/user` (или scheduled sync) в одной операции: актуализируется таблица `bitrix_users`, пересобираются связи `bitrix_user_departments` по актуальному `UF_DEPARTMENT`, и фоново синхронизируются справочники `bitrix_departments` и референсные таблицы.

### 3. Infrastructure Layer (`app/infrastructure/`)

```
app/infrastructure/
├── bitrix/
│   └── client.py            # BitrixClient с retry и rate limiting
├── database/
│   ├── connection.py        # AsyncEngine, get_session, get_dialect()
│   ├── models.py            # SQLAlchemy модели (SyncConfig, SyncLog, SyncState, AIChart, SchemaDescription, ChartPromptTemplate, PublishedDashboard, DashboardChart, DashboardLink, DashboardSelector, SelectorChartMapping, Plan). Таблицы `bitrix_departments`, `bitrix_user_departments`, `plan_templates` намеренно без ORM-моделей — адресация через raw `text()` в соответствующих сервисах (DepartmentService, DepartmentSyncService, PlanTemplateService)
│   └── dynamic_table.py     # Динамическое создание таблиц (кросс-БД, с комментариями полей). Системные колонки: record_id (PK), bitrix_id VARCHAR(50) UNIQUE, bitrix_id_int BIGINT nullable indexed, created_at, updated_at
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
    ├── 019_add_hide_title_to_dashboard_charts.py  # Колонка hide_title в dashboard_charts
    ├── 020_add_title_font_size_override.py  # Колонка title_font_size_override в dashboard_charts
    ├── 021_add_bitrix_id_int.py  # Идемпотентная миграция: добавление BIGINT-колонки bitrix_id_int во все динамические Bitrix-таблицы (crm_*/bitrix_*/stage_history_*), обработка трёх состояний (строковый/числовой/оба) для PG и MySQL, downgrade для state A
    ├── 022_create_plans_table.py  # Таблица plans: пользовательские плановые значения для числовых полей любых таблиц; колонки table_name/field_name/assigned_by_id/period_type/period_value/date_from/date_to/plan_value + индексы + uq_plan_key
    ├── 023_create_bitrix_departments_table.py  # Две таблицы: bitrix_departments (справочник отделов, PK id BIGINT autoincrement, UNIQUE bitrix_id, индекс ix_bitrix_departments_parent по parent_id, поля name/sort/uf_head) и bitrix_user_departments (junction, PK (user_id, department_id), индексы ix_bud_user/ix_bud_dept). Кросс-БД: sa.BigInteger+autoincrement=True, sa.DateTime+server_default=now()
    ├── 024_create_plan_templates_table.py  # Таблица plan_templates: шаблоны массового создания планов. Колонки name, description, table_name/field_name (nullable для builtin), period_mode (current_month|current_quarter|current_year|custom_period) + period_type/period_value/date_from/date_to, assignees_mode (all_managers|department|specific|global) + department_name/specific_manager_ids (JSON text), default_plan_value Numeric(18,2), is_builtin Boolean (index ix_plan_templates_is_builtin), created_by_id, timestamps. Seed-запись в миграции: builtin-шаблон 'Все менеджеры на текущий месяц' через op.execute(sa.text(...).bindparams(...)) — cross-dialect PG/MySQL
    └── 025_update_bitrix_context_transitions.py  # Идемпотентное обновление chart_prompt_templates.content WHERE name='bitrix_context' для существующих инсталляций: добавляет в конец content подсекцию «Фильтр по дате создания сделки на чартах переходов» (раздел «Конверсия между стадиями (переходы)»). Защита от повторного применения через проверку якорной фразы (`content NOT LIKE '%Фильтр по дате создания сделки на чартах переходов%'`) — ручные правки админа не затираются. Кросс-диалектная конкатенация: PG `content || :new_block` / MySQL `CONCAT(content, :new_block)` через `op.get_bind().dialect.name`. Текст блока синхронизирован с DEFAULT_BITRIX_PROMPT из миграции 009. downgrade выполняет REPLACE того же блока на пустую строку (no-op, если блока нет)
```

#### connection.py — ключевые функции:

```python
async def init_db() -> None       # Инициализация engine по DATABASE_URL
def get_engine()                   # Получить AsyncEngine
def get_dialect() -> str           # "postgresql" или "mysql"
async def get_session()            # Dependency для FastAPI
```

#### dynamic_table.py — системные колонки динамических Bitrix-таблиц

`DynamicTableBuilder` создаёт таблицы `crm_*` (deals/contacts/leads/companies), `bitrix_*` (calls) и `stage_history_*` на основе метаданных полей Bitrix API (`.fields` или захардкоженных `*_FIELD_TYPES`). Поля с именами из `RESERVED_COLUMNS` игнорируются при импорте пользовательских полей; в каждую таблицу добавляется фиксированный набор системных колонок:

| Колонка | Тип | Назначение |
|---|---|---|
| `record_id` | `BigInteger` (PK, autoincrement) | Внутренний суррогатный ключ |
| `bitrix_id` | `VARCHAR(50)` UNIQUE, NOT NULL, индекс | Канонический строковый идентификатор записи в Bitrix24 (источник правды для UPSERT и JOIN'ов из `chart_prompts`, `reports` и селекторных маппингов) |
| `bitrix_id_int` | `BIGINT`, nullable, индекс `ix_<table>_bitrix_id_int` | Числовое зеркало `bitrix_id` для числовых JOIN'ов и фильтров; заполняется sync-сервисом параллельно со строковой колонкой, `bitrix_id_int::text = bitrix_id` для всех записей с числовым идентификатором |
| `created_at` | `DateTime`, `server_default=now()` | Время первого UPSERT записи |
| `updated_at` | `DateTime`, `server_default=now()`, `onupdate=now()` | Время последнего обновления записи |

Обе колонки `bitrix_id` и `bitrix_id_int` поддерживаются одновременно: строковая — основной уникальный ключ и UPSERT-таргет, числовая — оптимизация для отчётов и чартов, которые джойнят по числовому идентификатору.

Метод `DynamicTableBuilder._ensure_bitrix_id_int_column(table_name)` вызывается из `create_table_from_fields` после `metadata.create_all` и выполняет runtime-safety net для legacy-таблиц: при необходимости добавляет колонку `bitrix_id_int` (ALTER TABLE), бэкфиллит её из `bitrix_id` по регекспу `^[0-9]+$` и создаёт индекс `ix_<table>_bitrix_id_int`. Идемпотентен, запускается на каждом старте синхронизации, независим от alembic-миграции 021.

Для MySQL строковые колонки с типом `String` автоматически конвертируются в `Text` (обход лимита 65535 байт на строку DDL), таблицы создаются с `mysql_row_format="DYNAMIC"`.

### 4. Core Layer (`app/core/`)

```
app/core/
├── auth.py                  # JWT валидация (опциональная)
├── exceptions.py            # Кастомные исключения (AppException, AIServiceError, ChartServiceError и др.)
├── job_store.py             # In-memory job store для долгих фоновых задач (asyncio.create_task); JobRecord, create_job/get_job/update_job
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
├── App.tsx                    # Роутинг (/ai/charts, /ai/reports, /ai/plans, /schema, /config, /monitoring, /validation, /dashboards, ...). Роут `/ai/plans` монтирует `PlansPage`
├── components/
│   ├── Layout.tsx             # Навигация верхнего уровня (Dashboard, AI, Configuration, Monitoring, Validation, Schema)
│   ├── SyncCard.tsx           # Карточка синхронизации CRM-сущности
│   ├── ReferenceCard.tsx      # Карточка справочника (статусы, воронки, валюты)
│   ├── charts/
│   │   ├── ChartRenderer.tsx  # Универсальный рендер чарта (bar/line/pie/area/scatter/funnel/horizontal_bar через Recharts, indicator — KPI-карточка, table — таблица с итогами и сортировкой). Опциональный проп fontScale?: number — масштабирует ticks, axis labels, legend, data labels, pie label, indicator value и table cells через helper fs(base)=max(8, round(base*fontScale)). При fontScale==null — IndicatorRenderer использует py-8, TableRenderer сохраняет text-sm на <table> (non-TV режим байт-стабилен относительно master). Флаг spec.general.fixedFontSize=true форсит effectiveFontScale=undefined (hard override пропа fontScale) во всех местах: fs()/fScale/horizontal_bar charPx/IndicatorRenderer/TableRenderer — и дополнительно для indicator выставляет resolvedFillHeight=false, чтобы autoFit-контейнер не растягивал значение на всю ячейку; используется для фиксации размера шрифта при растягивании (TV-режим, ресайз ячейки)
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
│   ├── plans/
│   │   ├── PlanFormModal.tsx          # Модалка создания/редактирования одного плана. В create-режиме 4 таба назначения (single/multi/department/global): multi и department разворачиваются через plansApi.batchCreate в N копий плана. Department-режим: select отдела из departmentsApi.getTree() + чекбокс «Включая подотделы» + live-preview менеджеров через departmentsApi.getManagers. Edit-режим показывает классический single-select менеджера (backward-compat).
│   │   ├── PlanDraftsTable.tsx        # Переиспользуемая таблица PlanDraft[] с inline-редактированием plan_value/description, удалением строки, жёлтой подсветкой warnings (иконка ⚠ с tooltip) и красной подсветкой невалидных сумм. Props: drafts, onChange, onRemove?, managers?, readOnlyFields?. Используется в AIGeneratePlansModal и ApplyTemplateModal.
│   │   ├── AIGeneratePlansModal.tsx   # Модалка AI-генерации: textarea описания, collapsible hints (table/field select), кнопка «✨ Сгенерировать» → plansApi.aiGenerate (до 5 мин), предпросмотр через PlanDraftsTable, «Сохранить все (N)» → plansApi.batchCreate. 502/503 → «AI временно недоступен».
│   │   ├── PlanTemplatesDrawer.tsx    # Side drawer справа со списком шаблонов (plansApi.listTemplates). На каждом шаблоне: бейдж «⭐ builtin», Применить/Редактировать/Удалить (delete disabled+tooltip для builtin). Кнопка «+ Новый шаблон» открывает PlanTemplateFormModal. onApply(id) зовёт родителя, который открывает ApplyTemplateModal.
│   │   ├── PlanTemplateFormModal.tsx  # Форма создания/редактирования шаблона плана: name, description, optional table/field, period_mode (current_month/quarter/year/custom_period — для custom_period доп. поля), assignees_mode (all_managers/department/specific/global — select отдела или multi-select менеджеров), default_plan_value. Для builtin name/period_mode/assignees_mode заблокированы.
│   │   └── ApplyTemplateModal.tsx     # Применение шаблона: plansApi.getTemplate → (при отсутствии target) обязательные override select'ы table/field → optional period override → default bulk value с «Заполнить всем» → «Подготовить превью» (plansApi.expandTemplate) → PlanDraftsTable для редактирования → «Сохранить все» (plansApi.applyTemplate).
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
│   ├── PlansPage.tsx          # Управление плановыми значениями («план/факт»): таблица планов (таблица/поле/менеджер/период/план/факт/отклонение), батчевая загрузка vs-actual через Promise.allSettled, человекочитаемый период (Апрель 2026, 2026 — Q2, custom-диапазон). Action-бар: «+ Добавить план» (components/plans/PlanFormModal), «✨ Сгенерировать через AI» (components/plans/AIGeneratePlansModal), «⭐ Избранные» (components/plans/PlanTemplatesDrawer → ApplyTemplateModal). Предзагружает bitrix_users через chartsApi.executeSql (для single/multi/edit) и managers через plansApi.listManagers (для резолвинга имён в PlanDraftsTable). Toast 3с при успешном batch/apply. Удаление одиночного плана через window.confirm.
│   ├── EmbedDashboardPage.tsx # Публичный дашборд: аутентификация, вкладки (linked-дашборды), авто-обновление, per-tab селекторы и per-tab filterValuesByTab (фильтры главного и вторичных табов хранятся раздельно). Полиморфный рендер dashboard.charts: ветка item_type==='heading' рендерит HeadingItem (read-only) в позицию gridStyle, остальные — DashboardChartCard. Фильтрует heading из fetchAllChartData/fetchLinkedChartData чтобы не делать запросы /chart/{id}/data. TV-режим (?tv=1 через useTvMode): чекбокс «Режим ТВ» и кнопка «Сбросить макет» в шапке (handleTvReset чистит localStorage[tv_layout_<storageKey>] и инкрементит tvKey для remount); при tvMode внешний контейнер становится fullscreen (p-2 / w-full, description скрыт); inline-функции renderTvChartCard(dc, fontScale, chartHeight) и renderTvHeading(dc, fontScale) повторяют логику DashboardChartCard/HeadingItem: заголовок чарта берётся напрямую из настроек редактора (getTitleSizeStyle(dc.title_font_size_override || config.general.titleFontSize)) БЕЗ умножения на fontScale — пользователь задаёт точный размер ползунком и TV-режим его уважает; fontScale прокидывается только в ChartRenderer/HeadingItem для осей/легенды/значений; условный рендер: tvMode → <TvModeGrid key={tvKey + '_' + tvStorageKey} storageKey charts chartData renderChart renderHeading />, иначе исходный CSS-grid без изменений. tvStorageKey = activeTab === 'main' ? slug : activeTab — каждый linked-таб хранит свой layout отдельно.
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
│   └── api.ts                 # Axios клиент, типы, API-объекты (syncApi, referencesApi, chartsApi, schemaApi, dashboardsApi, publicApi, plansApi — CRUD /plans + /plans/{id}/vs-actual + /plans/meta/tables + /plans/meta/numeric-fields; типы Plan, PlanCreateRequest, PlanUpdateRequest, PlanVsActual, PlanPeriodType, NumericFieldInfo, PlanTableInfo). Типы DashboardSelector, SelectorMapping (с post_filter_resolve_*), LabelResolver, FilterValue. Полиморфный DashboardChart (item_type='chart'|'heading', chart_id?, heading_config?). Heading-типы: HeadingConfig (text, level 1-6, align, color, bg_color, divider), HeadingCreateRequest, HeadingUpdateRequest. Endpoints: dashboardsApi.generateSelectors(dashboardId, userRequest?, chartIds?) — chartIds ограничивает AI-генерацию подмножеством чартов, dashboardsApi.addHeading, dashboardsApi.updateHeading, publicApi.getLinkedPublicSelectorOptionsBatch
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
