from fastapi import FastAPI, Request
import asyncio
from pprint import pprint
# from workPostgres import save_to_postgres
import workPostgres
import workBitrix
import firstStart
app = FastAPI()

import urllib.parse
#преобразуем строку в словарь с вложенными ключами
def parse_nested_query(query_string):
    # Разбираем строку запроса в список кортежей
    pairs = urllib.parse.parse_qsl(query_string)
    
    # Создаем пустой словарь для результата
    result = {}
    
    for key, value in pairs:
        # Разбиваем ключ на части по квадратным скобкам
        parts = key.replace(']', '').split('[')
        
        # Начинаем с корневого словаря
        current = result
        
        # Проходим по всем частям ключа кроме последней
        for i, part in enumerate(parts[:-1]):
            if part == '':
                continue
                
            # Если текущая часть еще не существует в словаре, создаем новый словарь
            if part not in current:
                current[part] = {}
            
            # Переходим к следующему уровню вложенности
            current = current[part]
            
        # Добавляем значение для последней части ключа
        last_key = parts[-1]
        if last_key in current and isinstance(current[last_key], dict):
            # Если последний ключ уже существует и является словарем,
            # добавляем значение как элемент списка
            if not isinstance(current[last_key], list):
                current[last_key] = [current[last_key]]
            current[last_key].append(value)
        else:
            current[last_key] = value
            
    return result

@app.get("/fist_start_1234radsf")
async def read_root():
    await firstStart.main()
    return {"message": "Hello, World!"}

@app.get("/fist_start_1234radsf2")
async def read_root():
    await firstStart.main2()
    return {"message": "Hello, World!"}

@app.post('/update')
async def update_deal(request: Request):
    body = await request.body()
    body_str = body.decode('utf-8')
    body_dict = parse_nested_query(body_str)
    pprint(body_dict)
    event = body_dict.get('event')
    domain = body_dict.get('auth').get('domain')

    match event:
        case 'ONCRMDEALUPDATE':
            dealID=body_dict.get('data').get('FIELDS').get('ID')
            print(dealID)
# 
            # await workBitrix.update_history_date_for_deal(dealID)
            #test cpmment
            deal=await workBitrix.get_deal(dealID)
            await workPostgres.update_record('deal_fields', deal)
            
        
        case 'ONCRMCOMPANYUPDATE':
            companyID=body_dict.get('data').get('FIELDS').get('ID')
            print(companyID)
            company=await workBitrix.get_company(companyID)
            await workPostgres.update_record('company_fields', company)

        case 'ONCRMCONTACTUPDATE':
            contactID=body_dict.get('data').get('FIELDS').get('ID')
            print(contactID)
            contact=await workBitrix.get_contact(contactID)
            await workPostgres.update_record('contact_fields', contact)

        case 'ONCRMLEADUPDATE':
            leadID=body_dict.get('data').get('FIELDS').get('ID')
            print(leadID)
            lead=await workBitrix.get_lead(leadID)
            await workPostgres.update_record('lead_fields', lead)

        case 'ONCRMDYNAMICITEMUPDATE':
            dynamicItemID=body_dict.get('data').get('FIELDS').get('ID')
            entityTypeId=body_dict.get('data').get('FIELDS').get('ENTITY_TYPE_ID')
            print(dynamicItemID, entityTypeId)
            dynamicItem=await workBitrix.get_dynamic_item_entity(entityTypeId, dynamicItemID)
            await workPostgres.update_record(f'dynamic_item_fields_{entityTypeId}', dynamicItem)

        case 'ONCRMREQUISITEUSERFIELDUPDATE':
            userFieldID=body_dict.get('data').get('FIELDS').get('ID')
            entityID=body_dict.get('data').get('FIELDS').get('ENTITY_ID')
            fieldID=body_dict.get('data').get('FIELDS').get('FIELD_ID')
            print(userFieldID, entityID, fieldID)
            userField=await workBitrix.get_userfield(userFieldID)
            await workPostgres.add_column_to_table('requisite_userfield_fields', userField)


        case 'ONTASKUPDATE':
            try:
                taskID=body_dict.get('data').get('FIELDS_BEFORE').get('ID')
                print(taskID)
            except:
                taskID=body_dict.get('data').get('FIELDS_AFTER').get('ID')
                print(taskID)
            task=await workBitrix.get_task(taskID)
            # pprint(task)
            record=await workPostgres.get_record('task_fields', taskID)
            pprint(record)
            if task.get('deadline') != record.deadline:
                await workPostgres.insert_record('move_task_to_history', task)
            await workPostgres.update_record('task_fields', task)


        case 'ONCALENDARENTRYUPDATE':
            eventID=body_dict.get('data').get('id')
            print(eventID)
            event=await workBitrix.get_event(eventID)
            await workPostgres.update_record('event_fields', event)

        case _:
            print('unknown event')
    # Сохранение данных в Postgres
    # save_to_postgres('deal_updated', body_dict['deal'])
    
    return {"status": "ok"}

