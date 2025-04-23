import asyncio
import json

import os
import traceback
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from pprint import pprint
import clickhouse_connect
load_dotenv()

userName = os.environ.get('CLICKHOUSE_USERNAME')
password = os.environ.get('CLICKHOUSE_PASSWORD')
url = os.environ.get('CLICKHOUSE_HOST')
db = os.environ.get('CLICKHOUSE_DB')


MAPPING_FIELDS_PATH='/opt/airflow/scripts/mapping_fields'
client = asyncio.run(clickhouse_connect.get_async_client(
    host=url,
    user=userName,
    password=password,
    database=db
))

# Функция для создания таблицы для перемещенных задач
async def create_table_move_task_to_history():
    query = """
    CREATE TABLE IF NOT EXISTS move_task_to_history (
        record_id UInt64,
        created_date DateTime DEFAULT now(),
        bitrix_id String,
        uf_crm_task String,
        uf_crm_task_history String,
        title String,
        assigned_by_id String,
        responsible_id String,
        stage_id String,
        group_id String,
        parent_id String,
        date_create DateTime,
        date_modify DateTime,
        deadline DateTime,
        last_activity_time DateTime,
        changeddate String,
        changedby String,
        moved_time DateTime,
        date_start DateTime,
        date_finish DateTime,
        close_date DateTime,
        description String
    ) ENGINE = MergeTree()
    ORDER BY (record_id, created_date)
    """
    await client.query(query)
    return True

# Функция для создания таблицы из списка полей
async def create_table_from_fields(table_name, fields_list):
    # Начало запроса на создание таблицы
    # pprint(fields_list)
    
    query = f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
    query += "    record_id UInt64,\n"
    query += "    created_date DateTime DEFAULT now(),\n"
    query += "    bitrix_id String,\n"
    
    descriptionsNames = []
    added_fields = set()  # Для отслеживания уже добавленных полей
    # pprint(fields_list)
    for field in fields_list:
        if field['fieldID'].lower() in ['bitrix_id', 'created_date']:
            continue
        field_name = field['fieldID'].lower()
        
        description=field.get('description')
        if description is None:
            field_name = field['fieldID'].lower()
        else:
            field_name=f"`{description.replace(' ','_').lower()}`"


        # Пропускаем дублированные поля
        if field_name in added_fields:
            print(f"Поле {field_name} уже существует, пропускаем.")
            continue
            
        added_fields.add(field_name)
        field_type = field['fieldType']
        description=field.get('description')
        
        
        if description in descriptionsNames:
            description = f'{description}_{field_name}'
            descriptionsNames.append(description)
        else:
            descriptionsNames.append(description)
            
        # Особая обработка для поля ID из Bitrix
        if field_name.lower() == 'id' or field_name.lower() == 'call_id':
            continue
            
        # Определяем тип поля в ClickHouse
        if field_type == 'string':
            ch_type = 'String'
        elif field_type == 'datetime':
            ch_type = 'DateTime'
        elif field_type == 'date':
            ch_type = 'DateTime'
        elif field_type == 'integer':
            ch_type = 'Int64'
        elif field_type == 'float':
            ch_type = 'Float64'
        elif field_type == 'decimal':
            ch_type = 'Decimal(18, 2)'
        elif field_type == 'double':
            ch_type = 'Float64'
        elif field_type == 'boolean':
            ch_type = 'UInt8'
        elif field_type == 'url':
            ch_type = 'String'
        elif field_type == 'json':
            ch_type = 'String'  # В ClickHouse нет прямого типа JSON, используем String
        elif field_type in ['array', 'iblock_element_list']:
            ch_type = 'Array(String)'
        else:
            ch_type = 'String'
            
        query += f"    {field_name} {ch_type} COMMENT '{description}',\n"
    
    # Завершаем запрос
    query = query.rstrip(',\n') + "\n"
    query += ") ENGINE = MergeTree()\n"
    query += "ORDER BY (record_id, created_date)"
    # print(query)
    await client.query(query)
    return True

# Функция для добавления столбца в таблицу
async def add_column_to_table(table_name, column_name, column_type):
    # Определяем ClickHouse тип данных на основе переданного типа
    ch_type = {
        'string': 'String',
        'datetime': 'DateTime',
        'integer': 'Int64',
        'float': 'Float64',
        'boolean': 'UInt8',
        'url': 'String',
        'json': 'String',
        'array': 'Array(String)',
        'crm_multifield': 'Array(String)'
    }.get(column_type.lower(), 'String')
    
    query = f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_name} {ch_type}"
    
    try:
        await client.query(query)
        print(f"Столбец {column_name} успешно добавлен в таблицу {table_name}")
        return True
    except Exception as e:
        print(f"Ошибка при добавлении столбца: {e}")
        raise e

