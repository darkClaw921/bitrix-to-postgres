from datetime import datetime, timedelta
from pprint import pprint
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
import sys
import os
import asyncio
from pathlib import Path

# Импортируем локальные модули из той же папки dags
import workBitrix1 as bit
from workPostgres1 import (
    insert_record, update_record, get_record,
    create_table_from_fields
)

# Параметры DAG по умолчанию
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Создаем DAG
dag = DAG(
    'update_bitrix_tables',
    default_args=default_args,
    description='Обновление таблиц Bitrix каждые 15 минут',
    schedule_interval='*/15 * * * *',
    start_date=datetime(2023, 12, 1),
    catchup=False,
    tags=['bitrix'],
)

async def update_history_move_deal():
    # """Обновление таблицы history_move_deal"""
    client = bit
    deals = await client.get_history_move_deal()
    for deal in deals:
        existing_record = await get_record('history_move_deal', deal['ID'])
        if existing_record:
            await update_record('history_move_deal', deal)
        else:
            await insert_record('history_move_deal', deal)

async def update_history_move_lead():
    """Обновление таблицы history_move_lead"""
    leads = await bit.get_history_move_lead()
    for lead in leads:
        existing_record = await get_record('history_move_lead', lead['ID'])
        if existing_record:
            await update_record('history_move_lead', lead)
        else:
            await insert_record('history_move_lead', lead)

async def update_department():
    """Обновление таблицы department"""
    departments = await bit.get_all_department()
    for dept in departments:
        existing_record = await get_record('department', dept['ID'])
        if existing_record:
            await update_record('department', dept)
        else:
            await insert_record('department', dept)

async def update_category():
    """Обновление таблицы category"""
    categories = await bit.get_all_category()
    for category in categories:
        existing_record = await get_record('category', str(category['id']))
        if existing_record:
            await update_record('category', category)
        else:
            await insert_record('category', category)

async def update_status():
    """Обновление таблицы status"""
    statuses = await bit.get_all_status()
    for status in statuses:
        existing_record = await get_record('status', str(status['ID']))
        if existing_record:
            await update_record('status', status)
        else:
            await insert_record('status', status)

async def update_token():
    """Обновление таблицы token"""
    tokens = [bit.WEBHOOK]
    for token in tokens:
        existing_record = await get_record('token', '1')
        
        if existing_record:
            existing_record={
                'token':token,
                'bitrix_id':'1',
            }
            await update_record('token', existing_record)
        else:
            existing_record={
                'token':token,
                'bitrix_id':'1',
            }
            await insert_record('token', existing_record)

async def update_call_fields():
    """Обновление таблицы call_fields"""
    calls = await bit.get_all_call()
    for call in calls:
        existing_record = await get_record('call_fields', call['ID'])
        if existing_record:
            await update_record('call_fields', call)
        else:
            await insert_record('call_fields', call)

async def update_date_update():
    """Обновление таблицы date_update"""
    tables = [
        'history_move_deal',
        'history_move_lead',
        'department',
        'category',
        'status',
        'token',
        'call_fields'
    ]
    
    for table in tables:
        update_info = {
            'ID': f"{table}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'table_name': table,
            'last_update': datetime.now(),
            'status': 'success'
        }
        await insert_record('date_update', update_info)

def run_async(func):
    """Обертка для запуска асинхронных функций"""
    asyncio.run(func())

# Создаем операторы для каждой задачи
tasks = []
for task_func, task_id in [
    (update_history_move_deal, 'update_history_move_deal'),
    (update_history_move_lead, 'update_history_move_lead'),
    (update_department, 'update_department'),
    (update_category, 'update_category'),
    (update_status, 'update_status'),
    (update_token, 'update_token'),
    (update_call_fields, 'update_call_fields'),
]:
    task = PythonOperator(
        task_id=task_id,
        python_callable=lambda f=task_func: run_async(f),
        dag=dag,
    )
    tasks.append(task)

# Создаем задачу обновления дат
update_date_update_task = PythonOperator(
    task_id='update_date_update',
    python_callable=lambda: run_async(update_date_update),
    dag=dag,
)

# Определяем порядок выполнения задач
tasks >> update_date_update_task