@app.post('/create')
async def create_deal(request: Request):
    body = await request.body()
    body_str = body.decode('utf-8')
    body_dict = parse_nested_query(body_str)
    pprint(body_dict)

    domain = body_dict.get('auth').get('domain')
    print(domain)

    event = body_dict.get('event')

    match event:
        case 'ONCRMDEALADD':
            dealID=body_dict.get('data').get('FIELDS').get('ID')
            print(dealID)
            deal=await workBitrix.get_deal(dealID)
            await workPostgres.insert_record('deal_fields', deal)
            
        case 'ONCRMCOMPANYADD':
            companyID=body_dict.get('data').get('FIELDS').get('ID')
            print(companyID)
            company=await workBitrix.get_company(companyID)
            await workPostgres.insert_record('company_fields', company)

        case 'ONCRMCONTACTADD':
            contactID=body_dict.get('data').get('FIELDS').get('ID')
            print(contactID)
            contact=await workBitrix.get_contact(contactID)
            await workPostgres.insert_record('contact_fields', contact) 

        case 'ONCRMLEADADD':
            leadID=body_dict.get('data').get('FIELDS').get('ID')
            print(leadID)
            lead=await workBitrix.get_lead(leadID)
            await workPostgres.insert_record('lead_fields', lead)

        case 'ONCRMDYNAMICITEMADD':
            dynamicItemID=body_dict.get('data').get('FIELDS').get('ID')
            entityTypeId=body_dict.get('data').get('FIELDS').get('ENTITY_TYPE_ID')
            print(dynamicItemID, entityTypeId)
            dynamicItem=await workBitrix.get_dynamic_item_entity(entityTypeId, dynamicItemID)
            await workPostgres.insert_record(f'dynamic_item_fields_{entityTypeId}', dynamicItem)
        
        case 'ONCRMREQUISITEUSERFIELDADD':
            userFieldID=body_dict.get('data').get('FIELDS').get('ID')
            entityID=body_dict.get('data').get('FIELDS').get('ENTITY_ID')
            fieldID=body_dict.get('data').get('FIELDS').get('FIELD_ID')
            print(userFieldID, entityID, fieldID)
            userField=await workBitrix.get_userfield(userFieldID)
            await workPostgres.add_column_to_table('requisite_userfield_fields', userField)


        case 'ONTASKADD':
            try:
                taskID=body_dict.get('data').get('FIELDS_BEFORE').get('ID')
                print(taskID)
            except:
                taskID=body_dict.get('data').get('FIELDS_AFTER').get('ID')
                print(taskID)

            task=await workBitrix.get_task(taskID)
            await workPostgres.insert_record('task_fields', task)

        case 'ONCALENDARENTRYADD':
            eventID=body_dict.get('data').get('id')
            print(eventID)
            event=await workBitrix.get_event(eventID)
            await workPostgres.insert_record('event_fields', event)
        case _:
            print('unknown event')
    
    # Сохранение данных в Postgres
    # save_to_postgres('deal_created', body_dict['deal'])
    
    return {"status": "ok"}

