from datetime import datetime, timedelta
from pprint import pprint
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
import sys
import os
import asyncio
from pathlib import Path

# # Добавляем путь к директории scripts в PYTHONPATH
# scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts'))
# sys.path.append(scripts_dir)

# Импортируем модули из scripts
import scripts.workBitrix1_2 as bit
from scripts.workPostgres1_2 import (
    insert_record, update_record, get_record,
    create_table_from_fields
)

# Параметры DAG по умолчанию
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=1),
    'retry_exponential_backoff': True,
    'max_retry_delay': timedelta(minutes=13),
}

# Создаем DAG
dag = DAG(
    'update_bitrix_tables_2',
    default_args=default_args,
    description='Обновление таблиц Bitrix каждый час в 00 минут',
    schedule='0 * * * *',
    start_date=datetime(2023, 12, 1),
    catchup=False,
    tags=['bitrix'],
    max_active_runs=1,
    max_active_tasks=8
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

async def update_user():
    """Обновление таблицы user"""
    users = await bit.get_all_user()
    # users=users['order0000000000']
    for user in users:
        existing_record = await get_record('user_fields', str(user['ID']))
        if existing_record:
            await update_record('user_fields', user)
        else:
            await insert_record('user_fields', user)

async def get_last_update_date(table_name: str) -> datetime:
    """Получение даты последнего обновления таблицы"""
    record = await get_record('date_update', f"{table_name}_latest")
    if record and hasattr(record, 'date_update'):
        #преобразуем строку в datetime
        return datetime.strptime(record.date_update, '%Y-%m-%d %H:%M:%S.%f')
    return datetime(2023, 1, 1)  # Если нет записи, возвращаем начальную дату


async def update_deals():
    """Инкрементное обновление таблицы deal_fields"""
    last_update = await get_last_update_date('deal_fields')
    
    
    deals = await bit.get_all_deal(last_update=last_update)
    for deal in deals:
        existing_record = await get_record('deal_fields', str(deal['ID']))
        if existing_record:
            await update_record('deal_fields', deal)
        else:
            await insert_record('deal_fields', deal)

async def update_companies():
    """Инкрементное обновление таблицы company_fields"""
    last_update = await get_last_update_date('company_fields')

    companies = await bit.get_all_company(last_update=last_update)
    for company in companies:
        existing_record = await get_record('company_fields', str(company['ID']))
        if existing_record:
            await update_record('company_fields', company)
        else:
            await insert_record('company_fields', company)

async def update_contacts():
    """Инкрементное обновление таблицы contact_fields"""
    last_update = await get_last_update_date('contact_fields')
    contacts = await bit.get_all_contact(last_update=last_update)
    for contact in contacts:
        existing_record = await get_record('contact_fields', str(contact['ID']))
        if existing_record:
            await update_record('contact_fields', contact)
        else:
            await insert_record('contact_fields', contact)

async def update_leads():
    """Инкрементное обновление таблицы lead_fields"""
    last_update = await get_last_update_date('lead_fields')
    leads = await bit.get_all_lead(last_update=last_update)
    for lead in leads:
        existing_record = await get_record('lead_fields', str(lead['ID']))
        if existing_record:
            await update_record('lead_fields', lead)
        else:
            await insert_record('lead_fields', lead)

async def update_tasks():
    """Инкрементное обновление таблицы task_fields"""
    last_update = await get_last_update_date('task_fields')
    tasks = await bit.get_all_task(last_update=last_update)
    for task in tasks:
        existing_record = await get_record('task_fields', str(task['id']))
        if existing_record:
            await update_record('task_fields', task)
        else:
            await insert_record('task_fields', task)

async def update_events():
    """Инкрементное обновление таблицы event_fields"""
    print('начали update_events')
    last_update = await get_last_update_date('event_fields')
    # last_update=datetime.now()-timedelta(days=400)
    print(f'{last_update=}')
    events = await bit.get_all_event(last_update=last_update)
    print(f'{len(events)=}')
    last_event_id=0
    for event in events:
        print(f'{event["ID"]=} обработан')
        if last_event_id!=event['ID']:
            last_event_id=event['ID']
        else:
            continue
        existing_record = await get_record('event_fields', str(event['ID']))
        if existing_record:
            await update_record('event_fields', event)
        else:
            await insert_record('event_fields', event)


async def update_task_comments():
    """Инкрементное обновление таблицы task_comment_fields"""
    last_update = await get_last_update_date('task_fields')
    tasks = await bit.get_all_task(last_update=last_update)
    task_comments=await bit.get_task_comments_batc(tasks=tasks)
    for taskID, task_comments in task_comments.items():
        for task_comment in task_comments:
            task_comment={
                'bitrix_id':task_comment.get('ID'),
                'task_id':taskID,
                'author_id':task_comment.get('AUTHOR_ID'),
                'author_name':task_comment.get('AUTHOR_NAME'),
                'post_message':task_comment.get('POST_MESSAGE'),
                'post_date':task_comment.get('POST_DATE'),
                'attached_objects':task_comment.get('ATTACHED_OBJECTS'),
            }
            existing_record = await get_record('task_comment_fields', str(task_comment['bitrix_id']))
            if existing_record:
                await update_record('task_comment_fields', task_comment)
            else:
                await insert_record('task_comment_fields', task_comment)


async def update_task_results():
    """Инкрементное обновление таблицы task_result_fields"""
    last_update = await get_last_update_date('task_fields')
    tasks = await bit.get_all_task(last_update=last_update)
    task_results=await bit.get_result_task_comments(tasks=tasks)

    for taskID, task_results in task_results.items():
        for task_result in task_results:
            task_result={
                'bitrix_id':task_result.get('id'),
                'task_id':taskID,
                'text':task_result.get('text'),
                'createdat':task_result.get('createdAt'),
                'updatedat':task_result.get('updatedAt'),
                'createdby':task_result.get('createdBy'),
                'files':task_result.get('files'),
                'status':task_result.get('status'),
                'commentid':task_result.get('commentId'),
            }
            existing_record = await get_record('task_result_fields', str(task_result['bitrix_id']))
            if existing_record:
                await update_record('task_result_fields', task_result)
            else:
                await insert_record('task_result_fields', task_result)







# async def update_dynamic_items():
#     """Инкрементное обновление таблиц dynamic_item_fields"""
#     dynamic_types = await bit.get_all_dynamic_item()
#     for dynamic_type in dynamic_types:
#         entityTypeId = dynamic_type['entityTypeId']
#         last_update = await get_last_update_date(f'dynamic_item_fields_{entityTypeId}')
#         dynamic_items = await bit.get_dynamic_item_all_entity(entityTypeId,last_update=last_update)
#         for item in dynamic_items:
#             existing_record = await get_record(f'dynamic_item_fields_{entityTypeId}', str(item['id']))
#             if existing_record:
#                 await update_record(f'dynamic_item_fields_{entityTypeId}', item)
#             else:
#                 await insert_record(f'dynamic_item_fields_{entityTypeId}', item)

async def update_date_update():
    """Обновление таблицы date_update"""
    tables = [
        'history_move_deal',
        'history_move_lead',
        'department',
        'category',
        'status',
        'token',
        'call_fields',
        'user_fields',
        'deal_fields',
        'company_fields',
        'contact_fields',
        'lead_fields',
        'task_fields',
        'event_fields',
        'task_comment_fields',
        'task_result_fields'
    ]
    
    for table in tables:
        update_info = {
            'ID': f"{table}_latest",
            'table_name': table,
            'date_update': datetime.now(),
            'status': 'success'
        }
        existing_record = await get_record('date_update', f"{table}_latest")
        if existing_record:
            await update_record('date_update', update_info)
        else:
            await insert_record('date_update', update_info)

    # Добавляем записи для dynamic_item_fields
    # dynamic_types = await bit.get_all_dynamic_item()
    # for dynamic_type in dynamic_types:
    #     entityTypeId = dynamic_type['id']
    #     table_name = f'dynamic_item_fields_{entityTypeId}'
    #     update_info = {
    #         'ID': f"{table_name}_latest",
    #         'table_name': table_name,
    #         'last_update': datetime.now(),
    #         'status': 'success'
    #     }
    #     existing_record = await get_record('date_update', f"{table_name}_latest")
    #     if existing_record:
    #         await update_record('date_update', update_info)
    #     else:
    #         await insert_record('date_update', update_info)

def run_async(func):
    """Запускает асинхронную функцию"""
    try:
        return asyncio.run(func())
    except Exception as e:
        print(f"Ошибка при выполнении {func.__name__}: {str(e)}")
        raise e

# Создаем задачи
update_history_move_deal_task = PythonOperator(
    task_id='update_history_move_deal',
    python_callable=lambda f=update_history_move_deal: run_async(f),
    retries=3,
    retry_delay=timedelta(minutes=1),
    execution_timeout=timedelta(minutes=10),
    dag=dag,
)

# Создаем операторы для каждой задачи
tasks = {
    'update_history_move_lead': update_history_move_lead,
    'update_department': update_department,
    'update_category': update_category,
    'update_status': update_status,
    'update_token': update_token,
    'update_call_fields': update_call_fields,
    'update_user': update_user,
    'update_deals': update_deals,
    'update_companies': update_companies,
    'update_contacts': update_contacts,
    'update_leads': update_leads,
    'update_tasks': update_tasks,
    'update_events': update_events,
    # 'update_dynamic_items': update_dynamic_items,
    'update_date_update': update_date_update,
    'update_task_comments': update_task_comments,
    'update_task_results': update_task_results
}

operators = {}
for task_id, task_func in tasks.items():
    operators[task_id] = PythonOperator(
        task_id=task_id,
        python_callable=lambda f=task_func: run_async(f),
        retries=3,
        retry_delay=timedelta(minutes=1),
        execution_timeout=timedelta(minutes=25),
        dag=dag,
    )

# Устанавливаем зависимости
for task_id in operators:
    if task_id != 'update_date_update':
        operators[task_id] >> operators['update_date_update']
        
# update_events()
# last_update = asyncio.run(update_date_update())
# print(f'{last_update=}')