import asyncio
import json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import (Column, Integer, Float, String,
                        DateTime, JSON, ARRAY, 
                        BigInteger, func, text, 
                        BOOLEAN, URL, ForeignKey, cast)
from sqlalchemy.orm import relationship, declarative_base
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from pprint import pprint

load_dotenv()

userName = os.environ.get('POSTGRES_USER')
password = os.environ.get('POSTGRES_PASSWORD')
db = os.environ.get('POSTGRES_DB')
url = os.environ.get('POSTGRES_URL')

# Создаем асинхронное подключение к базе данных
# engine = create_async_engine(
#     f'postgresql+asyncpg://postgres:postgres@localhost:5432/postgres',
#     echo=True,
# )
engine = create_async_engine(
    f'postgresql+asyncpg://{userName}:{password}@{url}:5432/{db}',
    echo=True,
)

# Создаем асинхронную фабрику сессий
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def create_table_from_fields(table_name, fields_list):
    # Базовые атрибуты таблицы
    attrs = {
        '__tablename__': table_name,
        'record_id': Column(BigInteger, primary_key=True, autoincrement=True),
        'created_date': Column(DateTime, default=datetime.now)
    }
    
    # Добавляем поля из списка
    for field in fields_list:
        field_name = field['fieldID'].lower()
        field_type = field['fieldType']
        
        # Особая обработка для поля ID из Bitrix
        if field_name.lower() == 'id':
            attrs['bitrix_id'] = Column(String)
            continue
            
        # Определяем тип поля в БД
        if field_type == 'string':
            attrs[field_name] = Column(String)
        if field_type == 'datetime':
            attrs[field_name] = Column(DateTime)
        if field_type == 'integer':
            attrs[field_name] = Column(BigInteger)
        if field_type == 'float':
            attrs[field_name] = Column(Float)
        if field_type == 'boolean':
            attrs[field_name] = Column(BOOLEAN)
        if field_type == 'url':
            attrs[field_name] = Column(URL)
        if field_type == 'json':
            attrs[field_name] = Column(JSON)
        if field_type == 'array':
            attrs[field_name] = Column(ARRAY(String))
        else:
            attrs[field_name] = Column(String)
            
    # Создаем класс таблицы динамически
    DynamicTable = type(table_name, (Base,), attrs)
    
    # Создаем таблицу в БД асинхронно
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    return DynamicTable


async def add_column_to_table(table_name: str, column_name: str, column_type: str):
    """
    Добавляет новый столбец в существующую таблицу
    
    Args:
        table_name (str): Имя таблицы
        column_name (str): Имя нового столбца
        column_type (str): Тип данных столбца ('string', 'datetime', 'integer', 'float', 'boolean', 'url', 'json', 'array')
    """
    # Определяем SQL тип данных на основе переданного типа
    sql_type = {
        'string': 'VARCHAR',
        'datetime': 'TIMESTAMP',
        'integer': 'BIGINT',
        'float': 'FLOAT',
        'boolean': 'BOOLEAN',
        'url': 'VARCHAR',
        'json': 'JSONB',
        'array': 'ARRAY(VARCHAR)',
        #массив
        'crm_multifield': 'ARRAY(VARCHAR)'
    }.get(column_type.lower())
    
    if not sql_type:
        # raise ValueError(f"Неподдерживаемый тип данных: {column_type}")
        sql_type='VARCHAR'
    # Формируем SQL запрос для добавления столбца
    alter_query = text(f"""
        ALTER TABLE {table_name} 
        ADD COLUMN IF NOT EXISTS {column_name} {sql_type}
    """)
    
    try:
        async with engine.begin() as conn:
            await conn.execute(alter_query)
            await conn.commit()
            print(f"Столбец {column_name} успешно добавлен в таблицу {table_name}")
    except Exception as e:
        print(f"Ошибка при добавлении столбца: {e}")
        raise e

async def drop_column_from_table(table_name: str, column_name: str):
    """
    Удаляет столбец из существующей таблицы
    
    Args:
        table_name (str): Имя таблицы
        column_name (str): Имя удаляемого столбца
    """
    # Формируем SQL запрос для удаления столбца
    drop_query = text(f"""
        ALTER TABLE {table_name} 
        DROP COLUMN IF EXISTS {column_name}
    """)
    
    try:
        async with engine.begin() as conn:
            await conn.execute(drop_query)
            await conn.commit()
            print(f"Столбец {column_name} успешно удален из таблицы {table_name}")
    except Exception as e:
        print(f"Ошибка при удалении столбца: {e}")
        raise e


