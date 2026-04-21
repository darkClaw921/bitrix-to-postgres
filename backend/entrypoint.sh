#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting Bitrix Sync Service...${NC}"

# Wait for database to be ready using Python
echo -e "${YELLOW}Waiting for database...${NC}"

max_attempts=30
attempt=0

echo "DATABASE_URL=${DATABASE_URL:-(empty)}"

while [ $attempt -lt $max_attempts ]; do
    if python -c "
import asyncio, sys, urllib.parse
url = '${DATABASE_URL}'
if not url:
    print('ERROR: DATABASE_URL is empty')
    sys.exit(1)
async def check():
    if url.startswith('mysql'):
        import aiomysql
        p = urllib.parse.urlparse(url.replace('+aiomysql', ''))
        conn = await aiomysql.connect(
            host=p.hostname, port=p.port or 3306,
            user=p.username, password=urllib.parse.unquote(p.password or ''),
            db=p.path.lstrip('/'), connect_timeout=5)
        conn.close()
    else:
        import asyncpg
        pg_url = url.replace('+asyncpg', '').replace('postgresql://', 'postgres://')
        conn = await asyncio.wait_for(asyncpg.connect(pg_url), timeout=5)
        await conn.execute('SELECT 1')
        await conn.close()
asyncio.run(check())
"; then
        echo -e "${GREEN}Database is ready!${NC}"
        break
    fi

    attempt=$((attempt + 1))
    echo -e "${YELLOW}Waiting for database... (attempt $attempt/$max_attempts)${NC}"
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "${RED}Failed to connect to database after $max_attempts attempts${NC}"
    exit 1
fi

# Run Alembic migrations
echo -e "${YELLOW}Running database migrations...${NC}"
if alembic upgrade head; then
    echo -e "${GREEN}Migrations completed successfully!${NC}"
else
    echo -e "${RED}Migration failed!${NC}"
    exit 1
fi

# Start the application
echo -e "${GREEN}Starting application...${NC}"
exec "$@"