# Функция для удаления столбца из таблицы
async def drop_column_from_table(table_name, column_name):
    query = f"ALTER TABLE {table_name} DROP COLUMN IF EXISTS {column_name}"
    
    try:
        await client.query(query)
        print(f"Столбец {column_name} успешно удален из таблицы {table_name}")
        return True
    except Exception as e:
        print(f"Ошибка при удалении столбца: {e}")
        raise e

# Функция для получения информации о типах столбцов таблицы
async def get_table_column_types(table_name):
    query = f"DESCRIBE TABLE {table_name}"
    
    try:
        result = await client.query(query)
        
        column_types = {}
        for row in result.result_rows:
            # print(row)
            column_name = row[0]
            data_type = row[1]
            
            # Определяем тип Python на основе типа ClickHouse
            if 'Array' in data_type:
                column_types[column_name] = 'array'
            elif data_type in ('String', 'FixedString'):
                column_types[column_name] = 'string'
            elif data_type in ('Int8', 'Int16', 'Int32', 'Int64', 'UInt8', 'UInt16', 'UInt32', 'UInt64'):
                column_types[column_name] = 'integer'
            elif data_type in ('Float32', 'Float64', 'Decimal'):
                column_types[column_name] = 'float'
            elif data_type == 'UInt8':  # для boolean
                column_types[column_name] = 'boolean'
            elif data_type in ('DateTime', 'Date'):
                column_types[column_name] = 'datetime'
            else:
                column_types[column_name] = 'string'
                
        return column_types
    except Exception as e:
        print(f"Ошибка при получении информации о столбцах: {e}")
        raise e

# Функция для конвертации значения в нужный тип
async def convert_value_to_type(value, target_type):
    """
    Преобразует значение в указанный тип
    """
    if value is None:
        return None
    if value is None or (isinstance(value, str) and not value):
        return None
        
    try:
        if target_type == 'string':
            value=str(value).replace('"','').replace('#','').replace('\\','').replace('`','').replace("'",'')
            return value
        
        elif target_type == 'integer':
            try:
                return int(float(value)) if value else 0
            except:
                if isinstance(value, str):
                    if value == 'N':
                        return 0
                    elif value == 'Y':
                        return 1
                    else:
                        return None
                else:
                    return None
        elif target_type == 'float':
            return float(value) if value else 0.0
        elif target_type == 'boolean':
            if isinstance(value, str):
                return 1 if value.lower() in ('true', '1', 'yes', 'y') else 0
            return 1 if value else 0
        elif target_type == 'datetime':
            if isinstance(value, str):
                try:
                    # Преобразуем строку в datetime с учетом часового пояса
                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    # Преобразуем в UTC и убираем информацию о часовом поясе
                    return dt.astimezone(timezone.utc).replace(tzinfo=None)
                except ValueError:
                    try:
                        dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                        return dt
                    except ValueError:
                        return None
            elif isinstance(value, datetime):
                # Если у datetime есть часовой пояс, преобразуем в UTC и убираем tzinfo
                if value.tzinfo is not None:
                    return value.astimezone(timezone.utc).replace(tzinfo=None)
                return value
            return None
        elif target_type == 'array':
            if isinstance(value, str):
                try:
                    # Пробуем распарсить JSON строку

                    parsed_value = json.loads(value)
                    if isinstance(parsed_value, list):
                        return [json.dumps(item) if isinstance(item, (dict, list)) else str(item).replace('"','').replace('#','').replace('\\','').replace('`','').replace("'",'') for item in parsed_value]
                    return [str(value).replace('"','').replace('#','').replace('\\','').replace('`','').replace("'",'').replace("'",'')]
                except json.JSONDecodeError:
                    return [str(value).replace('"','').replace('#','').replace('\\','').replace('`','').replace("'",'').replace("'",'')]
            elif isinstance(value, (list, tuple)):
                return [json.dumps(item) if isinstance(item, (dict, list)) else str(item).replace('"','').replace('#','').replace('\\','').replace('`','').replace("'",'') for item in value]
            return [str(value).replace('"','').replace('#','').replace('\\','').replace('`','').replace("'",'')]
        else:
            return str(value).replace('"','').replace('#','').replace('\\','').replace('`','').replace("'",'')
    except Exception as e:
        print(f"Ошибка преобразования значения {value} в тип {target_type}: {traceback.format_exc()}")
        return None

