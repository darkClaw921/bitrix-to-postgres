#!/bin/bash

# Максимальный размер всех логов (200MB в байтах)
MAX_SIZE=209715200

# Путь к директории с логами
LOG_DIR="/opt/airflow/logs"

# Получаем текущий размер логов
CURRENT_SIZE=$(du -sb "$LOG_DIR" | cut -f1)

# Если текущий размер превышает максимальный
if [ "$CURRENT_SIZE" -gt "$MAX_SIZE" ]; then
    # Удаляем старые файлы логов, оставляя самые новые
    find "$LOG_DIR" -type f -name "*.log" -o -name "*.log.*" | \
    sort -r | \
    while read file; do
        CURRENT_SIZE=$(du -sb "$LOG_DIR" | cut -f1)
        if [ "$CURRENT_SIZE" -gt "$MAX_SIZE" ]; then
            rm "$file"
        else
            break
        fi
    done
fi 