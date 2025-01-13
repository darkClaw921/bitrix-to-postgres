from datetime import datetime,timedelta
from workBitrix1 import get_all_event
from workPostgres1 import get_record, update_record, insert_record
import asyncio
from tqdm import tqdm

async def get_last_update_date(table_name: str) -> datetime:
    """Получение даты последнего обновления таблицы"""
    record = await get_record('date_update', f"{table_name}_latest")
    if record and hasattr(record, 'last_update'):
        return record.last_update
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

async def get_last_update_date(table_name: str) -> datetime:
    """Получение даты последнего обновления таблицы"""
    record = await get_record('date_update', f"{table_name}_latest")
    print(f'{record=}')
    if record :
        return record.created_date
    return datetime(2023, 1, 1)  # Если нет записи, возвращаем начальную дату

a=asyncio.run(get_last_update_date('event_fields'))
print(a)