async def get_table_column_types(table_name: str) -> dict:
    """
    Получает информацию о типах столбцов таблицы
    
    Args:
        table_name (str): Имя таблицы
        
    Returns:
        dict: Словарь с именами столбцов и их типами
    """
    query = text("""
        SELECT column_name, data_type, udt_name
        FROM information_schema.columns
        WHERE table_name = :table_name
    """)
    
    try:
        async with engine.begin() as conn:
            result = await conn.execute(query, {"table_name": table_name})
            columns_info = result.fetchall()
            
            # Создаем словарь с информацией о типах столбцов
            column_types = {}
            for col in columns_info:
                column_name = col[0]
                data_type = col[1]
                udt_name = col[2]
                
                # Определяем тип Python на основе типа PostgreSQL
                if data_type == 'ARRAY':
                    column_types[column_name] = 'array'
                elif udt_name in ('varchar', 'text', 'char'):
                    column_types[column_name] = 'string'
                elif udt_name in ('int2', 'int4', 'int8'):
                    column_types[column_name] = 'integer'
                elif udt_name in ('float4', 'float8', 'numeric'):
                    column_types[column_name] = 'float'
                elif udt_name == 'bool':
                    column_types[column_name] = 'boolean'
                elif udt_name in ('timestamp', 'timestamptz', 'date'):
                    column_types[column_name] = 'datetime'
                elif udt_name == 'jsonb':
                    column_types[column_name] = 'json'
                else:
                    column_types[column_name] = 'string'  # По уолчанию строка
                    
            return column_types
    except Exception as e:
        print(f"Ошибка при получении информации о столбцах: {e}")
        raise e

async def convert_value_to_type(value, target_type: str):
    """
    Преобразует знаение в указанный тип
    """
    if value is None or (isinstance(value, str) and not value):
        return None
        
    try:
        if target_type == 'string':
            return str(value)
        elif target_type == 'integer':
            return int(float(value)) if value else None
        elif target_type == 'float':
            return float(value) if value else None
        elif target_type == 'boolean':
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'y')
            return bool(value)
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
                return [value]
            elif isinstance(value, (list, tuple)):
                return list(value)
            return [str(value)]
        elif target_type == 'json':
            if isinstance(value, (dict, list)):
                return value
            return json.loads(value) if value else {}
        else:
            return str(value)
    except Exception as e:
        print(f"Ошибка преобразования значения {value} в тип {target_type}: {e}")
        return None

