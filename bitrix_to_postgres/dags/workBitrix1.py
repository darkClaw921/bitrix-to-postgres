from datetime import datetime, timedelta
from pprint import pprint
from fast_bitrix24 import BitrixAsync
from dotenv import load_dotenv

import asyncio

NAME_APP='H_'
import os
load_dotenv()

WEBHOOK=os.getenv('WEBHOOK')
bit = BitrixAsync(WEBHOOK, ssl=False)
print(f'{WEBHOOK=}')

# Работа с Deal
async def get_deal(dealID):
    items={ 
        'ID':dealID,
        'select':['*', 'UF_'],
    }
    deal = await bit.call('crm.deal.get',items=items,raw=True)
    deal=deal['result']
    return deal

async def get_all_userfields_deal()->list:
    items={
        'filter':{
            '>ID':0,
        }
    }
    
    poles=await bit.call('crm.deal.userfield.list',items=items,raw=True)
   
    poles=poles['result']
    # pprint(poles)
    # poles=prepare_userfields_deal_to_postgres(poles)
    # print(poles)
    return poles

async def get_userfields_deal(fieldID)->list:
    items={
        'ID':fieldID,
        
    }
    field=await bit.call('crm.deal.userfield.get',items=items,raw=True)
    field=field['result']
    pprint(field)
    return field

async def get_all_fields_deal()->list:
    items={
        'select':['*', 'UF_'],
    }
    fields=await bit.call('crm.deal.fields',items=items,raw=True)
    fields=fields['result']
    # pprint(fields)
    return fields

def prepare_userfields_deal_to_postgres(fields:list)->list:
    fieldsToPostgres=[]
    for field in fields:
        fieldName=field.get('FIELD_NAME')
        entityID=field.get('ENTITY_ID')
        userTypeID=field.get('USER_TYPE_ID')
        # print(fieldName, entityID, userTypeID)
        
        fieldToPostgres={
            'fieldID':fieldName,
            'entityID':entityID, #Deal
            'fieldType':userTypeID,
            'description':field.get('title'),
        }
        fieldsToPostgres.append(fieldToPostgres)
        
    return fieldsToPostgres

def prepare_fields_deal_to_postgres(fields:list)->list:
    entityID='CRM_DEAL'
    fieldsToPostgres=[]
    for fieldID, meta in fields.items():
        fieldType=meta.get('type')
        fieldsToPostgres.append({
            'fieldID':fieldID,
            'fieldType':fieldType,
            'entityID':entityID,
            'description':meta.get('title'),
        })
    return fieldsToPostgres

async def get_all_deal(last_update=None)->list:
    items={
        'FILTER':{
            '>ID':0,
        },
        'SELECT':['*', 'UF_*'],
    }
    if last_update:
        items['FILTER']['>DATE_MODIFY'] = last_update.strftime('%Y-%m-%dT%H:%M:%S')
    deals = await bit.get_all('crm.deal.list', params=items)
    # deals=await bit.call('crm.deal.list',items=items)
    deals=deals
    return deals

async def get_history_move_deal(last_update=None):
    #https://apidocs.bitrix24.ru/api-reference/crm/crm-stage-history-list.html
    """
    entityTypeId - ID типа сущности
    1 - Lead
    2 - Deal
    5 - Invoice
    """
    items={
        'entityTypeId':'2',
        # 'select':['*', 'UF_*'],
    }
    if last_update:
        items['filter']['>TIMESTAMP_X'] = last_update.strftime('%Y-%m-%dT%H:%M:%S')
    history=await bit.get_all('crm.stagehistory.list',params=items)
    # history=history
    return history



# Работа с Company
async def get_company(companyID):
    items={
        'ID':companyID,
        'select':['*', 'UF_'],
    }
    company=await bit.call('crm.company.get',items=items,raw=True)
    company=company['result']
    return company

async def get_all_fields_company()->list:
    fields=await bit.call('crm.company.fields',raw=True)
    fields=fields['result']
    return fields

