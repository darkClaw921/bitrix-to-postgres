import time
import workBitrix
import workPostgres
from pprint import pprint
import asyncio
# from tqdm import tqdm
from tqdm.asyncio import tqdm
# import workClickHouse as workPostgres 
async def main():
    
    #Deal
    fields=await workBitrix.get_all_fields_deal()
    userFields=await workBitrix.get_all_userfields_deal()

    prepareUserFields=workBitrix.prepare_userfields_deal_to_postgres(userFields)
    prepareFields= workBitrix.prepare_fields_deal_to_postgres(fields)
    
    allFields=prepareFields+prepareUserFields
    # allFields=prepareUserFields

    
    await workPostgres.create_table_from_fields('deal_fields',allFields)

    1/0
    
    
    # 1/0

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

    # # 1/0
    # #Contact
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
    # type{'443': {'id': 443, 'title': 'Оплата'}}
    allFields.append({'fieldID':'tags','fieldType':'json'})
    allFields.append({'fieldID':'group','fieldType':'json'})
    await workPostgres.create_table_from_fields('task_fields',allFields)


    #TaskComment
    prepareFields=[
        # {'fieldID':'id','fieldType':'string',},
        {'fieldID':'bitrix_id','fieldType':'string',},
        {'fieldID':'task_id','fieldType':'string',},
        {'fieldID':'author_id','fieldType':'string',},
        {'fieldID':'author_name','fieldType':'string',},
        {'fieldID':'post_message','fieldType':'string',},
        {'fieldID':'post_date','fieldType':'datetime',},
        {'fieldID':'attached_objects','fieldType':'json',},
        # {'fieldID':'attached_files','fieldType':'json',},
    ]
    await workPostgres.create_table_from_fields('task_comment_fields',prepareFields)



    #TaskResult
    prepareFields=[
        {'fieldID':'bitrix_id','fieldType':'string',},
        {'fieldID':'task_id','fieldType':'string',},
        {'fieldID':'text','fieldType':'string',},
        {'fieldID':'createdat','fieldType':'datetime',},
        {'fieldID':'updatedat','fieldType':'datetime',},
        {'fieldID':'createdby','fieldType':'string',},
        {'fieldID':'files','fieldType':'array',},
        {'fieldID':'status','fieldType':'string',},
        {'fieldID':'commentid','fieldType':'string',},


        
    ]
    await workPostgres.create_table_from_fields('task_result_fields',prepareFields)
    


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



    #MoveTaskToHistory
    # fields=await workBitrix.get_all_fields_task()
    # prepareFields=workBitrix.prepare_fields_task_to_postgres(fields)
   
    prepareFields = [
        # {'fieldID':'record_id','fieldType':'integer',},
        {'fieldID':'id','fieldType':'string',},
        # {'fieldID':'created_date','fieldType':'datetime',},
        {'fieldID':'fieldValue','fieldType':'string',},
        {'fieldID':'fieldDescription','fieldType':'string',},
        {'fieldID':'bitrix_id','fieldType':'string',},
        {'fieldID':'uf_crm_task','fieldType':'string',},
        {'fieldID':'uf_crm_task_history','fieldType':'string',},
        {'fieldID':'title','fieldType':'string',},
        {'fieldID':'assigned_by_id','fieldType':'string',},
        {'fieldID':'responsible_id','fieldType':'string',},
        {'fieldID':'stage_id','fieldType':'string',},
        {'fieldID':'group_id','fieldType':'string',},
        {'fieldID':'parent_id','fieldType':'string',},
        {'fieldID':'responsible_id','fieldType':'string',},
        {'fieldID':'date_create','fieldType':'datetime',},
        {'fieldID':'date_modify','fieldType':'datetime',},
        {'fieldID':'deadline','fieldType':'datetime',},
        {'fieldID':'last_activity_time','fieldType':'datetime',},
        {'fieldID':'changeddate','fieldType':'string',},
        {'fieldID':'changedby','fieldType':'string',},
        {'fieldID':'moved_time','fieldType':'datetime',},
        {'fieldID':'date_start','fieldType':'datetime',},
        {'fieldID':'date_finish','fieldType':'datetime',},
        {'fieldID':'close_date','fieldType':'datetime',},
        {'fieldID':'description','fieldType':'string',},
    ]
    await workPostgres.create_table_from_fields('move_task_to_history',prepareFields)

    # 1/0
    #Call
    prepareFields=[
        {'fieldID':'call_category','fieldType':'string',},
        {'fieldID':'call_duration','fieldType':'string',},
        {'fieldID':'call_failed_code','fieldType':'string',},
        {'fieldID':'call_failed_reason','fieldType':'string',},
        {'fieldID':'call_id','fieldType':'string',},
        {'fieldID':'call_record_url','fieldType':'string',},
        {'fieldID':'call_start_date','fieldType':'datetime',},
        {'fieldID':'call_type','fieldType':'string',},
        {'fieldID':'call_vote','fieldType':'string',},
        {'fieldID':'comment','fieldType':'string',},
        {'fieldID':'cost','fieldType':'string',},
        {'fieldID':'cost_currency','fieldType':'string',},
        {'fieldID':'crm_activity_id','fieldType':'string',},
        {'fieldID':'crm_entity_id','fieldType':'string',},
        {'fieldID':'crm_entity_type','fieldType':'string',},
        {'fieldID':'external_call_id','fieldType':'string',},
        {'fieldID':'phone_number','fieldType':'string',},
        {'fieldID':'portal_number','fieldType':'string',},
        {'fieldID':'portal_user_id','fieldType':'string',},
        {'fieldID':'record_duration','fieldType':'string',},
        {'fieldID':'record_file_id','fieldType':'string',},
        {'fieldID':'redial_attempt','fieldType':'string',},
        {'fieldID':'rest_app_id','fieldType':'string',},
        {'fieldID':'rest_app_name','fieldType':'string',},
        {'fieldID':'session_id','fieldType':'string',},
        {'fieldID':'transcript_id','fieldType':'string',},
        {'fieldID':'transcript_pending','fieldType':'string',},
    ]
    await workPostgres.create_table_from_fields('call_fields',prepareFields)
    

    #HistoryMoveDeal
    prepareFieldsHistoryMoveDeal=[
        {'fieldID':'category_id','fieldType':'string',},
        {'fieldID':'created_time','fieldType':'datetime',},
        {'fieldID':'id','fieldType':'string',},
        {'fieldID':'owner_id','fieldType':'string',},
        {'fieldID':'stage_id','fieldType':'string',},
        {'fieldID':'stage_semantic_id','fieldType':'string',},
        {'fieldID':'type_id','fieldType':'string',},
    ]
    await workPostgres.create_table_from_fields('history_move_deal',prepareFieldsHistoryMoveDeal)

    #HistoryMoveLead
    prepareFieldsHistoryMoveLead=[
        # {'fieldID':'category_id','fieldType':'string',},
        {'fieldID':'created_time','fieldType':'datetime',},
        {'fieldID':'id','fieldType':'string',},
        {'fieldID':'owner_id','fieldType':'string',},
        {'fieldID':'status_id','fieldType':'string',},
        {'fieldID':'status_semantic_id','fieldType':'string',},
        {'fieldID':'type_id','fieldType':'string',},
    ]
    await workPostgres.create_table_from_fields('history_move_lead',prepareFieldsHistoryMoveLead)


    #Event
    prepareFieldsEvent=[
        
        {'fieldID':'accessibility','fieldType':'string',},
        {'fieldID':'active','fieldType':'string',},
        {'fieldID':'attendees_codes','fieldType':'array',},
        {'fieldID':'attendee_list','fieldType':'array',},
        {'fieldID':'cal_dav_label','fieldType':'string',},
        {'fieldID':'cal_type','fieldType':'string',},
        {'fieldID':'collab_id','fieldType':'string',},
        {'fieldID':'color','fieldType':'string',},
        {'fieldID':'created_by','fieldType':'string',},
        {'fieldID':'date_create','fieldType':'datetime',},
        {'fieldID':'date_from','fieldType':'datetime',},
        {'fieldID':'date_from_formatted','fieldType':'datetime',},
        {'fieldID':'date_from_ts_utc','fieldType':'datetime',},
        {'fieldID':'date_to','fieldType':'datetime',},
        {'fieldID':'date_to_formatted','fieldType':'datetime',},
        {'fieldID':'date_to_ts_utc','fieldType':'datetime',},
        {'fieldID':'date_to_formatted','fieldType':'datetime',},
        {'fieldID':'dav_exch_label','fieldType':'string',},
        {'fieldID':'dav_xml_id','fieldType':'string',},
        {'fieldID':'deleted','fieldType':'string',},
        {'fieldID':'dav_xml_id','fieldType':'string',},
        {'fieldID':'dt_from','fieldType':'datetime',},
        {'fieldID':'dt_length','fieldType':'string',},
        {'fieldID':'dt_skip_time','fieldType':'string',},
        {'fieldID':'dt_to','fieldType':'datetime',},
        {'fieldID':'event_type','fieldType':'string',},
        {'fieldID':'exdate','fieldType':'string',},
        {'fieldID':'g_event_id','fieldType':'string',},
        {'fieldID':'id','fieldType':'string',},
        {'fieldID':'importance','fieldType':'string',},
        {'fieldID':'is_meeting','fieldType':'string',},
        {'fieldID':'location','fieldType':'string',},
        {'fieldID':'meeting','fieldType':'string',},
        {'fieldID':'allow_invite','fieldType':'string',},
        {'fieldID':'chat_id','fieldType':'string',},
        {'fieldID':'hide_guests','fieldType':'string',},
        {'fieldID':'host_name','fieldType':'string',},
        {'fieldID':'language_id','fieldType':'string',},
        {'fieldID':'mail_from','fieldType':'string',},
        {'fieldID':'meeting_creator','fieldType':'string',},
        {'fieldID':'notify','fieldType':'string',},
        {'fieldID':'reinvite','fieldType':'string',},
        {'fieldID':'meeting_host','fieldType':'string',},
        {'fieldID':'meeting_status','fieldType':'string',},
        {'fieldID':'name','fieldType':'string',},
        {'fieldID':'options','fieldType':'string',},
        {'fieldID':'original_date_from','fieldType':'datetime',},
        {'fieldID':'owner_id','fieldType':'string',},
        {'fieldID':'parent_id','fieldType':'string',},
        {'fieldID':'private_event','fieldType':'string',},
        {'fieldID':'recurrence_id','fieldType':'string',},
        {'fieldID':'relations','fieldType':'string',},
        {'fieldID':'remind','fieldType':'string',},
        {'fieldID':'rrule','fieldType':'string',},
        {'fieldID':'section_dav_xml_id','fieldType':'string',},
        {'fieldID':'section_id','fieldType':'string',},
        {'fieldID':'sect_id','fieldType':'string',},
        {'fieldID':'sync_status','fieldType':'string',},
        {'fieldID':'text_color','fieldType':'string',},
        {'fieldID':'timestamp_x','fieldType':'datetime',},
        {'fieldID':'tz_from','fieldType':'string',},
        {'fieldID':'tz_offset_from','fieldType':'string',},
        {'fieldID':'tz_offset_to','fieldType':'string',},
        {'fieldID':'tz_to','fieldType':'string',},
        {'fieldID':'uf_crm_cal_event','fieldType':'string',},
        {'fieldID':'uf_webdav_cal_event','fieldType':'string',},
        {'fieldID':'version','fieldType':'string',},
        {'fieldID':'attendees_entity_list','fieldType':'array',},
        {'fieldID':'user_offset_from','fieldType':'string',},
        {'fieldID':'user_offset_to','fieldType':'string',},
    ]
    await workPostgres.create_table_from_fields('event_fields',prepareFieldsEvent)



    # ДатаОбновления – Техническая таблица, фиксирующая даты последнего обновления каждой из таблиц 
    prepareFields=[
       {'fieldID':'id','fieldType':'string',},
       {'fieldID':'date_update','fieldType':'datetime',},
       {'fieldID':'table_name','fieldType':'string',},
    
    ]
    await workPostgres.create_table_from_fields('date_update',prepareFields)


    #Подразделения
    prepareFieldsDepartment=[
        {'fieldID':'id','fieldType':'string',},
        {'fieldID':'name','fieldType':'string',},
        {'fieldID':'parent','fieldType':'string',},
        {'fieldID':'sort','fieldType':'string',},
     
    ]
    await workPostgres.create_table_from_fields('department',prepareFieldsDepartment)


    #Воронки
    prepareFieldsCategory=[
        {'fieldID':'id','fieldType':'string',},
        {'fieldID':'name','fieldType':'string',},
        {'fieldID':'entitytypeid','fieldType':'string',},
        {'fieldID':'isdefault','fieldType':'string',},
        {'fieldID':'sort','fieldType':'string',},
        {'fieldID':'originatorid','fieldType':'string',},
        {'fieldID':'originid','fieldType':'string',},
    ]
    await workPostgres.create_table_from_fields('category',prepareFieldsCategory)


    #Статусы воронок
    prepareFieldsStatus=[
        {'fieldID':'category_id','fieldType':'string',},
        {'fieldID':'color','fieldType':'string',},
        {'fieldID':'entity_id','fieldType':'string',},
        {'fieldID':'extra','fieldType':'string',},
        {'fieldID':'id','fieldType':'string',},
        {'fieldID':'name','fieldType':'string',},
        {'fieldID':'name_init','fieldType':'string',},
        {'fieldID':'semantics','fieldType':'string',},
        {'fieldID':'sort','fieldType':'string',},
        {'fieldID':'status_id','fieldType':'string',},
        {'fieldID':'system','fieldType':'string',},
    ]
    await workPostgres.create_table_from_fields('status',prepareFieldsStatus)

    prepareFieldsToken=[
        {'fieldID':'id','fieldType':'string',},
        {'fieldID':'token','fieldType':'string',},
    ]
    await workPostgres.create_table_from_fields('token',prepareFieldsToken)

    # Вставка записей после создания таблиц
    await insert_records()


