from datetime import datetime, timedelta
from pprint import pprint
from fast_bitrix24 import BitrixAsync
from dotenv import load_dotenv

import asyncio

from tqdm import tqdm

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

def prepare_fields_deal_to_postgres(fields:list, table_name:str)->list[list,list]:
    entityID='CRM_DEAL'
    fieldsToPostgres=[]
    enumerateFields=[]
    for fieldID, meta in fields.items():
        fieldType=meta.get('type')

        description=fieldID
        if meta.get('listLabel'):
            description=meta['listLabel']
        elif meta.get('description'):
            description=meta['description']
        elif meta.get('title'):
            description=meta['title']
        
        if fieldType=='enumeration':
            items=meta['items']
            for item in items:
                enumerateFields.append({
                    'field_id':fieldID,
                    'value':item['VALUE'],
                    'id_value':item['ID'],
                    'table_name':table_name,
                    'description':meta['listLabel'].lower().replace(' ','_'),
                })
        
    
        fieldsToPostgres.append({
            'fieldID':fieldID,
            'fieldType':fieldType,
            'entityID':entityID,
            'description':description,
        })

    

    return fieldsToPostgres, enumerateFields


async def get_all_deal(last_update=None)->list:
    items={
        'FILTER':{
            '>ID':0,
        },
        'SELECT':['*', 'UF_*'],
    }
    if last_update:
        items['FILTER']['>DATE_MODIFY'] = last_update.strftime('%Y-%m-%dT%H:%M:%S')
    print(items)
    deals=await bit.get_all('crm.deal.list',params=items)
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
    enumerateFields=[]
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
        if userTypeID=='enumeration':
            items=field.get('LIST')
            for item in items:
                enumerateFields.append({
                    'field_id':fieldName,
                    'value':item['VALUE'],
                    'id_value':item['ID'],
                    'table_name':'company_fields',
                    'description':field.get('FIELD_NAME').lower().replace(' ','_'),
                })
    return fieldsToPostgres, enumerateFields