async def get_all_userfields_company()->list:
    items={
        'filter':{
            '>ID':0,
        }
    }
    fields=await bit.call('crm.company.userfield.list',items=items,raw=True)
    fields=fields['result']
    return fields   

async def get_userfields_company(fieldID)->list:
    field=await bit.call('crm.company.userfield.get',items={'ID':fieldID},raw=True)
    field=field['result']
    return field

def prepare_userfields_company_to_postgres(fields:list)->list:
    fieldsToPostgres=[]
    for field in fields:
        fieldName=field.get('FIELD_NAME')
        entityID=field.get('ENTITY_ID')
        userTypeID=field.get('USER_TYPE_ID')
        # print(fieldName, entityID, userTypeID)
        fieldToPostgres={
            'fieldID':fieldName,
            'entityID':entityID,
            'fieldType':userTypeID,
            'description':field.get('title'),
        }
        fieldsToPostgres.append(fieldToPostgres)
    return fieldsToPostgres

def prepare_fields_company_to_postgres(fields:list)->list:
    entityID='CRM_COMPANY'
    fieldsToPostgres=[]
    for fieldID, meta in fields.items():
        fieldType=meta.get('type')
        fieldsToPostgres.append({
            'fieldID':fieldID,
            'fieldType':fieldType,
            'entityID':entityID,
            'description':meta.get('title'),
        })
    return fieldsToPostgres

async def get_all_company(last_update=None):
    """Получение всех компаний с фильтрацией по дате обновления"""
    items = {
        'filter': {
            '>ID': 0,
        },
        'select': ['*', 'UF_*'],
    }
    if last_update:
        items['filter']['>DATE_MODIFY'] = last_update.strftime('%Y-%m-%dT%H:%M:%S')
    companies = await bit.get_all('crm.company.list', params=items)
    companies = companies
    return companies



#Lead
async def get_lead(leadID):
    items={
        'ID':leadID,
        'select':['*', 'UF_*'],
    }
    lead=await bit.call('crm.lead.get',items=items)
    lead=lead['order0000000000']
    return lead 

async def get_all_fields_lead()->list:
    fields=await bit.call('crm.lead.fields',raw=True)
    fields=fields['result']
    return fields

async def get_all_userfields_lead()->list:
    items={
        'filter':{
            '>ID':0,
        }
    }
    fields=await bit.call('crm.lead.userfield.list',items=items,raw=True)
    fields=fields['result']
    return fields

def prepare_userfields_lead_to_postgres(fields:list)->list:
    fieldsToPostgres=[]
    for field in fields:
        fieldName=field.get('FIELD_NAME')
        entityID=field.get('ENTITY_ID')
        userTypeID=field.get('USER_TYPE_ID')
        fieldToPostgres={
            'fieldID':fieldName,
            'entityID':entityID,
            'fieldType':userTypeID,
            'description':field.get('title'),
        }
        fieldsToPostgres.append(fieldToPostgres)
    return fieldsToPostgres

def prepare_fields_lead_to_postgres(fields:list)->list:
    entityID='CRM_LEAD'
    fieldsToPostgres=[]
    for fieldID, meta in fields.items():
        fieldType=meta.get('type')
        fieldsToPostgres.append({
            'fieldID':fieldID,
            'fieldType':fieldType,
            'entityID':entityID,
            'description':meta.get('title'),
        })
    return fieldsToPostgres

async def get_all_lead(last_update=None):
    """Получение всех лидов с фильтрацией по дате обновления"""
    items = {
        'filter': {
            '>ID': 0,
        },
        'select': ['*', 'UF_*'],
    }
    if last_update:
        items['filter']['>DATE_MODIFY'] = last_update.strftime('%Y-%m-%dT%H:%M:%S')
    leads = await bit.get_all('crm.lead.list', params=items)
    leads=leads
    return leads

