# Архитектура проекта

## Общее описание
Проект представляет собой коннектор для передачи данных из Bitrix в ClickHouse. Основная задача - получать данные из Bitrix, преобразовывать их и сохранять в ClickHouse для дальнейшего анализа.

## Структура проекта

### Основные файлы:

- **workClickHouse.py** - модуль для работы с ClickHouse базой данных. Содержит функции для:
  - Создания таблиц
  - Добавления и удаления столбцов
  - Вставки, обновления и удаления записей
  - Получения метаданных таблиц
  - Конвертации типов данных

### Основные функции и их назначение:

#### Функции для работы с таблицами:
- `create_table_move_task_to_history()` - создает таблицу для хранения истории перемещенных задач
- `create_table_from_fields(table_name, fields_list)` - создает таблицу на основе предоставленного списка полей
- `drop_table(table_name)` - удаляет таблицу
- `get_database_structure()` - получает структуру всех таблиц в базе данных

#### Функции для работы со столбцами:
- `add_column_to_table(table_name, column_name, column_type)` - добавляет столбец в таблицу
- `drop_column_from_table(table_name, column_name)` - удаляет столбец из таблицы
- `get_table_column_types(table_name)` - получает информацию о типах столбцов таблицы

#### Функции для работы с данными:
- `insert_record(table_name, data)` - вставляет запись в таблицу
- `update_record(table_name, data)` - обновляет запись в таблице
- `get_record(table_name, bitrix_id)` - получает запись по идентификатору Bitrix
- `delete_record(table_name, bitrix_id)` - удаляет запись из таблицы

#### Вспомогательные функции:
- `convert_value_to_type(value, target_type)` - конвертирует значение в указанный тип
- `prepare_record_for_insert(data, date_fields)` - подготавливает запись для вставки

## Особенности ClickHouse
В отличие от PostgreSQL, ClickHouse имеет некоторые особенности:
- Нет прямой поддержки JSON типа данных - используется String
- Обновления и удаления реализованы через ALTER TABLE и работают относительно медленно
- Для таблиц используется движок MergeTree
- Boolean тип представлен как UInt8 (0/1)

## Подключение к базе данных
Для подключения используются переменные окружения:
- CLICKHOUSE_HOST
- CLICKHOUSE_USERNAME
- CLICKHOUSE_PASSWORD
- CLICKHOUSE_DB 