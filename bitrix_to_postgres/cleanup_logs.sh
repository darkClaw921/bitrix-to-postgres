DO $$
DECLARE
    v_table_name text;
    v_deleted_count int;
BEGIN
    FOR v_table_name IN 
        SELECT t.table_name 
        FROM information_schema.tables t
        WHERE t.table_schema = 'public' 
        AND t.table_name LIKE '%_fields'
    LOOP
        EXECUTE format('
            WITH DuplicatesToDelete AS (
                SELECT record_id,
                       ROW_NUMBER() OVER (PARTITION BY bitrix_id ORDER BY record_id) as row_num
                FROM public.%I
                WHERE bitrix_id IS NOT NULL
            )
            DELETE FROM public.%I
            WHERE record_id IN (
                SELECT record_id 
                FROM DuplicatesToDelete 
                WHERE row_num > 1
            )', v_table_name, v_table_name);
            
        GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
        
        RAISE NOTICE 'Удалены дубликаты из таблицы: %. Удалено записей: %', v_table_name, v_deleted_count;
    END LOOP;
END $$;