async def get_history_move_lead()->list[dict]:
    #https://apidocs.bitrix24.ru/api-reference/crm/crm-stage-history-list.html
    """
    entityTypeId - ID типа сущности
    1 - Lead
    2 - Deal
    5 - Invoice
    """
    items={
        'entityTypeId':'1',
    }
    history=await bit.get_all('crm.stagehistory.list',params=items)
    return history





#Contact
async def get_contact(contactID):
    items={
        'ID':contactID,
        'select':['*', 'UF_'],
    }
    contact=await bit.call('crm.contact.get',items=items,raw=True)
    contact=contact['result']
    return contact  

async def get_all_fields_contact()->list:
    fields=await bit.call('crm.contact.fields',raw=True)
    fields=fields['result']
    return fields   

async def get_all_userfields_contact()->list:
    items={
        'filter':{
            '>ID':0,
        }
    }
    fields=await bit.call('crm.contact.userfield.list',items=items,raw=True)
    fields=fields['result']
    return fields

def prepare_userfields_contact_to_postgres(fields:list)->list:
    fieldsToPostgres=[]
    for field in fields:
        fieldName=field.get('FIELD_NAME')
        entityID=field.get('ENTITY_ID')
        userTypeID=field.get('USER_TYPE_ID')
        fieldToPostgres={
            'fieldID':fieldName,
            'entityID':entityID,
            'fieldType':userTypeID,
            'description':field.get('title'),
        }
        fieldsToPostgres.append(fieldToPostgres)
    return fieldsToPostgres

def prepare_fields_contact_to_postgres(fields:list)->list:
    entityID='CRM_CONTACT'
    fieldsToPostgres=[]
    for fieldID, meta in fields.items():
        fieldType=meta.get('type')
        fieldsToPostgres.append({
            'fieldID':fieldID,
            'fieldType':fieldType,
            'entityID':entityID,
            'description':meta.get('title'),
        })
    return fieldsToPostgres

async def get_all_contact(last_update=None):
    """Получение всех контактов с фильтрацией по дате обновления"""
    items = {
        'filter': {
            '>ID':0,
            
        },
        'select':['*', 'UF_*'],
    }
    if last_update:
        items['filter']['>DATE_MODIFY'] = last_update.strftime('%Y-%m-%dT%H:%M:%S')
    contacts = await bit.get_all('crm.contact.list', params=items)
    return contacts




#Task
async def get_task(taskID):
    items={
        'taskId':taskID,
        'select':['*', 'UF_'],
    }
    task=await bit.call('tasks.task.get',items=items,raw=True)
    task=task['result']['task']
    return task 

async def get_all_fields_task()->list:
    fields=await bit.call('tasks.task.getFields',raw=True)
    fields=fields['result']['fields']
    return fields

def prepare_fields_task_to_postgres(fields:list)->list:
    entityID='CRM_TASK'
    fieldsToPostgres=[]
    for fieldID, meta in fields.items():
        fieldType=meta.get('type')
        fieldsToPostgres.append({
            'fieldID':fieldID,
            'fieldType':fieldType,
            'entityID':entityID,
            'description':meta.get('title'),
        })
    fieldsToPostgres.append({
        'fieldID':'UF_CRM_TASK',
        'fieldType':'array',
        'entityID':'CRM_TASK',
        # 'description':,
    })
    return fieldsToPostgres

async def get_all_task(last_update=None):
    """Получение всех задач с фильтрацией по дате обновления"""
    items = {
        'filter': {
            '>taskId': 0,
        },
        'select': ['*', 'UF_*'],
    }
    if last_update:
        items['filter']['>DATE_MODIFY'] = last_update.strftime('%Y-%m-%dT%H:%M:%S')
    tasks = await bit.get_all('tasks.task.list', params=items)
    return tasks




#User
async def get_user(userID)->dict:
    items={
        # 'ID':userID,
        'filter':{
            'ID':userID,
        },
        # 'select':['*', 'UF_'],
    }
    user=await bit.call('user.get',items=items,raw=True)
    user=user['result'][0]
    return user