# Функция для подготовки записи перед вставкой
async def prepare_record_for_insert(data, date_fields=None):
    """
    Подготавливает запись для вставки, обрабатывая специальные случаи
    """
    if date_fields is None:
        date_fields = ['BEGINDATE', 'CLOSEDATE', 'DATE_CREATE', 
                      'DATE_MODIFY', 'LAST_ACTIVITY_TIME', 'MOVED_TIME']
    
    prepared_data = {}
    for key, value in data.items():
        # Преобразуем ключ в нижний регистр
        normalized_key = key.lower()
        
        # Особая обработка для ID
        if normalized_key == 'id':
            normalized_key = 'bitrix_id'
        if normalized_key == 'responsibleid':
            normalized_key = 'responsible_id'
        if normalized_key == 'createdby':
            normalized_key = 'created_by'
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

            
        if normalized_key in ('descriptioninbbcode',
                              'accomplicesdata',
                              'auditorsdata',
                              'substatus',
                              'responsible',
                              'creator',
                              'addInReport',
                              
                              'xml_id','post',
                              'sourceid'):
            continue

        # Пропускаем None значения
        if value is None:
            continue
            
        # Преобразуем пустые строки в None для дат
        if isinstance(value, str) and not value and key in date_fields:
            prepared_data[normalized_key] = None
        else:
            prepared_data[normalized_key] = value
    
    return prepared_data


def replace_placeholders(query, values):
    # Преобразуем значения в строковый формат для SQL
    formatted_values = []
    for val in values:
        if val is None:
            formatted_values.append('NULL')
        elif isinstance(val, str):
            # Экранируем одинарные кавычки и оборачиваем строки в кавычки
            formatted_values.append(f"'{val.replace('\'', '\'\'')}'")
        elif isinstance(val, (int, float)):
            formatted_values.append(str(val))
        elif isinstance(val, datetime):
            # Форматируем datetime в строку для SQL
            formatted_values.append(f"'{val.strftime('%Y-%m-%d %H:%M:%S')}'")
        elif isinstance(val, list):
            # Обработка списков - преобразуем в строку с одинарными кавычками для ClickHouse
            if len(val) == 0:
                formatted_values.append("[]")
            else:
                elements = []
                for item in val:
                    if isinstance(item, str):
                        elements.append(f"'{item.replace('\'', '\'\'')}'")
                    else:
                        elements.append(f"'{str(item)}'")
                formatted_values.append(f"[{', '.join(elements)}]")
        else:
            formatted_values.append(f"'{str(val)}'")
    
    # Заменяем все %s на соответствующие значения
    parts = query.split('%s')
    result = parts[0]
    for i in range(len(formatted_values)):
        result += formatted_values[i] + (parts[i+1] if i+1 < len(parts) else '')
    
    return result

