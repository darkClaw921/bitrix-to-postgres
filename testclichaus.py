# from datetime import datetime
import clickhouse_connect
from dotenv import load_dotenv
import os

load_dotenv()

client = clickhouse_connect.get_client(
    host=os.getenv('CLICKHOUSE_HOST'),
    username=os.getenv('CLICKHOUSE_USERNAME'),
    password=os.getenv('CLICKHOUSE_PASSWORD'),
)

def get_tables_columns(table_name):
    query = f"DESCRIBE TABLE {table_name}"
    result = client.query(query)
    return result.result_rows

def drop_tables():
        #удаляем все существующие таблицы

    tables = client.query('SHOW TABLES')
    print('Таблицы в ClickHouse:')
    print(tables.result_rows)
    for table in tables.result_rows:
        print(table[0])
        client.query(f'DROP TABLE IF EXISTS {table[0]}')
    # client.query(f'DROP TABLE IF EXISTS deal_fields')
def add_new_column(table_name, column_name, column_type,comment:str=None, name:str=None, after:str=None):
    query = f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_name} {column_type}"
    if comment:
        query += f" COMMENT '{comment}'"
    if name:
        query += f" AS {name}"
    if after:
        query += f" AFTER {after}"
    client.query(query)

def get_values_from_table(table_name):
    query = f"SELECT * FROM {table_name}"
    result = client.query(query)
    return result.result_rows

def insert_record(table_name, data):
    columns = list(data.keys())
    values = list(data.values())
    
    # Формируем SQL запрос с плейсхолдерами для значений
    column_str = ', '.join(columns)

    placeholders = ', '.join(['%s' for _ in columns])
    query = f"INSERT INTO {table_name} ({column_str}) VALUES ({placeholders})"
    
    print(f"Запрос: {query}")
    print(f"Значения: {values}")
    
    # Передаем данные как параметр parameters
    client.query(query, parameters=values)

