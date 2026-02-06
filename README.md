
сервис переходи на новую версию, смотри папку new_version

![main](main.png)
# Bitrix to Postgres Connector

Сервис для синхронизации данных между Bitrix24 и PostgreSQL.
получает данные из Bitrix24 и записывает в PostgreSQL
- Сделки
- Лиды
- Контакты
- Комментарии к задачам
- Результаты задач
- События
- Задачи
- Пользователи
- Смарт-процессы
- Справочники
- Подразделения

## права доступа
crm, 

## Компоненты
- FastAPI сервис
- Airflow для управления задачами
- PostgreSQL для хранения данных

## Установка и запуск
1. Убедитесь, что у вас установлен Docker и Docker Compose
2. Создайте файл .env с необходимыми переменными окружения
3. Запустите сервисы командой: `docker-compose -f docker-compose-airflow.yml up -d`
4. Добавьте в crontab команду для запуска скрипта очистки логов: `0 0 * * * /home/user/bitrix-to-postgres/bitrix_to_postgres/cleanup_logs.sh >> /home/user/bitrix-to-postgres/bitrix_to_postgres/cleanup_logs.log 2>&1`
