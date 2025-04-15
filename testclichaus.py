import clickhouse_connect
from dotenv import load_dotenv
import os

load_dotenv()

client = clickhouse_connect.get_client(
    host=os.getenv('CLICKHOUSE_HOST'),
    username=os.getenv('CLICKHOUSE_USERNAME'),
    password=os.getenv('CLICKHOUSE_PASSWORD'),
)

client.query(
    '''
    CREATE TABLE IF NOT EXISTS test_table 
    (
        id UInt8,
        name String
    ) 
    ENGINE = MergeTree()
    ORDER BY id
    '''
)