query="""INSERT INTO deal_fields (bitrix_id, `название`, `тип`, `стадия_сделки`, `вероятность`, `валюта`, `сумма`, `is_manual_opportunity`, `ставка_налога`, `компания`, `контакт`, `дата_начала`, `дата_завершения`, `ответственный`, `кем_создана`, `кем_изменена`, `дата_создания`, `дата_изменения`, `доступна_для_всех`, `закрыта`, `воронка`, `группа_стадии`, `новая_сделка`, `регулярная_сделка`, `повторная_сделка`, `повторное_обращение`, `moved_by_id`, `moved_time`, `last_activity_time`, `договоры`, `last_activity_by`, `сумма_с_ндс`, `сделки_с_поставщиками`, `ответственный_оо`, `прямая_поставка`, `дата_поставки_по_договору`, `направление_сделки_(к)`, `уведомление_клиента_об_отгрузке_со_склада_поставщика`, `добавить_ндс`, `шм_и_пнр`, `акт_пнр_с_замечаниями`, `ответственный_оуп`, `акт_вр`, `описание_в_названии_сделки`, `дата_отгрузки_план`, `подчиненные_сделки_пк`, `чек-лист`, `цфо`, `наше_юр._лицо`, `оборудование`, `признак`, `проверкабп`, `id_записи_в_списке_группы_компаний`, `отгрузки`, `компания-конечный_пользователь`, `срок_поставки_до_(например:_2_(двух)_недель)_`, `сообщение_об_изменении_не_позднее_(например:_3_(трех)_дней)`, `плановая_маржинальность,_%`, `наблюдатели_в_задачах`, `дата_окончания_работ._факт`, `сделка_с_клиентом`, `уведомление_клиента_об_отгрузке_со_склада_производителя`, `рамочный_договор`, `отгрузка_расходных_материалов,_зип_по_документам`, `end_user`, `сделка_консолидатора`, `специальные_условия_договора`, `ндс`, `частичная_отгрузка`, `дата_перехода_в_текущую_стадию`, `кол-во_н.ч._на_инструктаж`, `кол-во_н.ч._на_шм_и_пнр`, created_date, record_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""

query2="""INSERT INTO deal_fields (bitrix_id, `название`, `тип`, `стадия_сделки`, `валюта`, `сумма`, `is_manual_opportunity`, `ставка_налога`, `компания`, `контакт`, `дата_начала`, `дата_завершения`, `ответственный`, `кем_создана`, `кем_изменена`, `дата_создания`, `дата_изменения`, `доступна_для_всех`, `закрыта`, `воронка`, `группа_стадии`, `новая_сделка`, `регулярная_сделка`, `повторная_сделка`, `повторное_обращение`, `moved_by_id`, `moved_time`, `last_activity_time`, `last_activity_by`, `сумма_с_ндс`, `сделки_с_поставщиками`, `ответственный_оо`, `прямая_поставка`, `направление_сделки_(к)`, `добавить_ндс`, `шм_и_пнр`, `акт_пнр_с_замечаниями`, `акт_вр`, `подчиненные_сделки_пк`, `цфо`, `наше_юр._лицо`, `оборудование`, `признак`, `проверкабп`, `id_записи_в_списке_группы_компаний`, `отгрузки`, `срок_поставки_до_(например:_2_(двух)_недель)_`, `сообщение_об_изменении_не_позднее_(например:_3_(трех)_дней)`, `наблюдатели_в_задачах`, `сделка_с_клиентом`, `рамочный_договор`, `кс`, `гоз`, `порядок_оплаты`, `!(для_шаблона_акт_до)_ндс`, `отгрузка_расходных_материалов,_зип_по_документам`, `end_user`, `44-фз`, `223-фз`, `сделка_консолидатора`, `специальные_условия_договора`, `ндс`, `дата_перехода_в_текущую_стадию`, created_date, record_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""

def execute_query_string(query:str):
    print(query)
    result = client.raw_query(query)
    # return result.result_rows

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
        elif isinstance(val, datetime.datetime):
            # Форматируем datetime в строку для SQL
            formatted_values.append(f"'{val.strftime('%Y-%m-%d %H:%M:%S')}'")
        else:
            formatted_values.append(f"'{str(val)}'")
    
    # Заменяем все %s на соответствующие значения
    parts = query.split('%s')
    result = parts[0]
    for i in range(len(formatted_values)):
        result += formatted_values[i] + (parts[i+1] if i+1 < len(parts) else '')
    
    return result
import datetime
def update_record(table_name, data, is_mapping=False):
    

    query = r"""
INSERT INTO deal_fields (bitrix_id, "название", "тип", "стадия_сделки", "вероятность", "валюта", "сумма", "is_manual_opportunity", "ставка_налога", "компания", "контакт", "дата_начала", "дата_завершения", "ответственный", "кем_создана", "кем_изменена", "дата_создания", "дата_изменения", "доступна_для_всех", "закрыта", "воронка", "группа_стадии", "новая_сделка", "регулярная_сделка", "повторная_сделка", "повторное_обращение", "moved_by_id", "moved_time", "last_activity_time", "last_activity_by", "сумма_с_ндс", "сделки_с_поставщиками", "прямая_поставка", "направление_сделки_(к)", "уведомление_клиента_об_отгрузке_со_склада_поставщика", "добавить_ндс", "шм_и_пнр", "акт_пнр_с_замечаниями", "акт_вр", "описание_в_названии_сделки", "подчиненные_сделки_пк", "чек-лист", "цфо", "наше_юр._лицо", "оборудование", "признак", "проверкабп", "id_записи_в_списке_группы_компаний", "отгрузки", "компания-конечный_пользователь", "срок_поставки_до_(например:_2_(двух)_недель)_", "сообщение_об_изменении_не_позднее_(например:_3_(трех)_дней)", "плановая_маржинальность,_%", "наблюдатели_в_задачах", "сделка_с_клиентом", "уведомление_клиента_об_отгрузке_со_склада_производителя", "рамочный_договор", "отгрузка_расходных_материалов,_зип_по_документам", "end_user", "сделка_консолидатора", "специальные_условия_договора", "ндс", "дата_перехода_в_текущую_стадию", "кол-во_н.ч._на_инструктаж", "кол-во_н.ч._на_шм_и_пнр", created_date, record_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

    values=['18304', 'Геоптикс   описание 66', 'SALE', 'NEW', 10, 'RUB', 65160.0, 'N', 10860.0, '27920', '65588', datetime.datetime(2025, 4, 18, 0, 0), datetime.datetime(2025, 4, 25, 0, 0), '208', '208', '1', datetime.datetime(2025, 4, 18, 9, 33, 27), datetime.datetime(2025, 4, 18, 9, 33, 53), 'Y', 'N', 'Продажи', 'P', 'Y', 'N', 'N', 'N', '208', datetime.datetime(2025, 4, 18, 9, 33, 27), datetime.datetime(2025, 4, 18, 9, 33, 27), '208', 65160.0, '[]', 0, '5643', '5665', 0, 0, 0, 0, 'описание 66', '[]', '18268', '37877', '29189', '[]', '[]', 0, 53328, '[]', '2246', '2 (двух) недель', '3 (трех) дней', 44.0, '[]', '[]', '12199', 0, '[]', '[]', 0, '[]', '10860|RUB', datetime.datetime(2025, 4, 18, 0, 0), 0.0, 0.0, datetime.datetime(2025, 4, 23, 17, 2, 23, 540363), 63]
    


# Получаем преобразованный запрос
    formatted_query = replace_placeholders(query, values)

    # client.query(query=query, parameters=values)
    client.command(formatted_query)

def create_table(table_name):
    query = f"""CREATE TABLE IF NOT EXISTS {table_name} (id Int32, "тест" String, type String) ENGINE = MergeTree() ORDER BY id"""
    client.raw_query(query)

def delete_all_records(table_name):
    query = f"ALTER TABLE {table_name} DELETE WHERE 1=1"
    client.raw_query(query)

if __name__ == '__main__':
    from pprint import pprint
    # create_table('deal_fields2')
    # a=get_tables_columns('deal_fields2')
    # pprint(a)
    # insert_record('deal_fields2', {'id':1, "тест":'test', 'type':'test'})
    # 1/0
    # client.query(f'DROP TABLE IF EXISTS company_enumerate_fields')
    # execute_query_string(query2)
    # delete_all_records('deal_fields')
    drop_tables()
    1/0
    # # add_new_column(table_name='task_comment_fields',
    # #                column_name='test_odlas',
    # #                column_type='String',
    # # #                after='post_message')
    # a=get_tables_columns('deal_fields')
    # pprint(a)
    # b=get_values_from_table('deal_fields')
    # pprint(b)
    # insert_record('deal_fields', {'"название"':'test'})
    name='"tes123"'
    # name=name.replace('"','')
    update_record('deal_fields', {'bitrix_id':18270, "название":name})
    b=get_values_from_table('deal_fields')
    pprint(b)