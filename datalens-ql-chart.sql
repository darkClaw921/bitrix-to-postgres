WITH target_companies AS (
    -- Выбираем целевые компании
    SELECT 
        c.bitrix_id,
        c.title as company_name,
        c.assigned_by_id,
        CONCAT(
            COALESCE(u.last_name, ''), 
            ' ',
            COALESCE(u.name, ''),
            ' ',
            COALESCE(u.second_name, '')
        ) as manager_name
    FROM company_fields c
    LEFT JOIN user_fields u ON c.assigned_by_id = u.bitrix_id
    WHERE c.uf_crm_1665145412270 = '803'  -- фильтр целевых компаний
),
companies_with_active_tasks AS (
    -- Компании, у которых есть активные задачи (статус < 5)
    SELECT DISTINCT 
        SUBSTRING(unnest(uf_crm_task), 4)::varchar as company_id
    FROM task_fields
    WHERE uf_crm_task IS NOT NULL
    AND uf_crm_task::text LIKE '%CO_%'
    AND CAST(status AS INTEGER) < 5  -- только активные задачи
)

SELECT 
    tc.bitrix_id as "ID компании",
    tc.company_name as "Название компании",
    tc.manager_name as "Ответственный менеджер",
    CASE 
        WHEN cwt.company_id IS NULL THEN 'Нет активных задач'
        ELSE 'Есть активные задачи'
    END as "Статус задач"
FROM target_companies tc
LEFT JOIN companies_with_active_tasks cwt ON tc.bitrix_id::varchar = cwt.company_id
WHERE cwt.company_id IS NULL  -- оставляем только компании без активных задач
ORDER BY tc.company_name;