async def get_all_user()->list:
    items={
        'filter':{
            '>ID':0,
        },
        'ADMIN_MODE':True,
        # 'select':['*', 'UF_*'],
    }
    users=await bit.get_all('user.get',params=items)
    users=users
    return users

async def get_all_user_fields()->list:
    fields=await bit.call('user.fields',raw=True)
    fields=fields['result']
    return fields

async def get_all_user_userfield()->list:
    items={
        'filter':{
            '>ID':0,
        }
    }
    fields=await bit.call('user.userfield.list',items=items,raw=True)
    fields=fields['result']
    return fields

def prepare_user_userfields_to_postgres(fields:list)->list:
    fieldsToPostgres=[]
    for field in fields:
        fieldName=field.get('FIELD_NAME')
        entityID=field.get('ENTITY_ID')
        userTypeID=field.get('USER_TYPE_ID')
        fieldToPostgres={
            'fieldID':fieldName,
            'entityID':entityID,
            'fieldType':userTypeID,
            'description':field.get('title'),
        }
        fieldsToPostgres.append(fieldToPostgres)
    return fieldsToPostgres

def prepare_user_fields_to_postgres(fields:dict)->list:
    entityID='CRM_USER'
    fieldsToPostgres=[]
    pprint
    for fieldID, meta in fields.items():
        fieldType='string'
        fieldsToPostgres.append({
            'fieldID':fieldID,
            'fieldType':fieldType,
            'entityID':entityID,
            'description':meta,
        })
    return fieldsToPostgres



#DynamicItem
async def get_all_dynamic_item(last_update=None):
    """Получение всех динамических элементов с фильтрацией по дате обновления"""
    items = {
        'filter': {
            '>ID': 0,
        },
        'select': ['*', 'UF_*'],
    }
    if last_update:
        items['filter']['>date_modify'] = last_update.strftime('%Y-%m-%dT%H:%M:%S')
    dynamicItem=await bit.call('crm.type.list',items=items,raw=True)
    dynamicItem=dynamicItem['result']['types']
    return dynamicItem
    
async def get_dynamic_item_all_entity(dynamicItemID,last_update=None)->list:
    items={
        'entityTypeId':dynamicItemID,
        'select':['*', 'UF_*'],
    }
    if last_update:
        items['filter']['>date_modify'] = last_update.strftime('%Y-%m-%dT%H:%M:%S')
    dynamicItem=await bit.call('crm.item.list',items=items,raw=True)
    dynamicItem=dynamicItem['result']['items']
    return dynamicItem

async def get_dynamic_item_entity(dynamicItemID, entityID)->dict:
    items={
        'entityTypeId':dynamicItemID,
        'id':entityID,
    }
    dynamicItem=await bit.call('crm.item.get',items=items,raw=True)
    dynamicItem=dynamicItem['result']['item']
    return dynamicItem

async def get_dynamic_item_field(dynamicItemID)->dict:
    items={
        'entityTypeId':dynamicItemID,
        'select':['*', 'UF_*'],
    }
    dynamicItem=await bit.call('crm.item.fields',items=items,raw=True)
    dynamicItem=dynamicItem['result']['fields']
    return dynamicItem

def prepare_dynamic_item_field_to_postgres(fields:dict,entityTypeId:int)->list:
    entityID=f'CRM_DYNAMIC_ITEM_{entityTypeId}'
    fieldsToPostgres=[]
    for fieldID, meta in fields.items():
        fieldType=meta.get('type')
        fieldsToPostgres.append({
            'fieldID':fieldID,
            'fieldType':fieldType,
            'entityID':entityID,
            'description':meta.get('title'),
        })
    return fieldsToPostgres




#call
async def get_all_call()->list[dict]:
    # items={
    #     'ID':callID,
    #     'select':['*', 'UF_'],
    # }
