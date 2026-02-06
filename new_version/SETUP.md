# Инструкция по установке и настройке

## Генерация секретных ключей

Для работы приложения необходимо сгенерировать несколько секретных ключей. Используйте следующие команды:

### 1. Генерация всех ключей одной командой

```bash
cat > .env << 'EOF'
# Database
POSTGRES_PASSWORD=$(openssl rand -base64 32)

# Supabase JWT
JWT_SECRET=$(openssl rand -base64 32)

# Supabase Keys (временные, будут заменены после настройки)
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxvY2FsaG9zdCIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNjQxNzY5MjAwLCJleHAiOjE5NTczNDUyMDB9.dc6hdXN6IzqCWbP5F7LVdT0FfJzKqNjQG9L8VJ5s7r8
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxvY2FsaG9zdCIsInJvbGUiOiJzZXJ2aWNlX3JvbGUiLCJpYXQiOjE2NDE3NjkyMDAsImV4cCI6MTk1NzM0NTIwMH0.qNsmXzz2btmKbgGY8DqGhqnvS2K3kXzOCbJ5kqNX6H8

# Other secrets
SECRET_KEY_BASE=$(openssl rand -base64 32)
DASHBOARD_PASSWORD=$(openssl rand -base64 16)

# URLs
SITE_URL=http://localhost:3000
PUBLIC_SUPABASE_URL=http://localhost:8000
API_URL=http://localhost:8080

# Bitrix24 (необходимо заполнить вручную)
BITRIX_WEBHOOK_URL=https://your-portal.bitrix24.ru/rest/1/your-webhook-secret/

# Debug
DEBUG=true
EOF

echo "✓ Файл .env создан! Не забудьте добавить BITRIX_WEBHOOK_URL"
```

### 2. Генерация ключей по отдельности

Если нужно сгенерировать ключи вручную:

```bash
# POSTGRES_PASSWORD
openssl rand -base64 32

# JWT_SECRET
openssl rand -base64 32

# SECRET_KEY_BASE
openssl rand -base64 32

# DASHBOARD_PASSWORD
openssl rand -base64 16
```

## Настройка Bitrix24 Webhook

### Шаг 1: Создание входящего вебхука

1. Войдите в ваш портал Bitrix24
2. Перейдите в **Приложения** → **Вебхуки** → **Входящие вебхуки**
3. Нажмите **Добавить вебхук**
4. Выберите необходимые права доступа:

**Обязательные права:**
- ✓ `crm` - Доступ к CRM
- ✓ `user` - Доступ к пользователям (для получения информации о владельцах)

**Дополнительные права (рекомендуется):**
- ✓ CRM → Сделки (`crm.deal`) - Чтение и запись
- ✓ CRM → Контакты (`crm.contact`) - Чтение и запись
- ✓ CRM → Лиды (`crm.lead`) - Чтение и запись
- ✓ CRM → Компании (`crm.company`) - Чтение и запись

5. Нажмите **Сохранить**
6. Скопируйте полученный URL (формат: `https://your-portal.bitrix24.ru/rest/1/xxxxx/`)

### Шаг 2: Добавление URL в .env

Откройте файл `.env` и вставьте URL:

```env
BITRIX_WEBHOOK_URL=https://your-portal.bitrix24.ru/rest/1/xxxxx/
```

### Шаг 3: Настройка исходящих вебхуков (для real-time синхронизации)

Для автоматической синхронизации при изменениях в Bitrix24 необходимо:

1. Развернуть приложение на сервере с публичным IP или использовать ngrok для локальной разработки
2. Зарегистрировать обработчик вебхуков через API приложения:

```bash
# Для production
curl -X POST "http://your-server.com:8080/api/v1/webhooks/register?handler_base_url=http://your-server.com:8080"

# Для локальной разработки с ngrok
ngrok http 8080
# Используйте полученный URL
curl -X POST "http://localhost:8080/api/v1/webhooks/register?handler_base_url=https://your-id.ngrok.io"
```

## Генерация JWT ключей для Supabase (опционально)

Если вам нужно сгенерировать собственные JWT ключи вместо дефолтных:

### Использование онлайн генератора

Перейдите на https://jwt.io и создайте токены с следующими payload:

**Anon Key:**
```json
{
  "iss": "supabase",
  "ref": "localhost",
  "role": "anon",
  "iat": 1641769200,
  "exp": 1957345200
}
```

**Service Role Key:**
```json
{
  "iss": "supabase",
  "ref": "localhost",
  "role": "service_role",
  "iat": 1641769200,
  "exp": 1957345200
}
```

Используйте ваш `JWT_SECRET` как секретный ключ для подписи.

### Использование скрипта

Создайте файл `generate-jwt.js`:

