# Bitrix24 to PostgreSQL Sync Service

Сервис для синхронизации данных CRM из Bitrix24 в PostgreSQL с использованием Supabase для аутентификации.

## Обзор

Этот сервис позволяет:
- Синхронизировать сущности CRM (сделки, контакты, лиды, компании) из Bitrix24 в PostgreSQL
- Поддерживать полную и инкрементальную синхронизацию
- Получать webhook-уведомления от Bitrix24 для real-time обновлений
- Автоматически создавать и обновлять схему БД на основе полей Bitrix24
- Настраивать расписание синхронизации через API

## Архитектура

```
┌─────────────┐     ┌─────────────────┐     ┌────────────────┐
│  Bitrix24   │────▶│  FastAPI Backend │────▶│   PostgreSQL   │
│   CRM API   │◀────│  + APScheduler   │     │   (Supabase)   │
└─────────────┘     └─────────────────┘     └────────────────┘
       │                    │
       │ webhooks           │
       └────────────────────┘
```

## Требования

- Docker и Docker Compose
- Bitrix24 аккаунт с настроенным webhook
- (Опционально) Внешний URL для получения webhooks

## Быстрый старт

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd bitrix-to-postgres/new_version
```

### 2. Настройка переменных окружения

Создайте файл `.env` на основе примера:

```bash
cp .env.example .env
```

Отредактируйте `.env`:

```env
# PostgreSQL
POSTGRES_PASSWORD=your_secure_password

# Supabase Auth
JWT_SECRET=your-super-secret-jwt-key-min-32-characters
SUPABASE_ANON_KEY=your-supabase-anon-key

# Bitrix24
BITRIX_WEBHOOK_URL=https://your-domain.bitrix24.ru/rest/1/your-webhook-code/

# Application
DEBUG=false
SITE_URL=http://localhost:3000
API_URL=http://localhost:8080
PUBLIC_SUPABASE_URL=http://localhost:8000
```

### 3. Получение Bitrix24 Webhook URL

1. Войдите в ваш Bitrix24
2. Перейдите в **Приложения** → **Webhooks** → **Входящие вебхуки**
3. Нажмите **Добавить вебхук**
4. Выберите необходимые права:
   - `crm` - доступ к CRM
   - `crm.deal` - работа со сделками
   - `crm.contact` - работа с контактами
   - `crm.lead` - работа с лидами
   - `crm.company` - работа с компаниями
5. Скопируйте сгенерированный URL в `BITRIX_WEBHOOK_URL`

### 4. Запуск сервисов

```bash
docker-compose up -d
```

Сервисы будут доступны:
- **Backend API**: http://localhost:8080
- **Frontend**: http://localhost:3000
- **Supabase API**: http://localhost:8000
- **PostgreSQL**: localhost:5432

### 5. Проверка работоспособности

```bash
curl http://localhost:8080/health
```

## Конфигурация

### Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `DATABASE_URL` | PostgreSQL connection string | - |
| `BITRIX_WEBHOOK_URL` | Bitrix24 webhook URL | - |
| `SUPABASE_URL` | Supabase API URL | - |
| `SUPABASE_KEY` | Supabase anon key | - |
| `SUPABASE_JWT_SECRET` | JWT secret для валидации токенов | - |
| `DEBUG` | Режим отладки | `false` |
| `SYNC_BATCH_SIZE` | Размер пакета для синхронизации | `50` |
| `SYNC_DEFAULT_INTERVAL_MINUTES` | Интервал синхронизации по умолчанию | `30` |

## API Документация

### Синхронизация

#### Запуск синхронизации

```bash
# Полная синхронизация сделок
curl -X POST http://localhost:8080/api/v1/sync/start/deal \
  -H "Content-Type: application/json" \
  -d '{"sync_type": "full"}'

# Инкрементальная синхронизация контактов
curl -X POST http://localhost:8080/api/v1/sync/start/contact \
  -H "Content-Type: application/json" \
  -d '{"sync_type": "incremental"}'
```

Поддерживаемые сущности: `deal`, `contact`, `lead`, `company`

#### Получение статуса синхронизации

```bash
curl http://localhost:8080/api/v1/sync/status
```

#### Конфигурация синхронизации

```bash
# Получить конфигурацию
curl http://localhost:8080/api/v1/sync/config

