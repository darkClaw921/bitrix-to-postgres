from postgresWork import PostgresClient
import asyncio

async def create_tables():
    client = PostgresClient(
        dbname='postgres',
        user='postgres',
        password='postgres',
        host='postgres-2'
    )
    await client.create_tables()

if __name__ == "__main__":
    asyncio.run(create_tables()) 