```javascript
const jwt = require('jsonwebtoken');
const crypto = require('crypto');

// Ваш JWT_SECRET
const JWT_SECRET = process.env.JWT_SECRET || crypto.randomBytes(32).toString('base64');

const anonKey = jwt.sign(
  {
    iss: 'supabase',
    ref: 'localhost',
    role: 'anon',
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + (10 * 365 * 24 * 60 * 60) // 10 years
  },
  JWT_SECRET
);

const serviceKey = jwt.sign(
  {
    iss: 'supabase',
    ref: 'localhost',
    role: 'service_role',
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + (10 * 365 * 24 * 60 * 60)
  },
  JWT_SECRET
);

console.log('JWT_SECRET:', JWT_SECRET);
console.log('\nSUPABASE_ANON_KEY:', anonKey);
console.log('\nSUPABASE_SERVICE_ROLE_KEY:', serviceKey);
```

Запустите:
```bash
node generate-jwt.js
```

## Запуск приложения

### Первый запуск

```bash
# 1. Убедитесь, что .env настроен
cat .env

# 2. Запустите сервисы
docker compose up -d

# 3. Следите за логами при первом запуске
docker compose logs -f backend

# Вы должны увидеть:
# ✓ Waiting for PostgreSQL...
# ✓ PostgreSQL is ready!
# ✓ Running database migrations...
# ✓ Migrations completed successfully!
# ✓ Starting application...

# 4. Проверьте статус
curl http://localhost:8080/health
```

### ⚠️ ВАЖНО: Разница между restart и up

**`docker compose restart`** - НЕ применяет миграции автоматически
```bash
docker compose restart  # ❌ Только перезапускает, entrypoint не выполняется
```

**`docker compose up -d`** - применяет миграции автоматически
```bash
docker compose up -d  # ✅ Пересоздает контейнеры, миграции применяются
```

**После изменения кода или миграций:**
```bash
# Пересоздать только backend (миграции применятся автоматически)
docker compose up -d --force-recreate --build backend

# Или применить миграции вручную
docker compose exec backend alembic upgrade head
```

### Проверка миграций

```bash
# Проверить, какие миграции применены
docker-compose exec backend alembic current

# Посмотреть историю миграций
docker-compose exec backend alembic history

# Просмотр таблиц в БД
docker-compose exec db psql -U postgres -d postgres -c "\dt"
```

## Автоматическое применение миграций

### Как это работает

При каждом запуске контейнера backend:

1. **Скрипт entrypoint.sh** проверяет готовность PostgreSQL
2. **Alembic** автоматически применяет все новые миграции
3. **Приложение** запускается после успешного применения миграций

### Структура миграций

```
backend/
├── alembic/
│   ├── env.py                              # Async конфигурация
│   └── versions/
│       └── 001_create_system_tables.py     # Начальная миграция
├── alembic.ini                             # Настройки Alembic
└── entrypoint.sh                           # Скрипт автозапуска миграций
```

### Создание новой миграции

```bash
# Автоматическая генерация на основе изменений моделей
docker-compose exec backend alembic revision --autogenerate -m "add new column"

# Ручное создание миграции
docker-compose exec backend alembic revision -m "custom migration"
```

### Откат миграции

```bash
# Откатить последнюю миграцию
docker-compose exec backend alembic downgrade -1

# Откатить до конкретной ревизии
docker-compose exec backend alembic downgrade <revision_id>

# Откатить все миграции
docker-compose exec backend alembic downgrade base
```

## Устранение проблем

### База данных не готова

Если backend не может подключиться к БД:

```bash
# Проверить статус PostgreSQL
docker-compose ps db

# Проверить логи БД
docker-compose logs db

# Проверить готовность вручную
docker-compose exec db pg_isready -U postgres
```

### Миграции не применяются

```bash
# Проверить логи backend
docker-compose logs backend | grep -i migration

# Применить миграции вручную
docker-compose exec backend alembic upgrade head

# Проверить текущую версию схемы
docker-compose exec backend alembic current
```

### Проблемы с правами доступа

```bash
# Проверить владельца файлов
ls -la backend/

# Если нужно, пересоздать контейнер
docker-compose down
docker-compose up -d --build
```

### Полная переустановка

Если что-то пошло не так и нужно начать с чистого листа:

```bash
# ВНИМАНИЕ: Это удалит ВСЕ данные!
docker-compose down -v
docker-compose up -d

# Проверить применение миграций
docker-compose logs -f backend
```

## Дополнительные настройки

### Настройка SMTP для уведомлений

Добавьте в `.env`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
SMTP_ADMIN_EMAIL=admin@example.com
```

### Настройка расписания синхронизации

После запуска настройте интервал синхронизации через API:

```bash
# Синхронизация сделок каждые 15 минут
curl -X PUT http://localhost:8080/api/v1/sync/config \
  -H "Content-Type: application/json" \
  -d '{
    "entity_type": "deal",
    "enabled": true,
    "sync_interval_minutes": 15,
    "webhook_enabled": true
  }'
```

## Полезные команды

```bash
# Просмотр всех контейнеров
docker-compose ps

# Остановка всех сервисов
docker-compose stop

# Перезапуск конкретного сервиса
docker-compose restart backend

# Просмотр логов с фильтрацией
docker-compose logs backend | grep ERROR

# Подключение к базе данных
docker-compose exec db psql -U postgres -d postgres

# Выполнение команд в контейнере backend
docker-compose exec backend bash

# Очистка неиспользуемых образов
docker system prune -a
```
