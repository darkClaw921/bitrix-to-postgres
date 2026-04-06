---
name: Типичная фазовая структура задач для new_version
description: Паттерн декомпозиции backend+frontend фич в проекте Bitrix24 sync (FastAPI Clean Arch + React)
type: project
---

## Стандартный шаблон фаз для full-stack фичи

Для фичи, затрагивающей и backend (FastAPI Clean Arch), и frontend (React+TS), хорошо работает 6-фазная декомпозиция:

1. **Phase 1 — БД и модели:** Alembic миграция (cross-DB PG/MySQL!) + SQLAlchemy модель в `backend/app/infrastructure/database/models.py` + ручная валидация схемы.
2. **Phase 2 — Pydantic schemas + Domain Service:** схемы в `backend/app/api/v1/schemas/` + методы в `backend/app/domain/services/<entity>_service.py` (raw `text()` queries через `get_engine().begin()`).
3. **Phase 3 — REST endpoints:** в `backend/app/api/v1/endpoints/` + защита публичных endpoints в `public.py` если нужна.
4. **Phase 4 — Frontend types и API client:** `frontend/src/services/api.ts` (типы + методы) + `frontend/src/hooks/useXxx.ts` (React Query mutations с invalidate).
5. **Phase 5 — UI компоненты:** новые компоненты в `frontend/src/components/...` + интеграция в `pages/*Page.tsx` (Editor + Embed/Public).
6. **Phase 6 — i18n + ARCHITECTURE.md:** локализационные ключи во всех файлах `frontend/src/i18n/*` + обновление `ARCHITECTURE.md` (только архитектура, БЕЗ статусов и тестирования).

## Cross-DB особенности backend (важны для миграций и сервисов)

- Cross-DB ALTER COLUMN: смотреть последние миграции (например `016_add_post_filter_to_mappings.py`) на предмет паттерна `op.get_bind().dialect.name`.
- INSERT и получение ID: PG → `RETURNING id`, MySQL → `result.lastrowid`. Паттерн уже есть в `DashboardService.create_dashboard`.
- JSON колонки в MySQL могут возвращаться как str — нужен `json.loads` с fallback при чтении.
- UPSERT: `ON CONFLICT DO UPDATE` (PG) / `ON DUPLICATE KEY UPDATE` (MySQL).
- Раздельных моделей не делаем — динамические таблицы через `DynamicTableBuilder`, raw SQL через `text()`.

## Конвенции названий задач

- Эпики: `Phase N: <Описание фазы>`
- Задачи: `PN.M: <Глагол + что сделать>` (например `P2.4: Реализовать DashboardService.add_heading`)
- Все на русском (как и план).

## Frontend конвенции

- ReactGridLayout drag-handle: при добавлении inline-edit полей нужно учитывать, чтобы input не перехватывал drag (event.stopPropagation или специальный CSS class).
- Embed-страница `EmbedDashboardPage.tsx` отдельная от `DashboardEditorPage.tsx` — изменения данных и рендера нужно дублировать в обе, обычно ветвление по `item_type` или похожему дискриминатору.
- React Query кеш-ключи: использовать тот же паттерн что в существующих хуках (`['dashboard', id]`), invalidate в onSuccess мутаций.
