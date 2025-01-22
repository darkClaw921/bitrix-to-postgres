from datetime import datetime,timedelta
from pprint import pprint
from workBitrix1 import get_all_event, get_all_task, get_comment_task, bit
from workPostgres1 import get_record, update_record, insert_record
import asyncio
from tqdm import tqdm

async def get_last_update_date(table_name: str) -> datetime:
    """Получение даты последнего обновления таблицы"""
    record = await get_record('date_update', f"{table_name}_latest")
    if record and hasattr(record, 'date_update'):
        #преобразуем строку в datetime
        return datetime.strptime(record.date_update, '%Y-%m-%d %H:%M:%S.%f')
    return datetime(2023, 1, 1)  # Если нет записи, возвращаем начальную дату

async def update_events():
    """Инкрементное обновление таблицы event_fields"""
    print('начали update_events')
    last_update = await get_last_update_date('event_fields')
    # last_update=datetime.now()-timedelta(days=400)
    print(f'{last_update=}')
    events = await get_all_event(last_update=last_update)
    print(f'{len(events)=}')
    last_event_id=0
    for event in tqdm(events):
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

# async def get_last_update_date(table_name: str) -> datetime:
#     """Получение даты последнего обновления таблицы"""
#     record = await get_record('date_update', f"{table_name}_latest")
#     print(f'{record=}')
#     if record :
#         return record.date_update
#     return datetime(2023, 1, 1)  # Если нет записи, возвращаем начальную дату


async def update_tasks():
    """Инкрементное обновление таблицы task_fields"""
    last_update = await get_last_update_date('task_fields')
    tasks = await get_all_task(last_update=last_update)
    for task in tasks:
        existing_record = await get_record('task_fields', str(task['id']))
        if existing_record:
            await update_record('task_fields', task)
        else:
            await insert_record('task_fields', task)



async def get_task_comments_batc(tasks:list):
    """Инкрементное обновление таблицы task_batches"""
    #
    last_update = await get_last_update_date('task_fields')
    # пакетно получаем комментарии к задачам по 50 задач
    tasks=await get_all_task(last_update=last_update)
    
    i=0
    commands={}
    results={}
    for task in tqdm(tasks, 'получение комментариев'):
        i+=1
        if i>48:
            results.update(await bit.call_batch ({
                'halt': 0,
                'cmd': commands
            }))

            commands={}
            i=0
        commands[f'{task["id"]}']=f'task.commentitem.getlist?taskId={task["id"]}'
        
    # print(len(results))
    return results

async def update_task_comments():
    """Инкрементное обновление таблицы task_comment_fields"""
    
    task_and_comments=await get_task_comments_batc([])
    
    for task_id, task_comments in task_and_comments.items():
        for task_comment in tqdm(task_comments, 'обработка комментариев'):
            task_comment={
                # 'id':task.get('id'),
                'task_id':task_id,
                'bitrix_id':task_comment.get('ID'),
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


async def get_result_task_comments():
    """Получение результатов задач"""
    last_update = await get_last_update_date('task_fields')
    tasks=await get_all_task(last_update=last_update)
    i=0
    commands={}
    results={}
    for task in tqdm(tasks, 'получение комментариев'):
        i+=1
        if i>48:
            results.update(await bit.call_batch ({
                'halt': 0,
                'cmd': commands
            }))

            commands={}
            i=0

        commands[f'{task["id"]}']=f'tasks.task.result.list?taskId={task["id"]}'
    
    # pprint(results)
    return results


async def update_task_results():
    """Инкрементное обновление таблицы task_result_fields"""
    task_results=await get_result_task_comments()

    pprint(task_results)
    for taskID, task_results in tqdm(task_results.items(), 'обработка результатов задач'):
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
last_update = asyncio.run(get_last_update_date('task_fields'))
print(f'{last_update=}')
# asyncio.run(update_date_update())
