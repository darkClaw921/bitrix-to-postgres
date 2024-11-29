import workBitrix
import workPostgres
from pprint import pprint
import asyncio
from tqdm import tqdm
async def main():
    #Deal
    fields=await workBitrix.get_all_fields_deal()
    userFields=await workBitrix.get_all_userfields_deal()
    
    prepareUserFields=workBitrix.prepare_userfields_deal_to_postgres(userFields)
    prepareFields= workBitrix.prepare_fields_deal_to_postgres(fields)
    
    allFields=prepareFields+prepareUserFields
    # pprint(allFields)
    # 1/0
    await workPostgres.create_table_from_fields('deal_fields',allFields)
    

    #Company
    fields=await workBitrix.get_all_fields_company()
    userFields=await workBitrix.get_all_userfields_company()
    
    prepareUserFields=workBitrix.prepare_userfields_company_to_postgres(userFields)
    prepareFields= workBitrix.prepare_fields_company_to_postgres(fields)
    
    allFields=prepareFields+prepareUserFields
    await workPostgres.create_table_from_fields('company_fields',allFields)


    #Lead
    fields=await workBitrix.get_all_fields_lead()
    userFields=await workBitrix.get_all_userfields_lead()
    
    prepareUserFields=workBitrix.prepare_userfields_lead_to_postgres(userFields)
    prepareFields= workBitrix.prepare_fields_lead_to_postgres(fields)
    
    allFields=prepareFields+prepareUserFields
    await workPostgres.create_table_from_fields('lead_fields',allFields)

    
    #Contact
    fields=await workBitrix.get_all_fields_contact()
    userFields=await workBitrix.get_all_userfields_contact()
    
    prepareUserFields=workBitrix.prepare_userfields_contact_to_postgres(userFields)
    prepareFields= workBitrix.prepare_fields_contact_to_postgres(fields)
    
    allFields=prepareFields+prepareUserFields
    await workPostgres.create_table_from_fields('contact_fields',allFields)
    

    #Task
    fields= await workBitrix.get_all_fields_task()
    prepareFields=workBitrix.prepare_fields_task_to_postgres(fields)
    
    allFields=prepareFields
    await workPostgres.create_table_from_fields('task_fields',allFields)


    #User
    fields=await workBitrix.get_all_user_fields()
    userFields=await workBitrix.get_all_user_userfield()
    
    prepareUserFields=workBitrix.prepare_user_userfields_to_postgres(userFields)
    prepareFields=workBitrix.prepare_user_fields_to_postgres(fields)
    allFields=prepareFields+prepareUserFields
    await workPostgres.create_table_from_fields('user_fields',allFields)
    


    #DynamicItem
    items=await workBitrix.get_all_dynamic_item()
    for item in items:
        entityTypeId=item.get('entityTypeId')
        fields=await workBitrix.get_dynamic_item_field(entityTypeId)
        prepareFields=workBitrix.prepare_dynamic_item_field_to_postgres(fields,entityTypeId)
        await workPostgres.create_table_from_fields(f'dynamic_item_fields_{entityTypeId}',prepareFields)



    # Вставка записей после создания таблиц
    await insert_records()


async def insert_records():
    deals = await workBitrix.get_all_deal()
    print(f'Всего записей Deal: {len(deals)}')
    for deal in tqdm(deals):
        try:
            await workPostgres.insert_record('deal_fields', deal)
        except Exception as e:
            print(f"Ошибка при добавлении записи: {str(e)}")

    companies = await workBitrix.get_all_company()
    print(f'Всего записей Company: {len(companies)}')
    for company in tqdm(companies):
        try:
            await workPostgres.insert_record('company_fields', company)
        except Exception as e:
            print(f"Ошибка при добавлении записи: {str(e)}")

    leads = await workBitrix.get_all_lead()
    print(f'Всего записей Lead: {len(leads)}')
    for lead in tqdm(leads):
        try:
            await workPostgres.insert_record('lead_fields', lead)
        except Exception as e:
            print(f"Ошибка при добавлении записи: {str(e)}")

    contacts = await workBitrix.get_all_contact()
    print(f'Всего записей Contact: {len(contacts)}')
    for contact in tqdm(contacts):
        try:
            await workPostgres.insert_record('contact_fields', contact)
        except Exception as e:
            print(f"Ошибка при добавлении записи: {str(e)}")

    tasks = await workBitrix.get_all_task()
    print(f'Всего записей Task: {len(tasks)}')
    for task in tqdm(tasks):
        try:
            await workPostgres.insert_record('task_fields', task)
        except Exception as e:
            print(f"Ошибка при добавлении записи: {str(e)}")

    users = await workBitrix.get_all_user()
    print(f'Всего записей User: {len(users)}')
    for user in tqdm(users):
        try:
            await workPostgres.insert_record('user_fields', user)
        except Exception as e:
            print(f"Ошибка при добавлении записи: {str(e)}")

    items=await workBitrix.get_all_dynamic_item()
    for item in items:
        entityTypeId=item.get('entityTypeId')
        fields=await workBitrix.get_dynamic_item_all_entity(entityTypeId)
        for field in fields:
            try:
                await workPostgres.insert_record(f'dynamic_item_fields_{entityTypeId}', field)
            except Exception as e:
                print(f"Ошибка при добавлении записи: {str(e)}")

async def drop_table():
    await workPostgres.drop_table('deal_fields')
    await workPostgres.drop_table('company_fields')
    await workPostgres.drop_table('lead_fields')
    await workPostgres.drop_table('contact_fields')
    await workPostgres.drop_table('task_fields')
    await workPostgres.drop_table('user_fields')
    items=await workBitrix.get_all_dynamic_item()
    for item in items:
        entityTypeId=item.get('entityTypeId')
        await workPostgres.drop_table(f'dynamic_item_fields_{entityTypeId}')

async def update_records():
    deal = await workBitrix.get_deal(2)
    try:
        await workPostgres.update_record('deal_fields', deal)
        print("Запись успешно обновлена")
    except Exception as e:
        print(f"Ошибка при обновлении записи: {str(e)}")
async def update_records_task():
    task=await workBitrix.get_task(2)
    pprint(task) 
    # 1/0
    await workPostgres.insert_record('task_fields', task)
    # await workPostgres.update_record('task_fields', task)

async def delete_records():
    try:
        deleted = await workPostgres.delete_record('task_fields', '3')
        if deleted:
            print("Запись успешно удалена")
        else:
            print("Запись не найдена")
    except Exception as e:
        print(f"Ошибка при удалении записи: {str(e)}")

if __name__ == '__main__':
    # asyncio.run(drop_table())
    asyncio.run(main())
    # asyncio.run(delete_records())
    # asyncio.run(update_records_task())