def prepare_fields_company_to_postgres(fields:list)->list:
    entityID='CRM_COMPANY'
    fieldsToPostgres=[]
    for fieldID, meta in fields.items():
        fieldType=meta.get('type')
        isMultiple=meta.get('isMultiple', False)
        if isMultiple:
            fieldType='array'

        fieldsToPostgres.append({
            'fieldID':fieldID,
            'fieldType':fieldType,
            'entityID':entityID,
            'description':meta.get('title'),
            'isMultiple':isMultiple,
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

async def get_all_lead()->list:
    items={
        'filter':{
            '>ID':0,
        },
        'select':['*', 'UF_*'],
    }
    leads=await bit.get_all('crm.lead.list',params=items)
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
    enumerateFields=[]
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
        
        if userTypeID=='enumeration':
            # pprint(field)
            # 1/0
            items=field.get('LIST')
            for item in items:
                enumerateFields.append({
                    'field_id':fieldName,
                    'value':item['VALUE'],
                    'id_value':item['ID'],
                    'table_name':'contact_fields',
                    'description':field['FIELD_NAME'],
                })
    return fieldsToPostgres, enumerateFields

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

async def get_all_task(last_update=None)->list:
    items={
        'filter':{
            '>taskId':0,
        },
        'select':['*', 'UF_*', 'TAGS'],
    }
    if last_update:
        items['filter']['>DATE_MODIFY'] = last_update.strftime('%Y-%m-%dT%H:%M:%S')
    tasks=await bit.get_all('tasks.task.list',params=items)
    tasks=tasks
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
async def get_all_dynamic_item()->list:
    items={
        # 'ID':dynamicItemID,
        'select':['*', 'UF_*'],
    }
    dynamicItem=await bit.call('crm.type.list',items=items,raw=True)
    dynamicItem=dynamicItem['result']['types']
    return dynamicItem
    
async def get_dynamic_item_all_entity(dynamicItemID)->list:
    items={
        'entityTypeId':dynamicItemID,
        'select':['*', 'UF_*'],
    }
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

def prepare_record_for_insert(pole:str):
    """
    Подготавливает запись для вставки, обрабатывая специальные случаи
    """
    normalized_key=pole.lower()
    # Особая обработка для ID
    # if normalized_key == 'id':
    #     normalized_key = 'bitrix_id'
    if normalized_key == 'responsibleid':
        normalized_key = 'responsible_id'
    if normalized_key == 'createdby':
        normalized_key = 'created_by'
    
    # if normalized_key == 'updatedby':
    #     normalized_key = 'updated_by'
    # if normalized_key == 'assignedbyid':
    #     normalized_key = 'assigned_by_id'
    
    if normalized_key=='createddate':
        normalized_key='created_date'
    if normalized_key == 'stageid':
        normalized_key = 'stage_id'
    if normalized_key == 'groupid':
        normalized_key = 'group_id'
    if normalized_key == 'parentid':
        normalized_key = 'parent_id'
    if normalized_key == 'datecreate':
        normalized_key = 'date_create'
    if normalized_key == 'datemodify':
        normalized_key = 'date_modify'
    if normalized_key == 'lastactivitytime':
        normalized_key = 'last_activity_time'
    if normalized_key == 'movedtime':
        normalized_key = 'moved_time'
    if normalized_key == 'datestart':
        normalized_key = 'date_start'
    if normalized_key == 'datefinish':
        normalized_key = 'date_finish'
    if normalized_key == 'closeddate':
        normalized_key = 'closed_date'
    if normalized_key == 'ufcrmtask':
        normalized_key = 'uf_crm_task'
    if normalized_key == 'notviewed':
        normalized_key = 'not_viewed'
    if normalized_key == 'changedby':
        normalized_key = 'changed_by'
    if normalized_key == 'changeddate':
        normalized_key = 'changed_date'
    if normalized_key == 'statuschangedby':
        normalized_key = 'status_changed_by'
    if normalized_key == 'statuschangeddate':
        normalized_key = 'status_changed_date'
    if normalized_key == 'closedby':
        normalized_key = 'closed_by'
    if normalized_key == 'closeddate':
        normalized_key = 'closed_date'
    if normalized_key == 'activitydate':
        normalized_key = 'activity_date'
    if normalized_key == 'datefinish':
        normalized_key = 'date_finish'
    if normalized_key == 'xmlid':
        normalized_key = 'xml_id'
    if normalized_key == 'commentscount':
        normalized_key = 'comments_count'
    if normalized_key == 'servicecommentscount':
        normalized_key = 'service_comments_count'
    if normalized_key == 'newcommentscount':
        normalized_key = 'new_comments_count'
    if normalized_key == 'enddateplan':
        normalized_key = 'end_date_plan'
    if normalized_key == 'durationplan':
        normalized_key = 'duration_plan'
    if normalized_key == 'durationfact':
        normalized_key = 'duration_fact'
    if normalized_key == 'allowchangedeadline':
        normalized_key = 'allow_change_deadline'
    if normalized_key == 'allowtimetracking':
        normalized_key = 'allow_time_tracking'
    if normalized_key == 'taskcontrol':
        normalized_key = 'task_control'
    if normalized_key == 'addinreport':
        normalized_key = 'add_in_report'
    if normalized_key == 'forkedbytemplateid':
        normalized_key = 'forked_by_template_id'
    if normalized_key == 'timeestimate':
        normalized_key = 'time_estimate'
    if normalized_key == 'timespentinlogs':
        normalized_key = 'time_spent_in_logs'
    if normalized_key == 'matchworktime':
        normalized_key = 'match_work_time'
    if normalized_key == 'forumtopicid':
        normalized_key = 'forum_topic_id'
    if normalized_key == 'forumid':
        normalized_key = 'forum_id'
    if normalized_key == 'siteid':
        normalized_key = 'site_id'
    if normalized_key == 'outlookversion':
        normalized_key = 'outlook_version'
    if normalized_key == 'vieweddate':
        normalized_key = 'viewed_date'
    if normalized_key == 'ismuted':
        normalized_key = 'is_muted'
    if normalized_key == 'ispinned':
        normalized_key = 'is_pinned'
    if normalized_key == 'exchangeid':
        normalized_key = 'exchange_id'
    if normalized_key == 'ispinnedingroup':
        normalized_key = 'is_pinned_in_group'
    if normalized_key == 'durationtype':
        normalized_key = 'duration_type'
    # if normalized_key == 'creator':
    #     normalized_key = 'created_by'

    
    
    return normalized_key

def prepare_dynamic_item_field_to_postgres(fields:dict,entityTypeId:int, table_name:str)->list:
    entityID=f'CRM_DYNAMIC_ITEM_{entityTypeId}'
    fieldsToPostgres=[]
    enumerateFields=[]
    
    for fieldID, meta in fields.items():
        fieldType=meta.get('type')

        description=fieldID
        if meta.get('listLabel'):
            description=meta['listLabel']
        elif meta.get('description'):
            description=meta['description']
        elif meta.get('title'):
            description=meta['title']

        fieldID= prepare_record_for_insert(fieldID)
        # if description in ('id','ID'):
        #     description='bitrix_id'
        fieldsToPostgres.append({
            'fieldID':fieldID,
            'fieldType':fieldType,
            'entityID':entityID,
            'description':description,
        })

        if fieldType=='enumeration':
            items=meta['items']
            for item in items:
                enumerateFields.append({
                    'field_id':fieldID,
                    'value':item['VALUE'],
                    'id_value':item['ID'],
                    'table_name':table_name,
                    'description':meta['listLabel'],
                })

    return fieldsToPostgres, enumerateFields





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
    
    event=await bit.call('calendar.event.getbyid',items=items)
    print(event)
    # event=event['result']
    return event['order0000000000']

async def get_all_event_by_user(userID:str=None)->list:
    if userID is None:
        items={
            'type': 'company_calendar',
            'ownerId': '',   
        }
        
    else:
        items={
            'type': 'user',
            'ownerId': userID,   
        }
    

    event=await bit.get_all('calendar.event.get',params=items)
    # event=event['result']
    return event

async def get_all_event()->list:
    users=await get_all_user()
    events=[]
    for user in users:
        userID=user.get('ID')
        events=await get_all_event_by_user(userID)
        print(f'{userID=} {len(events)=}')
        events.extend(events)

    events.extend(await get_all_event_by_user())
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
        
        # if ENTITY_ID.startswith(element.get('ENTITY_ID')):
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


async def update_events():
    """Инкрементное обновление таблицы event_fields"""
    print('начали update_events')
    # last_update = await get_last_update_date('event_fields')
    # print(f'{last_update=}')
    events = get_all_event(last_update=datetime.now())
    print(f'{len(events)=}')
    # for event in events:
    #     print(f'{event["ID"]=} обработан')
    #     existing_record = await get_record('event_fields', str(event['ID']))
    #     if existing_record:
    #         await update_record('event_fields', event)
    #     else:
    #         await insert_record('event_fields', event)

async def get_tags_task(taskID:int):
    items={
        'taskId':taskID,
        'select':['TAGS'],
    }
    
    tags=await bit.call('tasks.task.get',items=items)
    tags=tags['tags']
    return tags


async def get_history_task(taskID:int):
    items={
        'taskId':taskID,
    }
    history=await bit.get_all('tasks.task.history.list',params=items)
    history=history
    return history

async def get_result_task(taskID:int):
    items={
        'taskId':taskID,
    }
    result=await bit.get_all('tasks.task.result.list',params=items)
    result=result
    return result


async def get_comment_task(taskID:int):
    items={
        'taskId':taskID,
    }
    comment=await bit.get_all('task.commentitem.getlist',params=items)
    comment=comment
    return comment


async def get_task_comments_batc(tasks:list):
    """Получение комментариев к задачам"""
    # пакетно получаем комментарии к задачам по 50 задач
    # tasks=await get_all_task()
    
    i=0
    commands={}
    results={}
    for task in tqdm(tasks,desc='Получение комментариев к задачам'):
        i+=1
        if i>20:
            # pprint(commands)
            
            results.update(await bit.call_batch ({
                'halt': 0,
                'cmd': commands
            }))

            commands={}
            i=0
        #TODO почему-то эта сделака не доступна fast_bitrix24.server_response.ErrorInServerResponseException: {'5593': {'error': 'ERROR_CORE', 'error_description': 'TASKS_ERROR_EXCEPTION_#8; Action failed; 8/TE/ACTION_FAILED_TO_BE_PROCESSED<br>'}}    
        if task['id']=='5593':
            continue
        
        commands[f'{task["id"]}']=f'task.commentitem.getlist?taskId={task["id"]}'
    return results

async def get_result_task_comments(tasks:list):
    """Получение результатов задач"""
    i=0
    commands={}
    results={}
    for task in tqdm(tasks, 'Получение результатов задач'):
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



async def get_activity_company_batc(companyID:list):
    """Получение комментариев к задачам"""
    # пакетно получаем комментарии к задачам по 50 задач
    # tasks=await get_all_task()
    
    i=0
    commands={}
    results={}
    for company in tqdm(companyID,desc='Получение комментариев к задачам'):
        i+=1
        if i>48:
            results.update(await bit.call_batch ({
                'halt': 0,
                'cmd': commands
            }))

            commands={}
            i=0
        commands[f'{company["ID"]}']=f'crm.activity.list?id={company["ID"]}'
    return results

async def main():
    #Deal
    # fields= await get_all_userfields_deal()
    # prepareFields=prepare_userfields_deal_to_postgres(fields)
    # pprint(prepareFields)
    # user=await get_lead(10865)
    # pprint(user)
    # status=await get_all_user()
    # pprint(status)
    # print(len(status))
    await get_all_task(last_update=datetime.now())
    1/0
    # history=await get_result_task(30255)
    history=await get_event(24453)
    pprint(history)
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
    # asyncio.run(get_all_fields_deal())
    asyncio.run(main())
    # asyncio.run(get_userfields(234))
