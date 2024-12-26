#!/bin/bash

set -x  # Включаем режим отладки

echo "=== Текущий пользователь ==="
id
whoami

# Создаем необходимые директории
echo "=== Создание директорий ==="
mkdir -p ./dags ./logs ./plugins
mkdir -p ./logs/scheduler ./logs/dag_processor ./logs/webserver ./logs/worker

# Устанавливаем переменные окружения
export AIRFLOW_UID=$(id -u)
export AIRFLOW_GID=0

echo "=== Переменные окружения ==="
echo "AIRFLOW_UID: $AIRFLOW_UID"
echo "AIRFLOW_GID: $AIRFLOW_GID"
echo "PWD: $(pwd)"

echo "=== Проверка прав доступа на директории ==="
ls -la .
echo "=== Содержимое и права /opt/airflow ==="
ls -la /opt/airflow/
echo "=== Содержимое и права /opt/airflow/logs ==="
ls -la /opt/airflow/logs/
echo "=== Содержимое и права /opt/airflow/dags ==="
ls -la /opt/airflow/dags/
echo "=== Содержимое и права /opt/airflow/plugins ==="
ls -la /opt/airflow/plugins/

# Проверяем возможность записи
echo "=== Тест записи в директории ==="
touch ./logs/test.txt 2>&1 || echo "Ошибка записи в ./logs"
touch ./dags/test.txt 2>&1 || echo "Ошибка записи в ./dags"
touch ./plugins/test.txt 2>&1 || echo "Ошибка записи в ./plugins"

# Запускаем Airflow
# docker-compose -f docker-compose-airflow.yml up -d 