# Обновить конфигурацию
curl -X PUT http://localhost:8080/api/v1/sync/config \
  -H "Content-Type: application/json" \
  -d '{
    "entity_type": "deal",
    "enabled": true,
    "sync_interval_minutes": 15,
    "webhook_enabled": true
  }'
```

### Webhooks

#### Регистрация webhooks в Bitrix24

```bash
# Зарегистрировать webhooks
curl -X POST "http://localhost:8080/api/v1/webhooks/register?handler_base_url=https://your-public-url.com"

# Отменить регистрацию
curl -X DELETE "http://localhost:8080/api/v1/webhooks/unregister?handler_base_url=https://your-public-url.com"

# Получить список зарегистрированных webhooks
curl http://localhost:8080/api/v1/webhooks/registered
```

#### Endpoint для Bitrix24

Bitrix24 будет отправлять события на:
```
POST https://your-public-url.com/api/v1/webhooks/bitrix
```

Поддерживаемые события:
- `ONCRMDEALUPDATE`, `ONCRMDEALADD`, `ONCRMDEALDELETE`
- `ONCRMCONTACTUPDATE`, `ONCRMCONTACTADD`, `ONCRMCONTACTDELETE`
- `ONCRMLEADUPDATE`, `ONCRMLEADADD`, `ONCRMLEADDELETE`
- `ONCRMCOMPANYUPDATE`, `ONCRMCOMPANYADD`, `ONCRMCOMPANYDELETE`

## Разработка

### Настройка окружения для разработки

```bash
cd new_version/backend

# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
.\venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -e ".[dev]"
```

### Запуск в режиме разработки

```bash
# Только база данных
docker-compose up -d db auth

# Backend с hot-reload
cd backend
DEBUG=true uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# Frontend с hot-reload
cd frontend
npm install
npm run dev
```

### Структура проекта

```
new_version/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API endpoints
│   │   ├── core/            # Auth, logging, exceptions
│   │   ├── domain/          # Business logic
│   │   │   ├── entities/    # Pydantic models
│   │   │   └── services/    # Sync service
│   │   ├── infrastructure/  # External services
│   │   │   ├── bitrix/      # Bitrix24 client
│   │   │   ├── database/    # DB connection, models
│   │   │   └── scheduler/   # APScheduler
│   │   └── tests/           # Unit, integration, e2e tests
│   ├── alembic/             # Database migrations
│   └── pyproject.toml
├── frontend/                # React frontend
├── docker-compose.yml
└── README.md
```

## Тестирование

### Запуск тестов

```bash
cd backend

# Все тесты
pytest

# Unit тесты
pytest app/tests/unit/

# Integration тесты
pytest app/tests/integration/

# E2E тесты
pytest app/tests/e2e/

# С покрытием
pytest --cov=app --cov-report=html
```

### Типы тестов

- **Unit тесты** (`app/tests/unit/`): Тестируют отдельные компоненты с моками
- **Integration тесты** (`app/tests/integration/`): Тестируют API endpoints
- **E2E тесты** (`app/tests/e2e/`): Тестируют полный flow синхронизации

## Устранение неполадок

### Проблемы с подключением к Bitrix24

1. Проверьте правильность `BITRIX_WEBHOOK_URL`
2. Убедитесь, что webhook имеет необходимые права
3. Проверьте логи: `docker-compose logs backend`

### Проблемы с базой данных

1. Проверьте подключение: `docker-compose exec db pg_isready`
2. Проверьте логи: `docker-compose logs db`
3. Запустите миграции вручную:
   ```bash
   docker-compose exec backend alembic upgrade head
   ```

### Webhooks не приходят

1. Убедитесь, что ваш сервер доступен из интернета
2. Проверьте, что webhooks зарегистрированы: `curl http://localhost:8080/api/v1/webhooks/registered`
3. Используйте ngrok для локальной разработки:
   ```bash
   ngrok http 8080
   # Используйте полученный URL для регистрации webhooks
   ```

### Ошибки синхронизации

1. Проверьте статус: `curl http://localhost:8080/api/v1/sync/status`
2. Проверьте логи: `docker-compose logs backend | grep -i error`
3. Проверьте таблицу `sync_logs` в базе данных

## Лицензия

MIT License