async def insert_records():
    # Создаем семафор для ограничения количества одновременных подключений
    semaphore = asyncio.Semaphore(5)  # Ограничиваем до 5 одновременных подключений
    
    # Обработка сделок
    deals = await workBitrix.get_all_deal()
    print(f'Всего записей Deal: {len(deals)}')
    
    async def process_deal(deal):
        async with semaphore:
            try:
                await workPostgres.insert_record('deal_fields', deal)
            except Exception as e:
                print(f"Ошибка при добавлении записи: {str(e)}")
    
    tasks = [process_deal(deal) for deal in deals]
    await tqdm.gather(*tasks, desc="Обработка сделок")

    # Обработка компаний
    companies = await workBitrix.get_all_company()
    print(f'Всего записей Company: {len(companies)}')
    
    async def process_company(company):
        async with semaphore:
            try:
                await workPostgres.insert_record('company_fields', company)
            except Exception as e:
                print(f"Ошибка при добавлении записи: {str(e)}")
    
    tasks = [process_company(company) for company in companies]
    await tqdm.gather(*tasks, desc="Обработка компаний")

    # Обработка лидов
    leads = await workBitrix.get_all_lead()
    print(f'Всего записей Lead: {len(leads)}')
    
    async def process_lead(lead):
        async with semaphore:
            try:
                await workPostgres.insert_record('lead_fields', lead)
            except Exception as e:
                print(f"Ошибка при добавлении записи: {str(e)}")
    
    tasks = [process_lead(lead) for lead in leads]
    await tqdm.gather(*tasks, desc="Обработка лидов")


    # Обработка контактов
    contacts = await workBitrix.get_all_contact()
    print(f'Всего записей Contact: {len(contacts)}')
    
    async def process_contact(contact):
        async with semaphore:
            try:
                await workPostgres.insert_record('contact_fields', contact)
            except Exception as e:
                print(f"Ошибка при добавлении записи: {str(e)}")
    
    tasks = [process_contact(contact) for contact in contacts]
    await tqdm.gather(*tasks, desc="Обработка контактов")

    # Обработка задач
    tasks_list = await workBitrix.get_all_task()
    print(f'Всего записей Task: {len(tasks_list)}')
    
    async def process_task(task):
        async with semaphore:
            try:
                await workPostgres.insert_record('task_fields', task)
            except Exception as e:
                print(f"Ошибка при добавлении записи: {str(e)}")
    
    tasks = [process_task(task) for task in tasks_list]
    await tqdm.gather(*tasks, desc="Обработка задач")

    # Обработка пользователей
    users = await workBitrix.get_all_user()
    print(f'Всего записей User: {len(users)}')
    
    async def process_user(user):
        async with semaphore:
            try:
                await workPostgres.insert_record('user_fields', user)
            except Exception as e:
                print(f"Ошибка при добавлении записи: {str(e)}")
    
    tasks = [process_user(user) for user in users]
    await tqdm.gather(*tasks, desc="Обработка пользователей")

    # Обработка динамических элементов
    items = await workBitrix.get_all_dynamic_item()
    for item in items:
        entityTypeId = item.get('entityTypeId')
        fields = await workBitrix.get_dynamic_item_all_entity(entityTypeId)
        
        async def process_dynamic_field(field):
            async with semaphore:
                try:
                    await workPostgres.insert_record(f'dynamic_item_fields_{entityTypeId}', field)
                except Exception as e:
                    print(f"Ошибка при добавлении записи: {str(e)}")
        
        tasks = [process_dynamic_field(field) for field in fields]
        await tqdm.gather(*tasks, desc=f"Обработка динамических элементов {entityTypeId}")

    #Обработка звонков
    calls=await workBitrix.get_all_call()
    print(f'Всего записей Call: {len(calls)}')
    async def process_call(call):
        async with semaphore:
            try:
                await workPostgres.insert_record('call_fields', call)
            except Exception as e:
                print(f"Ошибка при добавлении записи: {str(e)}")

    tasks = [process_call(call) for call in calls]
    await tqdm.gather(*tasks, desc="Обработка звонков")

    #Обработака истории перемещения сделок
    history_move_deal=await workBitrix.get_history_move_deal()
    print(f'Всего записей HistoryMoveDeal: {len(history_move_deal)}')
    async def process_history_move_deal(history_move_deal):
        async with semaphore:
            try:
                await workPostgres.insert_record('history_move_deal', history_move_deal)
            except Exception as e:
                print(f"Ошибка при добавлении записи: {str(e)}")
    
    tasks = [process_history_move_deal(history_move_deal) for history_move_deal in history_move_deal]
    await tqdm.gather(*tasks, desc="Обработка истории перемещения сделок")

    #Обработка истории перемещения лидов
    history_move_lead=await workBitrix.get_history_move_lead()
    print(f'Всего записей HistoryMoveLead: {len(history_move_lead)}')
    async def process_history_move_lead(history_move_lead):
        async with semaphore:
            try:
                await workPostgres.insert_record('history_move_lead', history_move_lead)
            except Exception as e:
                print(f"Ошибка при добавлении записи: {str(e)}")

    tasks = [process_history_move_lead(history_move_lead) for history_move_lead in history_move_lead]
    await tqdm.gather(*tasks, desc="Обработка истории перемещения лидов")


    #Обработка событий
    events=await workBitrix.get_all_event()
    print(f'Всего записей Event: {len(events)}')
    async def process_event(event):
        async with semaphore:
            try:
                eventID=await workPostgres.get_record('event_fields', event.get('id'))
                if eventID:
                    await workPostgres.update_record('event_fields', event)
                else:   
                    await workPostgres.insert_record('event_fields', event)
                    
            except Exception as e:
                print(f"Ошибка при добавлении записи: {str(e)}")
    
    tasks = [process_event(event) for event in events]
    await tqdm.gather(*tasks, desc="Обработка событий")


    #Обработка подразделений
    departments=await workBitrix.get_all_department()
    print(f'Всего записей Department: {len(departments)}')
    async def process_department(department):
        async with semaphore:
            try:
                await workPostgres.insert_record('department', department)
            except Exception as e:
                print(f"Ошибка при добавлении записи: {str(e)}")

    tasks = [process_department(department) for department in departments]
    await tqdm.gather(*tasks, desc="Обработка подразделений")

    #Обработка воронок
    categories=await workBitrix.get_all_category()
    print(f'Всего записей Category: {len(categories)}')
    async def process_category(category):
        async with semaphore:
            try:
                await workPostgres.insert_record('category', category)
            except Exception as e:
                print(f"Ошибка при добавлении записи: {str(e)}")

    tasks = [process_category(category) for category in categories]
    await tqdm.gather(*tasks, desc="Обработка воронок")

    #Обработка статусов воронок
    status=await workBitrix.get_all_status()
    print(f'Всего записей Status: {len(status)}')
    async def process_status(status):
        async with semaphore:
            try:
                await workPostgres.insert_record('status', status)
            except Exception as e:
                print(f"Ошибка при добавлении записи: {str(e)}")

    tasks = [process_status(status) for status in status]
    await tqdm.gather(*tasks, desc="Обработка статусов воронок")

    #Обработка токенов
    token=[workBitrix.WEBHOOK]
    print(f'Всего записей Token: {len(token)}')
    async def process_token(token):
        async with semaphore:
            try:
                await workPostgres.insert_record('token', {'id':1,'token':token})
            except Exception as e:
                print(f"Ошибка при добавлении записи: {str(e)}")

    tasks = [process_token(token) for token in token]
    await tqdm.gather(*tasks, desc="Обработка токенов")


    #Обработка комментариев задач
    tasksBitrix=await workBitrix.get_all_task()
    task_and_comments=await workBitrix.get_task_comments_batc(tasks=tasksBitrix)
    #dict['taskID':['coment1','coment2']]
    print('Всего записей Комментарии к задачам ',len(task_and_comments))

    async def process_task_comments(task_id,task_comments):
        async with semaphore:
            try:
                for comment in task_comments:
                    commenta={
                        'task_id':task_id,
                        'bitrix_id':comment.get('ID'),
                        'author_id':comment.get('AUTHOR_ID'),
                        'author_name':comment.get('AUTHOR_NAME'),
                        'post_message':comment.get('POST_MESSAGE'),
                        'post_date':comment.get('POST_DATE'),
                        'attached_objects':comment.get('ATTACHED_OBJECTS'),
                    }
                    await workPostgres.insert_record('task_comment_fields', commenta)

            except Exception as e:
                print(f"Ошибка при добавлении записи: {str(e)}")

    tasks = [process_task_comments(task_id,task_comments) for task_id,task_comments in task_and_comments.items()]
    await tqdm.gather(*tasks, desc="Обработка комментариев задач")
            

    #Обработка результатов задач
    results=await workBitrix.get_result_task_comments(tasks=tasksBitrix)
    print(f'Всего записей ResultTask: {len(results)}')
    async def process_result_task(taskID,results):
        async with semaphore:
            try:
                for result in results:
                    result={
                        'bitrix_id':result.get('id'),
                        'task_id':taskID,
                        'text':result.get('text'),
                        'createdat':result.get('createdAt'),
                        'updatedat':result.get('updatedAt'),
                        'createdby':result.get('createdBy'),
                        'files':result.get('files'),
                        'status':result.get('status'),
                        'commentid':result.get('commentId'),
                    }
                    await workPostgres.insert_record('result_task', result)
            except Exception as e:
                print(f"Ошибка при добавлении записи: {str(e)}")

    tasks = [process_result_task(taskID,results) for taskID,results in results.items()]
    await tqdm.gather(*tasks, desc="Обработка результатов задач")


    # for task_id, task_comments in task_and_comments.items():
    #     for task_comment in task_comments:
    #         task_comment={
    #             # 'id':task.get('id'),
    #             'task_id':task_id,
    #             'bitrix_id':task_comment.get('ID'),
    #             'author_id':task_comment.get('AUTHOR_ID'),
    #             'author_name':task_comment.get('AUTHOR_NAME'),
    #             'post_message':task_comment.get('POST_MESSAGE'),
    #             'post_date':task_comment.get('POST_DATE'),
    #             'attached_objects':task_comment.get('ATTACHED_OBJECTS'),
    #         }
           
    #         await workPostgres.insert_record('task_comment_fields', task_comment)







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



