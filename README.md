# Bitrix to Postgres Connector

Сервис для синхронизации данных между Bitrix24 и PostgreSQL.

## Компоненты
- FastAPI сервис
- Airflow для управления задачами
- PostgreSQL для хранения данных

## Установка и запуск
1. Убедитесь, что у вас установлен Docker и Docker Compose
2. Создайте файл .env с необходимыми переменными окружения
3. Запустите сервисы командой: `docker-compose -f docker-compose-airflow.yml up -d`