#     {'CALL_CATEGORY': 'external',
#   'CALL_DURATION': '15',
#   'CALL_FAILED_CODE': '200',
#   'CALL_FAILED_REASON': 'Success call',
#   'CALL_ID': '1977F2315C08E697.1734773622.15063781',
#   'CALL_RECORD_URL': '',
#   'CALL_START_DATE': '2024-12-21T12:33:43+03:00',
#   'CALL_TYPE': '1',
#   'CALL_VOTE': None,
#   'COMMENT': None,
#   'COST': '0.0000',
#   'COST_CURRENCY': 'RUR',
#   'CRM_ACTIVITY_ID': '12',
#   'CRM_ENTITY_ID': '12',
#   'CRM_ENTITY_TYPE': 'CONTACT',
#   'EXTERNAL_CALL_ID': None,
#   'ID': '8',
#   'PHONE_NUMBER': '+79097754113',
#   'PORTAL_NUMBER': 'reg130528',
#   'PORTAL_USER_ID': '1',
#   'RECORD_DURATION': None,
#   'RECORD_FILE_ID': None,
#   'REDIAL_ATTEMPT': None,
#   'REST_APP_ID': None,
#   'REST_APP_NAME': None,
#   'SESSION_ID': '3351901428',
#   'TRANSCRIPT_ID': None,
#   'TRANSCRIPT_PENDING': 'N'}
    call=await bit.get_all('voximplant.statistic.get')
    # call=call['result']
    return call


#event
async def get_event(eventID:str)->list:
    items={
        'id':eventID,
    }
    event=await bit.call('calendar.event.getbyid',params=items)
    # event=event['result']
    return event

async def get_all_event_by_user(userID:str=None,last_update=None)->list:
    if userID is None:
        items={
            'type': 'company_calendar',
            'ownerId': '',   
        }
        print(items)
    else:
        items={
            'type': 'user',
            'ownerId': userID,  
            'from': last_update.strftime('%Y-%m-%dT%H:%M:%S'),
            # 'to': last_update.strftime('%Y-%m-%dT%H:%M:%S'),
        }
    if last_update:
        # items['filter']['>TIMESTAMP_X'] = last_update.strftime('%Y-%m-%dT%H:%M:%S')
        items['from'] = last_update.strftime('%Y-%m-%dT%H:%M:%S')
    # print(items)
    event=await bit.get_all('calendar.event.get',params=items)
    # event=event['result']
    return event

async def get_all_event(last_update=None)->list:
    users=await get_all_user()
    events=[]
    print(f'{len(users)=}')
    for user in users:
        userID=user.get('ID')
        events=await get_all_event_by_user(userID,last_update)
        print(f'{userID=} {len(events)=}')
        events.extend(events)
    print(f'{len(events)=}')
    # events.extend(await get_all_event_by_user(last_update=last_update))
    return events




#Подразделения
async def get_all_department()->list[dict]:
    # items={
    #     'filter':{
    #         '>ID':0,
    #     },
    #     'select':['*', 'UF_*'],
    # }
    department=await bit.get_all('department.get')
    
    return department


#Воронки
async def get_all_category(entityTypeId:int=2)->list[dict]:
    """
    entityTypeId=2 - Сделки
    """
    params={
        'entityTypeId':entityTypeId
    }
    status=await bit.get_all('crm.category.list',params=params)
    return status


#Статусы воронок
async def get_all_status_pipeline(ENTITY_ID:str='DEAL_STAGE')->list[dict]:
    """
    ENTITY_ID=DEAL_STAGE - Статусы сделок
    ENTITY_ID=STATUS - Статусы лидов
    """
    items={
            # {'%ENTITY_ID':ENTITY_ID}
            'filter':{'%ENTITY_ID':ENTITY_ID}
            }
    print(items)
    status=await bit.get_all('crm.status.list',params=items)
    # import json
    # with open('status.json', 'w') as file:
    #     json.dump(status, file)
    prepareStatus=[]
    for element in status:
        try:
            if element.get('ENTITY_ID').startswith(ENTITY_ID):
                prepareStatus.append(element)
        except:
            print(f'{element.get('ENTITY_ID')=} {ENTITY_ID=}')
    return prepareStatus

