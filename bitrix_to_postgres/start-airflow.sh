#!/bin/bash

# Создаем необходимые директории
mkdir -p ./dags ./logs ./plugins

# Устанавливаем переменные окружения
export AIRFLOW_UID=$(id -u)
export AIRFLOW_GID=0

# Запускаем Airflow
# docker-compose -f docker-compose-airflow.yml up -d 