# Changelog

Все значимые изменения в проекте документируются в этом файле.

## [Unreleased]

### Added
- **Автоматическое применение миграций при запуске Docker** - миграции Alembic теперь применяются автоматически при каждом запуске backend контейнера
- `backend/entrypoint.sh` - скрипт для автоматической инициализации с проверкой готовности PostgreSQL
- `SETUP.md` - подробная инструкция по установке и настройке с примерами команд для генерации ключей
- Расширенные переменные окружения в `.env.example` для Supabase сервисов

### Changed
- `backend/Dockerfile` - добавлен `postgresql-client` для проверки готовности БД
- `backend/Dockerfile` - настроен ENTRYPOINT для запуска скрипта автоматической инициализации
- `docker-compose.yml` - добавлена переменная `POSTGRES_PASSWORD` для backend сервиса
- `ARCHITECTURE.md` - обновлена документация архитектуры с описанием процесса автоматического применения миграций
- `README.md` - добавлены инструкции по проверке применения миграций и работе с Alembic
- `.env.example` - добавлены недостающие переменные: `SUPABASE_SERVICE_ROLE_KEY`, `SECRET_KEY_BASE`, `DASHBOARD_PASSWORD`

### Technical Details

#### Последовательность запуска
1. PostgreSQL контейнер стартует и выполняет скрипты инициализации из `/docker-entrypoint-initdb.d` (только при первом запуске)
2. Backend контейнер ожидает готовности PostgreSQL (до 30 попыток)
3. Alembic автоматически применяет все новые миграции (`alembic upgrade head`)
4. Приложение запускается после успешного применения миграций

#### Преимущества
- ✅ Не нужно вручную запускать миграции
- ✅ Автоматическая синхронизация схемы БД при обновлении кода
- ✅ Безопасный запуск с проверкой готовности БД
- ✅ Детальное логирование процесса инициализации
- ✅ Graceful degradation при ошибках соединения

#### Файлы изменений
```
new_version/
├── backend/
│   ├── entrypoint.sh (новый)        # Автоматическая инициализация
│   └── Dockerfile (изменен)         # ENTRYPOINT + postgresql-client
├── docker-compose.yml (изменен)     # POSTGRES_PASSWORD для backend
├── .env.example (изменен)           # Дополнительные переменные
├── ARCHITECTURE.md (изменен)        # Документация миграций
├── README.md (изменен)              # Инструкции по работе
├── SETUP.md (новый)                 # Подробная инструкция установки
└── CHANGELOG.md (новый)             # Этот файл
```

## [1.0.0] - Initial Release

### Features
- Полная и инкрементальная синхронизация CRM сущностей (сделки, контакты, лиды, компании)
- Webhook поддержка для real-time обновлений
- Динамическое создание таблиц на основе полей Bitrix24
- Scheduled синхронизация с APScheduler
- JWT аутентификация через Supabase
- Supabase Stack (Auth, Realtime, Storage, Studio)
- Docker Compose конфигурация для легкого развертывания
- Alembic миграции для управления схемой БД
- Comprehensive test suite (unit, integration, e2e)
- Structured logging с structlog
- Retry механизм для Bitrix24 API
- Clean Architecture структура проекта
