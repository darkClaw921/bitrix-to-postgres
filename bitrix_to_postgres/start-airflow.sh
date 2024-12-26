#!/bin/bash

# Создаем необходимые директории
mkdir -p ./dags ./logs ./plugins

# Устанавливаем переменные окружения
export AIRFLOW_UID=$(id -u)
export AIRFLOW_GID=0

# Проверяем права доступа
echo "Проверка прав доступа:"
ls -la ./dags
ls -la ./logs
ls -la ./plugins

# Запускаем Airflow
# docker-compose -f docker-compose-airflow.yml up -d 