from pprint import pprint
from fast_bitrix24 import BitrixAsync
from dotenv import load_dotenv

import asyncio


import os
load_dotenv()


bit = BitrixAsync(os.getenv('WEBHOOK'), ssl=False)


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
        })
    return fieldsToPostgres

async def get_all_deal()->list:
    items={
        'filter':{
            '>ID':0,
        }
    }
    deals=await bit.call('crm.deal.list',items=items,raw=True)
    deals=deals['result']
    return deals




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
        })
    return fieldsToPostgres

async def get_all_company()->list:
    items={
        'filter':{
            '>ID':0,
        }
    }
    companies=await bit.call('crm.company.list',items=items,raw=True)
    companies=companies['result']
    return companies



#Lead
async def get_lead(leadID):
    items={
        'ID':leadID,
        'select':['*', 'UF_'],
    }
    lead=await bit.call('crm.lead.get',items=items,raw=True)
    lead=lead['result']
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
        })
    return fieldsToPostgres

async def get_all_lead()->list:
    items={
        'filter':{
            '>ID':0,
        }
    }
    leads=await bit.call('crm.lead.list',items=items,raw=True)
    leads=leads['result']
    return leads




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
        })
    return fieldsToPostgres

async def get_all_contact()->list:
    items={
        'filter':{
            '>ID':0,
        }
    }
    contacts=await bit.call('crm.contact.list',items=items,raw=True)
    contacts=contacts['result']
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
        })
    fieldsToPostgres.append({
        'fieldID':'UF_CRM_TASK',
        'fieldType':'array',
        'entityID':'CRM_TASK',
    })
    return fieldsToPostgres

async def get_all_task()->list:
    items={
        'filter':{
            '>taskId':0,
        }
    }
    tasks=await bit.call('tasks.task.list',items=items,raw=True)
    tasks=tasks['result']['tasks']
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
    }
    users=await bit.call('user.get',items=items,raw=True)
    users=users['result']
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
        }
        fieldsToPostgres.append(fieldToPostgres)
    return fieldsToPostgres

def prepare_user_fields_to_postgres(fields:dict)->list:
    entityID='CRM_USER'
    fieldsToPostgres=[]
    for fieldID, meta in fields.items():
        fieldType='string'
        fieldsToPostgres.append({
            'fieldID':fieldID,
            'fieldType':fieldType,
            'entityID':entityID,
        })
    return fieldsToPostgres



#DynamicItem
async def get_all_dynamic_item()->list:
    items={
        # 'ID':dynamicItemID,
        'select':['*', 'UF_'],
    }
    dynamicItem=await bit.call('crm.type.list',items=items,raw=True)
    dynamicItem=dynamicItem['result']['types']
    return dynamicItem
    
async def get_dynamic_item_all_entity(dynamicItemID)->list:
    items={
        'entityTypeId':dynamicItemID,
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
        'select':['*', 'UF_'],
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
        })
    return fieldsToPostgres







async def main():
    #Deal
    # fields= await get_all_userfields_deal()
    # prepareFields=prepare_userfields_deal_to_postgres(fields)
    # pprint(prepareFields)
    types=await get_all_dynamic_item()
    pprint(types)
    for type in types:
        entityTypeId=type.get('entityTypeId')
        fields=await get_dynamic_item_field(entityTypeId)
        pprint(fields)

        prepareFields=prepare_dynamic_item_field_to_postgres(fields,entityTypeId)
        pprint(prepareFields)
    
    # users= await get_dynamic_item_field(1036)
    # pprint(users)
    # prepareFields=prepare_fields_company_to_postgres(fields)
    # pprint(prepareFields)

if __name__ == '__main__':
    # asyncio.run(get_all_fields_deal())
    asyncio.run(main())
    # asyncio.run(get_userfields(234))