async def get_all_status()->list:
    status=[] 
    status.extend(await get_all_status_pipeline('STATUS'))
    status.extend(await get_all_status_pipeline('DEAL_STAGE'))
    return status




#TODO перенести обновление полей в отдельный модуль

def get_current_datetime():
    """
    Функция для получения текущей даты и времени.
    
    :return: Текущая дата и время в формате 'YYYY-MM-DD HH:MM:SS'
    """
    # current_datetime = datetime.now()+timedelta(hours=3)  # Получаем текущую дату и время
    current_datetime = datetime.now() # Получаем текущую дату и время
    # return current_datetime.strftime('%Y-%m-%dT%H:%M:00+Z')  # Форматируем в строку
    # return '2024-11-07'
    # return '2024-11-07T18:48:54+03:00'
    # return '2024.07.11T00:00:00+03:00'
    # return '2024-11-01T13:51:08+03:00'
    # return '11-11-2024 00:00:00 00:2024-07-11 00Ж00Ж00 00Ж0000'
    # return "'$(date --iso-8601=seconds)'"
    return current_datetime

def prepare_pole_history(stageID:str):
    """Возвращает подходящие название поля обрезаное до 20 знаков"""
    poleHistoryDate=f'UF_CRM_{NAME_APP}'
    # print(f'вход {stageID=}')
    fullPole=poleHistoryDate+stageID
    # print(fullPole)
    # print(len(fullPole))
    idPole=stageID
    if len(fullPole)>20:
        startIndex=len(fullPole)-20

        # fullPole=poleHistoryDate+stageID[startIndex:]
        if startIndex > 0:
            
            fullPole=poleHistoryDate+stageID[:-startIndex] 
            idPole=stageID[:-startIndex]
        else:
            fullPole=poleHistoryDate+stageID
            idPole=stageID[:startIndex]
        # fullPole=fullPole[:20] 
        # idPole=stageID[startIndex:]
    return fullPole, idPole

async def update_history_date_for_deal(dealID, stageID:str=None):
    deal=await get_deal(dealID=dealID)
    # pprint(deal)
    deal=deal
    if stageID is None:
        stageID=deal['STAGE_ID']
        
    
    poleHistory, idStage= prepare_pole_history(stageID=stageID)
    poleHistory=poleHistory.replace(':','_')
    print(f'{poleHistory=}')
    
    historyDealPole=deal[poleHistory]
    print(f'{historyDealPole=} {get_current_datetime()=}')
    # 1/0
    items={
        'id':dealID,
        'fields':{
            poleHistory:get_current_datetime()
        }

    }
    pprint(items)
    if deal[poleHistory]=='':
        await bit.call('crm.deal.update',items=items)




async def main():
    #Deal
    # fields= await get_all_userfields_deal()
    # prepareFields=prepare_userfields_deal_to_postgres(fields)
    # pprint(prepareFields)
    # user=await get_lead(10865)
    # pprint(user)
    status=await get_history_move_lead()
    pprint(status)
    # types=await get_all_user_fields()
    # pprint(types)
    # for type in types:
    #     entityTypeId=type.get('entityTypeId')
    #     fields=await get_dynamic_item_field(entityTypeId)
    #     pprint(fields)

    #     prepareFields=prepare_dynamic_item_field_to_postgres(fields,entityTypeId)
    #     pprint(prepareFields)
    
    # users= await get_dynamic_item_field(1036)
    # pprint(users)
    # prepareFields=prepare_fields_company_to_postgres(fields)
    # pprint(prepareFields)

if __name__ == '__main__':
    # a=asyncio.run(get_all_event_by_user(userID='138',last_update=datetime.now()-timedelta(days=20)))
    # pprint(a)
    asyncio.run(main())
    # asyncio.run(get_userfields(234))