# Функция для вставки записи в таблицу
async def insert_record(table_name, data, is_mapping=False):
    """
    Вставляет запись в указанную таблицу
    """
    data['created_date'] = datetime.now()
    # Подготавливаем данные
    prepared_data = await prepare_record_for_insert(data)
    
    # Получаем информацию о типах столбцов
    column_types = await get_table_column_types(table_name)
    
    # Преобразуем имена колонок в нижний регистр в column_types
    column_types = {k.lower(): v for k, v in column_types.items()}
    
    # Преобразуем данные в соответствии с типами столбцов
    # pprint(column_types)
    converted_data = {}
    mapping_fields = {}
    if is_mapping:
    
        # with open(f'mapping_fields/mapping_fields_{table_name}.json', 'r', encoding='utf-8') as f:
        with open(f'{MAPPING_FIELDS_PATH}/mapping_fields_{table_name}.json', 'r', encoding='utf-8') as f:
            mapping_fields = json.load(f)
    # print('mapping_fields') 
    # pprint(mapping_fields)
    
    for key_bitrix, value_bitrix in prepared_data.items():
        # if key_bitrix in column_types:
        key_bitrix_lower=key_bitrix.lower()
        mapping_keys=list(mapping_fields.keys())
        if is_mapping and key_bitrix_lower in mapping_keys:
            
            key_bitrix_lower=mapping_fields.get(key_bitrix_lower)
            
            if key_bitrix_lower is None or key_bitrix_lower == 'id':
                key_bitrix_lower=key_bitrix
        
        elif is_mapping and key_bitrix_lower != 'bitrix_id':
            continue
        # print(key_bitrix_lower)
        # if value_bitrix in [['18309'],['1907'], ['1909']]:
        # if key_bitrix_lower == 'bitrix_id' and str(value_bitrix) in ('13550','29033'):
        
            # if value_bitrix == ['1909']:
            
                # print(key_bitrix_lower)
        # print('column_types')
        # pprint(column_types)
        # if key_bitrix_lower in ('sourceid','movedby'):
        #     1+0
        converted_value = await convert_value_to_type(value_bitrix, column_types[key_bitrix_lower])
        if converted_value is not None:  # Добавляем только не-None значения
            if key_bitrix in mapping_fields:
                if is_mapping and mapping_fields[key_bitrix] is not None:
                    converted_data[f'"{mapping_fields[key_bitrix]}"'] = converted_value
                else:
                    converted_data[key_bitrix] = converted_value
            else:
                converted_data[key_bitrix] = converted_value
    
    if not converted_data:
        raise ValueError("Нет данных для вставки после преобразования")
    
    # Генерируем запрос для вставки
    if 'record_id' not in converted_data:
        # Генерируем уникальный ID, если его нет
        query = f"SELECT max(record_id) FROM {table_name}"
        result = await client.query(query)
        result=result.result_rows
        # pprint(result)

        max_id = result[0][0] if result[0][0] is not None else 0
        converted_data['record_id'] = max_id + 1
    
    # Формируем списки колонок и значений для запроса
    columns = list(converted_data.keys())
    values = [converted_data[col] for col in columns]
    # print(columns)
    
    placeholders = ', '.join(['%s' for _ in columns])
    query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
    # Формируем SQL запрос
    # query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES"
    
    # print(values)
    # print(query)
    # 1/0
    try:
        valid_query=replace_placeholders(query, values)
        # await client.query(query, parameters=values)
        await client.command(valid_query)
        # print(f"Запись успешно добавлена в таблицу {table_name}")
        return converted_data['record_id']
    except Exception as e:
        print(values)
        print(query)

        print(replace_placeholders(query, values))
        print(f"Ошибка при добавлении записи: {traceback.format_exc()}")
        raise e

# Функция для обновления записи в таблице
async def update_record(table_name, data, is_mapping=False):
    """
    Обновляет запись в указанной таблице
    """
    # В ClickHouse нет прямого обновления записей, нужно использовать ALTER TABLE UPDATE
    # или делать INSERT с меткой времени и потом получать последние данные по запросу
    
    # Подготавливаем данные
    prepared_data = await prepare_record_for_insert(data)
    
    if 'bitrix_id' not in prepared_data:
        raise ValueError("Отсутствует bitrix_id для обновления записи")
    
    # Получаем информацию о типах столбцов
    column_types = await get_table_column_types(table_name)
    
    
    # Преобразуем имена колонок в нижний регистр в column_types
    column_types = {k.lower(): v for k, v in column_types.items()}
    # pprint(column_types)
    # Преобразуем данные в соответствии с типами столбцов
    converted_data = {}
    mapping_fields = {}
    if is_mapping:

        # with open(f'mapping_fields/mapping_fields_{table_name}.json', 'r', encoding='utf-8') as f:
        with open(f'{MAPPING_FIELDS_PATH}/mapping_fields_{table_name}.json', 'r', encoding='utf-8') as f:
            mapping_fields = json.load(f)

    for key, value in prepared_data.items():
        key_lower=key.lower()
        mapping_keys=list(mapping_fields.keys())
        if is_mapping and key_lower in mapping_keys:
            key_lower=mapping_fields.get(key_lower)
        
            
        elif is_mapping and key_lower != 'bitrix_id':
            continue
        # if value == ['18309']:
        #     print(key_lower)

        if key_lower in column_types:
            converted_value = await convert_value_to_type(value, column_types[key_lower])
            if converted_value is not None:  # Добавляем только не-None значения
                if key_lower in mapping_fields:
                    if is_mapping and mapping_fields[key_lower] is not None:
                        converted_data[f'"{mapping_fields[key_lower]}"'] = converted_value
                    else:
                        converted_data[key_lower] = converted_value
                else:
                    converted_data[key_lower] = converted_value
    

    if not converted_data:
        raise ValueError("Нет данных для обновления после преобразования")
    
    # В ClickHouse обновление через ALTER TABLE ... UPDATE
    # pprint(converted_data)
    bitrix_id = converted_data.pop('bitrix_id')
    
    if converted_data:
        # Формируем SET часть запроса
        set_parts = []
        for key, value in converted_data.items():
            key=key.replace('"','')
            if isinstance(value, str):
                set_parts.append(f""""{key}" = '{value}' """)
            elif isinstance(value, (int, float)):
                set_parts.append(f""""{key}" = {value}""")
            elif isinstance(value, datetime):
                set_parts.append(f""""{key}" = '{value.strftime('%Y-%m-%d %H:%M:%S')}' """)
            elif isinstance(value, list):
                values_str = "[" + ", ".join([f"'{v}'" for v in value]) + "]"
                set_parts.append(f""""{key}" = {values_str}""")
            else:
                set_parts.append(f""""{key}" = NULL""")
        
        # Формируем SQL запрос
        query = f"ALTER TABLE {table_name} UPDATE {', '.join(set_parts)} WHERE bitrix_id = '{bitrix_id}'"
        # print(query)
        try:
            await client.query(query)
            print(f"Запись с bitrix_id={bitrix_id} успешно обновлена в таблице {table_name}")
            # В ClickHouse ALTER TABLE UPDATE не возвращает ID обновленной записи
            # Получаем ID отдельным запросом
            select_query = f"""SELECT "record_id" FROM {table_name} WHERE bitrix_id = '{bitrix_id}' LIMIT 1"""
            result = await client.command(select_query)
            # result=result.result_rows
            # pprint(result)
            # return result[0][0] if result else None
            return result
        except Exception as e:
            print(query)
            print(f"Ошибка при обновлении записи: {traceback.format_exc()}")
            raise e
    else:
        print("Нет данных для обновления")
        return None

