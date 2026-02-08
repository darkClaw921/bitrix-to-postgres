# История движения сделок и лидов по стадиям (Stage History)

## Обзор

Функциональность синхронизации истории движения сделок и лидов по стадиям/статусам из Bitrix24 CRM. Эта функция позволяет отслеживать, как элементы CRM перемещаются по воронке продаж с временными метками каждого перехода.

## Возможности

- **Полная синхронизация (Full Sync)**: Получение всей истории движения по стадиям
- **Инкрементальная синхронизация**: Получение только новых записей истории с момента последней синхронизации
- **Две отдельные таблицы**:
  - `stage_history_deals` - для сделок
  - `stage_history_leads` - для лидов
- **Поддержка различных типов событий**:
  - Создание элемента (TYPE_ID=1)
  - Переход на промежуточную стадию (TYPE_ID=2)
  - Переход на финальную стадию (TYPE_ID=3)
  - Смена воронки (TYPE_ID=5)

## API Эндпоинты

### Запуск синхронизации истории сделок

```bash
# Полная синхронизация
POST /api/v1/sync/start/stage_history_deal?sync_type=full

# Инкрементальная синхронизация
POST /api/v1/sync/start/stage_history_deal?sync_type=incremental
```

### Запуск синхронизации истории лидов

```bash
# Полная синхронизация
POST /api/v1/sync/start/stage_history_lead?sync_type=full

# Инкрементальная синхронизация
POST /api/v1/sync/start/stage_history_lead?sync_type=incremental
```

### Проверка статуса синхронизации

```bash
GET /api/v1/sync/status
```

Ответ будет включать информацию о синхронизации stage_history:
```json
{
  "stage_history_deal": {
    "last_sync": "2026-02-08T10:00:00",
    "total_records": 5432,
    "status": "completed"
  },
  "stage_history_lead": {
    "last_sync": "2026-02-08T10:05:00",
    "total_records": 2156,
    "status": "completed"
  }
}
```

## Структура данных

### Поля таблицы stage_history_deals

| Поле | Тип | Описание |
|------|-----|----------|
| `record_id` | BIGINT (PK) | Внутренний ID записи |
| `bitrix_id` | VARCHAR(50) | ID записи истории в Bitrix24 (уникальный) |
| `history_id` | VARCHAR(50) | Дубликат bitrix_id для удобства |
| `type_id` | INTEGER | Тип события (1/2/3/5) |
| `owner_id` | VARCHAR(50) | ID сделки (связь с crm_deals) |
| `created_time` | TIMESTAMP | Время перехода |
| `category_id` | VARCHAR(50) | ID воронки |
| `stage_id` | VARCHAR(50) | ID стадии |
| `stage_semantic_id` | VARCHAR(10) | P/S/F (промежуточная/успешная/провальная) |
| `created_at` | TIMESTAMP | Время создания записи в БД |
| `updated_at` | TIMESTAMP | Время обновления записи в БД |

### Поля таблицы stage_history_leads

| Поле | Тип | Описание |
|------|-----|----------|
| `record_id` | BIGINT (PK) | Внутренний ID записи |
| `bitrix_id` | VARCHAR(50) | ID записи истории в Bitrix24 (уникальный) |
| `history_id` | VARCHAR(50) | Дубликат bitrix_id для удобства |
| `type_id` | INTEGER | Тип события (1/2/3/5) |
| `owner_id` | VARCHAR(50) | ID лида (связь с crm_leads) |
| `created_time` | TIMESTAMP | Время перехода |
| `status_id` | VARCHAR(50) | ID статуса |
| `status_semantic_id` | VARCHAR(10) | P/S/F (промежуточная/успешная/провальная) |
| `created_at` | TIMESTAMP | Время создания записи в БД |
| `updated_at` | TIMESTAMP | Время обновления записи в БД |

## Примеры SQL-запросов

### Получить историю движения конкретной сделки

```sql
SELECT
    bitrix_id,
    type_id,
    stage_id,
    stage_semantic_id,
    created_time
FROM stage_history_deals
WHERE owner_id = '123'
ORDER BY created_time ASC;
```

### Средняя скорость прохождения воронки

```sql
SELECT
    d.id,
    d.title,
    MIN(sh.created_time) as first_stage,
    MAX(sh.created_time) as last_stage,
    EXTRACT(EPOCH FROM (MAX(sh.created_time) - MIN(sh.created_time))) / 86400 as days_in_funnel
FROM crm_deals d
JOIN stage_history_deals sh ON d.id = sh.owner_id
WHERE sh.type_id IN (2, 3)
GROUP BY d.id, d.title
ORDER BY days_in_funnel DESC;
```

### Анализ конверсии по стадиям

```sql
SELECT
    stage_id,
    COUNT(*) as total_transitions,
    COUNT(DISTINCT owner_id) as unique_deals,
    COUNT(CASE WHEN stage_semantic_id = 'S' THEN 1 END) as success_count,
    COUNT(CASE WHEN stage_semantic_id = 'F' THEN 1 END) as failed_count
FROM stage_history_deals
WHERE created_time >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY stage_id
ORDER BY total_transitions DESC;
```

### Количество переходов между стадиями

