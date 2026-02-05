#!/bin/bash
set -e

# Create supabase_admin user with the same password as postgres
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create supabase_admin user if it doesn't exist
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = 'supabase_admin') THEN
            CREATE USER supabase_admin WITH PASSWORD '${POSTGRES_PASSWORD}' SUPERUSER;
            RAISE NOTICE 'User supabase_admin created';
        ELSE
            RAISE NOTICE 'User supabase_admin already exists';
        END IF;
    END
    \$\$;

    -- Grant all privileges to supabase_admin
    GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB} TO supabase_admin;
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO supabase_admin;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO supabase_admin;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO supabase_admin;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO supabase_admin;
EOSQL

echo "Database initialization completed: supabase_admin user configured"