@app.post('/delete')
async def delete_deal(request: Request):
    body = await request.body() 
    body_str = body.decode('utf-8')
    body_dict = parse_nested_query(body_str)
    pprint(body_dict)

    domain = body_dict.get('auth').get('domain')
    print(domain)

    event = body_dict.get('event')
    match event:
        case 'ONCRMDEALDELETE':
            dealID=body_dict.get('data').get('FIELDS').get('ID')
            print(dealID)
            await workPostgres.delete_record('deal_fields', dealID)
            
        case 'ONCRMCOMPANYDELETE':
            companyID=body_dict.get('data').get('FIELDS').get('ID')
            print(companyID)
            await workPostgres.delete_record('company_fields', companyID)

        case 'ONCRMCONTACTDELETE':
            contactID=body_dict.get('data').get('FIELDS').get('ID')
            print(contactID)
            await workPostgres.delete_record('contact_fields', contactID)

        case 'ONCRMLEADDELETE':
            leadID=body_dict.get('data').get('FIELDS').get('ID')
            print(leadID)
            await workPostgres.delete_record('lead_fields', leadID)

        case 'ONCRMDYNAMICITEMDELETE':
            dynamicItemID=body_dict.get('data').get('FIELDS').get('ID')
            entityTypeId=body_dict.get('data').get('FIELDS').get('ENTITY_TYPE_ID')
            print(dynamicItemID, entityTypeId)
            await workPostgres.delete_record(f'dynamic_item_fields_{entityTypeId}', dynamicItemID)

        case 'ONTASKDELETE':
            try:
                taskID=body_dict.get('data').get('FIELDS_BEFORE').get('ID')
                print(taskID)
            except:
                taskID=body_dict.get('data').get('FIELDS_AFTER').get('ID')
                print(taskID)
            await workPostgres.delete_record('task_fields', taskID)

        case 'ONCALENDARENTRYDELETE':
            eventID=body_dict.get('data').get('id')
            print(eventID)
            await workPostgres.delete_record('event_fields', eventID)


        case _:
            print('unknown event')

    # Сохранение данных в Postgres
    # save_to_postgres('deal_deleted', body_dict['deal'])
    
    return {"status": "ok"}



@app.post('/create_table_history')
async def create_table_history(request: Request):
    await workPostgres.create_table_move_task_to_history()
    return {"status": "ok"}

@app.post('/add_field')
async def add_field(request: Request):
    body = await request.body()
    body_str = body.decode('utf-8')
    body_dict = parse_nested_query(body_str)
    pprint(body_dict) 
    return {"status": "ok"}

@app.post('/call')
async def handle_call_event(request: Request):
    body = await request.body()
    body_str = body.decode('utf-8')
    body_dict = parse_nested_query(body_str)
    pprint(body_dict)

    domain = body_dict.get('auth').get('domain')
    print(domain)

    event = body_dict.get('event')
    match event:
        case 'ONCRMCALLADD':
            callID = body_dict.get('data').get('FIELDS').get('ID')
            print(callID)
            call = await workBitrix.get_call(callID)
            await workPostgres.insert_record('call_fields', call)

        case 'ONCRMCALLUPDATE':
            callID = body_dict.get('data').get('FIELDS').get('ID')
            print(callID)
            call = await workBitrix.get_call(callID)
            await workPostgres.update_record('call_fields', call)

        case 'ONCRMCALLDELETE':
            callID = body_dict.get('data').get('FIELDS').get('ID')
            print(callID)
            await workPostgres.delete_record('call_fields', callID)

        case _:
            print('unknown call event')

    return {"status": "ok"}

async def test():
    taskID=28885
    task=await workBitrix.get_task(taskID)
    # pprint(task)
    # record=await workPostgres.get_record('task_fields', taskID)
    # pprint(record)
    await workPostgres.insert_record('move_task_to_history', task)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8009)
    # asyncio.run(test())