```sql
WITH stage_transitions AS (
    SELECT
        owner_id,
        stage_id as from_stage,
        LEAD(stage_id) OVER (PARTITION BY owner_id ORDER BY created_time) as to_stage,
        created_time
    FROM stage_history_deals
    WHERE type_id IN (2, 3)
)
SELECT
    from_stage,
    to_stage,
    COUNT(*) as transition_count
FROM stage_transitions
WHERE to_stage IS NOT NULL
GROUP BY from_stage, to_stage
ORDER BY transition_count DESC
LIMIT 20;
```

### Время на каждой стадии

```sql
WITH stage_durations AS (
    SELECT
        owner_id,
        stage_id,
        created_time as entered_at,
        LEAD(created_time) OVER (PARTITION BY owner_id ORDER BY created_time) as exited_at
    FROM stage_history_deals
    WHERE type_id IN (2, 3)
)
SELECT
    stage_id,
    COUNT(*) as times_visited,
    AVG(EXTRACT(EPOCH FROM (exited_at - entered_at)) / 3600) as avg_hours_in_stage,
    MIN(EXTRACT(EPOCH FROM (exited_at - entered_at)) / 3600) as min_hours_in_stage,
    MAX(EXTRACT(EPOCH FROM (exited_at - entered_at)) / 3600) as max_hours_in_stage
FROM stage_durations
WHERE exited_at IS NOT NULL
GROUP BY stage_id
ORDER BY avg_hours_in_stage DESC;
```

## Технические детали

- **Метод API**: `crm.stagehistory.list`
- **Пагинация**: Автоматическая через `get_all()` (встроенный механизм fast-bitrix24)
- **Идентификатор типа**:
  - `entityTypeId=2` для сделок
  - `entityTypeId=1` для лидов
- **Уникальный ключ**: Поле `ID` из Bitrix24 → `bitrix_id` в БД

## Ограничения

1. **Только история переходов**: Stage history не содержит данных о самих сделках/лидах, только о переходах между стадиями
2. **Нет webhooks**: Bitrix24 не предоставляет прямых webhooks для stage history. Можно использовать `onCrmDealUpdate`/`onCrmLeadUpdate` как триггер
3. **Нет пользовательских полей**: Stage history не поддерживает UF_* поля
4. **Разные поля для разных типов**:
   - Сделки используют `stage_id`, `stage_semantic_id`, `category_id`
   - Лиды используют `status_id`, `status_semantic_id`
5. **Большой объем данных**: В активных CRM системах может накапливаться очень много записей истории

## Рекомендации

1. **Периодичность синхронизации**: 1-2 раза в день достаточно (история редко меняется задним числом)
2. **Инкрементальная синхронизация**: Используйте incremental sync для оптимизации
3. **Архивация старых данных**: Рассмотрите возможность архивации записей старше 2 лет
4. **Индексы**: Создайте дополнительные индексы на `owner_id` и `created_time` для ускорения запросов:
   ```sql
   CREATE INDEX idx_stage_history_deals_owner ON stage_history_deals(owner_id);
   CREATE INDEX idx_stage_history_deals_created ON stage_history_deals(created_time);
   ```
5. **Связь с основными таблицами**: Всегда синхронизируйте stage_history после обновления сделок/лидов

## Типы событий (TYPE_ID)

| TYPE_ID | Название | Описание |
|---------|----------|----------|
| 1 | Создание | Элемент только что создан |
| 2 | Промежуточная стадия | Переход на промежуточную стадию воронки |
| 3 | Финальная стадия | Переход на финальную стадию (успех или провал) |
| 5 | Смена воронки | Элемент перемещен в другую воронку |

## Semantic ID

| Код | Название | Описание |
|-----|----------|----------|
| P | Process | Промежуточная стадия (в работе) |
| S | Success | Успешное завершение |
| F | Fail | Провальное завершение |

## Использование в дашбордах

Примеры чартов, которые можно создать:

1. **Воронка продаж**: Количество сделок на каждой стадии
2. **Скорость движения**: Среднее время от создания до закрытия
3. **Конверсия между стадиями**: Процент перехода со стадии на стадию
4. **Хронология**: Timeline движения конкретной сделки
5. **Анализ потерь**: На каких стадиях чаще всего проваливаются сделки
6. **Активность**: Количество переходов по дням/неделям

## Troubleshooting

### Синхронизация не запускается

Проверьте логи сервиса:
```bash
docker logs bitrix-sync-backend
```

### Пустая таблица после синхронизации

1. Проверьте, что в Bitrix24 есть история движения сделок/лидов
2. Убедитесь, что webhook URL правильный и имеет доступ к методу `crm.stagehistory.list`
3. Проверьте логи синхронизации через API: `GET /api/v1/sync/status`

### Дублирование записей

Stage history использует поле `ID` как уникальный ключ. Дубликаты быть не должны. Если они появляются:
1. Проверьте версию Bitrix24
2. Проверьте логи на ошибки UPSERT
3. Пересоздайте таблицу через full sync

## Дополнительные ресурсы

- [Документация Bitrix24 API: crm.stagehistory.list](https://dev.1c-bitrix.ru/rest_help/crm/stagehistory/crm_stagehistory_list.php)
- [ARCHITECTURE.md](./ARCHITECTURE.md) - полная архитектура системы
- [CHANGELOG.md](./CHANGELOG.md) - история изменений