async def prepare_record_for_insert(data: dict, date_fields=None):
    """
    Подготавливает запись для вставки, обрабатывая специальные случаи
    
    Args:
        data (dict): Исходные данные
        date_fields (list): Список полей с датами
    Returns:
        dict: Подготовленные данные
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
            normalized_key = 'close_date'
        if normalized_key == 'ufcrmtask':
            normalized_key = 'uf_crm_task'
        # Пропускаем None значения
        if value is None:
            continue
            
        # Преобразуем пустые строки в None для дат
        if isinstance(value, str) and not value and key in date_fields:
            prepared_data[normalized_key] = None
        else:
            prepared_data[normalized_key] = value
    
    return prepared_data

async def insert_record(table_name: str, data: dict):
    """
    Вставляет запись в указанную таблицу с преобразованием типов данных

    Args:
        table_name (str): Имя таблицы
        data (dict): Словарь с данными для вставки
    """
    # Подготавливаем данные
    prepared_data = await prepare_record_for_insert(data)
    
    # Получаем информацию о типах столбцов
    column_types = await get_table_column_types(table_name)
    
    # Преобразуем имена колонок в нижний регистр в column_types
    column_types = {k.lower(): v for k, v in column_types.items()}
    
    # Преобразуем данные в соответствии с типами столбцов
    converted_data = {}
    for key, value in prepared_data.items():
        if key in column_types:
            converted_value = await convert_value_to_type(value, column_types[key])
            if converted_value is not None:  # Добавляем только не-None значения
                converted_data[key] = converted_value
    
    if not converted_data:
        raise ValueError("Нет данных для вставки после преобразования")
    
    # Формируем списки колонок и значений из словаря
    columns = list(converted_data.keys())
    
    # Формируем SQL запрос с именованными параметрами
    placeholders = [f':{col}' for col in columns]
    
    # Формируем SQL запрос
    insert_query = text(f"""
        INSERT INTO "{table_name}" ({', '.join(f'"{col}"' for col in columns)})
        VALUES ({', '.join(placeholders)})
        RETURNING record_id
    """)
    
    try:
        async with engine.begin() as conn:
            result = await conn.execute(insert_query, converted_data)
            await conn.commit()
            inserted_id = result.scalar()
            print(f"Запись успешно добавлена в таблицу {table_name} с id={inserted_id}")
            return inserted_id
    except Exception as e:
        print(f"Ошибка при добавлении записи: {e}")
        raise e

async def update_record(table_name: str, data: dict):
    """
    Обновляет запись в указанной таблице с преобразованием типов данных

    Args:
        table_name (str): Имя таблицы
        data (dict): Словарь с данными для обновления
    """
    # Подготавливаем данные
    prepared_data = await prepare_record_for_insert(data)
    
    # Получаем информацию о типах столбцов
    column_types = await get_table_column_types(table_name)
    
    # Преобразуем имена колонок в нижний регистр в column_types
    column_types = {k.lower(): v for k, v in column_types.items()}
    
    # Преоб��азуем данные в соответствии с типами столбцов
    converted_data = {}
    for key, value in prepared_data.items():
        if key in column_types:
            converted_value = await convert_value_to_type(value, column_types[key])
            if converted_value is not None:  # Добавляем только не-None значения
                converted_data[key] = converted_value
    
    if not converted_data:
        raise ValueError("Нет данных для обновления после преобразования")
    
    if 'bitrix_id' not in converted_data:
        raise ValueError("Отсутствует bitrix_id для обновления записи")
        
    # Формируем SET часть запроса, исключая bitrix_id из обновляемых полей
    update_pairs = []
    update_data = {}
    for key, value in converted_data.items():
        if key != 'bitrix_id':
            update_pairs.append(f'"{key}" = :{key}')
            update_data[key] = value
            
    # Добавляем bitrix_id для условия WHERE
    update_data['where_bitrix_id'] = converted_data['bitrix_id']
    
    # Формируем SQL запрос
    update_query = text(f"""
        UPDATE "{table_name}"
        SET {', '.join(update_pairs)}
        WHERE bitrix_id = :where_bitrix_id
        RETURNING record_id
    """)
    
    try:
        async with engine.begin() as conn:
            result = await conn.execute(update_query, update_data)
            await conn.commit()
            updated_id = result.scalar()
            if updated_id:
                print(f"Запись успешно обновлена в таблице {table_name} с id={updated_id}")
                return updated_id
            else:
                print(f"Запись с bitrix_id={converted_data['bitrix_id']} не найдена в таблице {table_name}")
                return None
    except Exception as e:
        print(f"Ошибка при обновлении записи: {e}")
        raise e

async def delete_record(table_name: str, bitrix_id: str):
    """
    Удаляет запись из указанной таблицы по bitrix_id

    Args:
        table_name (str): Имя таблицы
        bitrix_id (str): ID записи в Bitrix
    
    Returns:
        bool: True если запись была удалена, False если запись не найдена
    """
    # Формируем SQL запрос
    delete_query = text(f"""
        DELETE FROM "{table_name}"
        WHERE bitrix_id = :bitrix_id
        RETURNING record_id
    """)
    
    try:
        async with engine.begin() as conn:
            result = await conn.execute(delete_query, {"bitrix_id": bitrix_id})
            await conn.commit()
            deleted_id = result.scalar()
            
            if deleted_id:
                print(f"Запись с bitrix_id={bitrix_id} успешно удалена из таблицы {table_name}")
                return True
            else:
                print(f"Запись с bitrix_id={bitrix_id} не найдена в таблице {table_name}")
                return False
    except Exception as e:
        print(f"Ошибка при удалении записи: {e}")
        raise e

async def drop_table(table_name: str):
    """
    Удаляет таблицу

    Args:
        table_name (str): Имя таблицы для удаления
    """
    drop_query = text(f'DROP TABLE IF EXISTS "{table_name}"')
    
    try:
        async with engine.begin() as conn:
            await conn.execute(drop_query)
            await conn.commit()
            print(f"Таблица {table_name} успешно удалена")
    except Exception as e:
        print(f"Ошибка при удалении таблицы {table_name}: {e}")
        raise e

async def get_database_structure():
    """
    Получает структуру всех таблиц в базе данных, включая типы полей и пример данных
    """
    try:
        # Запрос для получения всех таблиц
        tables_query = text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        
        output = []
        
        async with engine.begin() as conn:
            # Получаем список таблиц
            tables_result = await conn.execute(tables_query)
            tables = tables_result.fetchall()
            
            for table in tables:
                table_name = table[0]
                output.append(f"\nТаблица: {table_name}")
                output.append("-" * 50)
                
                # Получаем информацию о столбцах
                columns_query = text("""
                    SELECT column_name, data_type, udt_name
                    FROM information_schema.columns
                    WHERE table_name = :table_name
                    ORDER BY ordinal_position
                """)
                
                columns_result = await conn.execute(columns_query, {"table_name": table_name})
                columns = columns_result.fetchall()
                
                # Выводим информацию о столбцах
                output.append("\nСтруктура:")
                for column in columns:
                    column_name, data_type, udt_name = column
                    output.append(f"{column_name}: {data_type}")
                
                # Получаем пример данных
                sample_query = text(f'SELECT * FROM "{table_name}" LIMIT 1')
                try:
                    sample_result = await conn.execute(sample_query)
                    sample_data = sample_result.fetchone()
                    
                    if sample_data:
                        output.append("\nПример данных:")
                        for col, value in zip(columns, sample_data):
                            output.append(f"{col[0]}: {value}")
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

# Изменяем main для тестирования
async def main():
    await get_database_structure()

if __name__ == '__main__':
    asyncio.run(main())