async def main2():
    #Обработка комментариев задач
    semaphore = asyncio.Semaphore(5)  # Ограничиваем до 5 одновременных подключений
    tasksBitrix= await workBitrix.get_all_task()
    task_and_comments=await workBitrix.get_task_comments_batc(tasks=tasksBitrix)
    #dict['taskID':['coment1','coment2']]
    print('Всего записей Комментарии к задачам ',len(task_and_comments))

    async def process_task_comments(task_id,task_comments):
        async with semaphore:
            try:
                for comment in task_comments:
                    commenta={
                        'task_id':task_id,
                        'bitrix_id':comment.get('ID'),
                        'author_id':comment.get('AUTHOR_ID'),
                        'author_name':comment.get('AUTHOR_NAME'),
                        'post_message':comment.get('POST_MESSAGE'),
                        'post_date':comment.get('POST_DATE'),
                        'attached_objects':comment.get('ATTACHED_OBJECTS'),
                    }
                    await workPostgres.insert_record('task_comment_fields', commenta)

            except Exception as e:
                print(f"Ошибка при добавлении записи: {str(e)}")

    tasks = [process_task_comments(task_id,task_comments) for task_id,task_comments in task_and_comments.items()]
    await tqdm.gather(*tasks, desc="Обработка комментариев задач")

    #Обработка результатов задач
    results=await workBitrix.get_result_task_comments(tasks=tasksBitrix)
    print(f'Всего записей ResultTask: {len(results)}')
    async def process_result_task(taskID,results):
        async with semaphore:
            try:
                for result in results:
                    taskResult={
                        'bitrix_id':result.get('id'),
                        'task_id':taskID,
                        'text':result.get('text'),
                        'createdat':result.get('createdAt'),
                        'updatedat':result.get('updatedAt'),
                        'createdby':result.get('createdBy'),
                        'files':result.get('files'),
                        'status':result.get('status'),
                        'commentid':result.get('commentId'),
                    }
                    await workPostgres.insert_record('task_result_fields', taskResult)
            except Exception as e:
                print(f"Ошибка при добавлении записи: {str(e)}")

    tasks = [process_result_task(taskID,results) for taskID,results in results.items()]
    await tqdm.gather(*tasks, desc="Обработка результатов задач")

if __name__ == '__main__':
    # status= asyncio.run(workBitrix.get_all_status())
    # pprint(status)
    asyncio.run(main())
    # pass
    # asyncio.run(delete_records())
    # asyncio.run(update_records_task())