# Функция для получения записи из таблицы
async def get_record(table_name, bitrix_id):
    """
    Получает запись из указанной таблицы по bitrix_id
    """
    query = f"SELECT * FROM {table_name} WHERE bitrix_id = '{bitrix_id}' LIMIT 1"
    result = await client.query(query)
    result=result.result_rows
    return result[0] if result else None

# Функция для удаления записи из таблицы
async def delete_record(table_name, bitrix_id):
    """
    В ClickHouse нет прямого удаления по условию для таблиц MergeTree.
    Альтернативы:
    1. Использовать таблицу с ReplacingMergeTree и отмечать записи как удаленные
    2. Использовать ALTER TABLE DELETE (работает медленно)
    """
    # Для примера используем ALTER TABLE DELETE
    query = f"ALTER TABLE {table_name} DELETE WHERE bitrix_id = '{bitrix_id}'"
    
    try:
        await client.query(query)
        print(f"Запись с bitrix_id={bitrix_id} успешно удалена из таблицы {table_name}")
        return True
    except Exception as e:
        print(f"Ошибка при удалении записи: {e}")
        raise e

# Функция для удаления таблицы
async def drop_table(table_name):
    """
    Удаляет таблицу
    """
    query = f"DROP TABLE IF EXISTS {table_name}"
    
    try:
        await client.query(query)
        print(f"Таблица {table_name} успешно удалена")
        return True
    except Exception as e:
        print(f"Ошибка при удалении таблицы {table_name}: {e}")
        raise e

# Функция для получения структуры базы данных
async def get_database_structure():
    """
    Получает структуру всех таблиц в базе данных
    """
    try:
        # Запрос для получения списка таблиц
        tables_query = "SHOW TABLES"
        tables = await client.query(tables_query)
        
        output = []
        
        for table in tables:
            table_name = table[0]
            output.append(f"\nТаблица: {table_name}")
            output.append("-" * 50)
            
            # Получаем информацию о столбцах
            columns_query = f"DESCRIBE TABLE {table_name}"
            columns = await client.query(columns_query)
            
            # Выводим информацию о столбцах
            output.append("\nСтруктура:")
            for column in columns:
                column_name, data_type = column[0], column[1]
                output.append(f"{column_name}: {data_type}")
            
            # Получаем пример данных
            sample_query = f"SELECT * FROM {table_name} LIMIT 1"
            try:
                sample_data = await client.query(sample_query)
                
                if sample_data:
                    output.append("\nПример данных:")
                    for i, column in enumerate(columns):
                        if i < len(sample_data[0]):
                            output.append(f"{column[0]}: {sample_data[0][i]}")
                else:
                    output.append("\nТаблица пуста")
            except Exception as e:
                output.append(f"\nОшибка при получении примера данных: {e}")
            
            output.append("\n" + "=" * 80)
        
        # Записываем результат в файл
        with open('database_structure.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(output))
            
        print("Структура базы данных сохранена в файл database_structure.txt")
        
    except Exception as e:
        print(f"Ошибка при получении структуры базы данных: {e}")
        raise e

# Главная функция для тестирования
def main():
    get_database_structure()
    # create_table_move_task_to_history()

if __name__ == '__main__':
    main()
