from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from workPostgres1_2 import create_tables

# Параметры DAG по умолчанию
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}

# Создаем DAG
dag = DAG(
    'create_tables_dag',
    default_args=default_args,
    description='DAG для создания таблиц в базе данных',
    schedule_interval=None,  # Запускается только вручную
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['bitrix', 'init']
)

# Задача для создания таблиц
create_tables_task = PythonOperator(
    task_id='create_tables',
    python_callable=create_tables,
    dag=dag
)

# Определяем порядок выполнения задач
create_tables_task 