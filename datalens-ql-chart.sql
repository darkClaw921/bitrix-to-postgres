


-- Получение количества активных задач для каждого менеджера
WITH active_tasks AS (
    SELECT 
        responsible_id,
        COUNT(DISTINCT bitrix_id) as active_tasks_count
    FROM task_fields
    WHERE 
        CAST(status AS INTEGER) < 5
        AND date_start::timestamp >= {{interval_from}}
        AND date_start::timestamp <= {{interval_to}}
    GROUP BY responsible_id
)

SELECT 
    -- Базовая информация о менеджере
    d.assigned_by_id,
    CONCAT(
        COALESCE(u.last_name, ''), 
        ' ',
        COALESCE(u.name, ''),
        ' ',
        COALESCE(u.second_name, '')
    ) as "Менеджер",
    
    -- Получено заявок (UF_CRM_H_C3_NEW)
    COUNT(DISTINCT 
        CASE 
            WHEN d.uf_crm_h_c3_new::timestamp >= {{interval_from}}
            AND d.uf_crm_h_c3_new::timestamp <= {{interval_to}}
            THEN d.bitrix_id 
        END
    ) as "Получено заявок",
    
    -- КП отправлено (UF_CRM_H_C3_EXECUTIN)
    COUNT(DISTINCT 
        CASE 
            WHEN d.uf_crm_h_c3_executin::timestamp >= {{interval_from}}
            AND d.uf_crm_h_c3_executin::timestamp <= {{interval_to}}
            THEN d.bitrix_id
        END
    ) as "КП отправлено",
    
    -- КП согласовано (UF_CRM_H_C3_UC_C4S78)
    COUNT(DISTINCT 
        CASE 
            WHEN d.uf_crm_h_c3_uc_c4s78::timestamp >= {{interval_from}}
            AND d.uf_crm_h_c3_uc_c4s78::timestamp <= {{interval_to}}
            THEN d.bitrix_id
        END
    ) as "КП согласовано",
    
    -- Количество отказов
    COUNT(DISTINCT 
        CASE 
            WHEN d.stage_semantic_id = 'F'
            AND d.closedate::timestamp >= {{interval_from}}
            AND d.closedate::timestamp <= {{interval_to}}
            THEN d.bitrix_id
        END
    ) as "Количество отказов",
    
    -- Результативные звонки (холодная воронка)
    COUNT(DISTINCT 
        CASE 
            WHEN d.uf_crm_h_1::timestamp >= {{interval_from}}
            AND d.uf_crm_h_1::timestamp <= {{interval_to}}
            AND CAST(d.category_id AS TEXT) = '0'
            THEN d.bitrix_id
        END
    ) as "Результативные звонки",
    
    -- План и факт по продажам
    CAST(MAX(di.ufcrm7_1731586319) AS NUMERIC) as "План по продажам",
    CAST(MAX(di.ufcrm7_1731586774) AS NUMERIC) as "Факт по продажам",
    
    -- Процент выполнения плана с индикатором
    CASE 
        WHEN CAST(MAX(di.ufcrm7_1731586319) AS NUMERIC) > 0 THEN
            ROUND(
                (CAST(MAX(di.ufcrm7_1731586774) AS NUMERIC) / CAST(MAX(di.ufcrm7_1731586319) AS NUMERIC) * 100)::numeric, 
                2
            )
        ELSE 0
    END as "Процент выполнения плана",
    
    -- Индикатор выполнения плана
    CASE 
        WHEN CAST(MAX(di.ufcrm7_1731586319) AS NUMERIC) > 0 THEN
            CASE 
                WHEN (CAST(MAX(di.ufcrm7_1731586774) AS NUMERIC) / CAST(MAX(di.ufcrm7_1731586319) AS NUMERIC) * 100) >= 100 THEN '🟢'
                WHEN (CAST(MAX(di.ufcrm7_1731586774) AS NUMERIC) / CAST(MAX(di.ufcrm7_1731586319) AS NUMERIC) * 100) >= 70 THEN '🟡'
                ELSE '🔴'
            END
        ELSE '⚪'
    END as " ",
    
    -- Количество активных задач
    COALESCE(t.active_tasks_count, 0) as "Активные задачи",
    -- Получено заявок (холодники)
    COUNT(DISTINCT 
        CASE 
            WHEN d.uf_crm_h_c3_new::timestamp >= {{interval_from}}
            AND d.uf_crm_h_c3_new::timestamp <= {{interval_to}}
            AND d.assigned_by_id::integer = ANY(ARRAY[49, 109, 111])  -- ID холодников
            THEN d.bitrix_id 
        END
    ) as "Получено заявок (холодники)",
    
    -- Запущено (только ключевики)
    COUNT(DISTINCT 
        CASE 
            WHEN d.uf_crm_h_c3_won::timestamp >= {{interval_from}}
            AND d.uf_crm_h_c3_won::timestamp <= {{interval_to}}
            AND d.assigned_by_id::integer = ANY(ARRAY[9, 95])  -- ID ключевиков
            THEN d.bitrix_id
        END
    ) as "Запущено (ключевики)"

FROM deal_fields d
LEFT JOIN user_fields u ON d.assigned_by_id = u.bitrix_id
LEFT JOIN dynamic_item_fields_1036 di ON d.assigned_by_id = di.assignedbyid
LEFT JOIN active_tasks t ON d.assigned_by_id = t.responsible_id
WHERE 
    d.date_create IS NOT NULL
    -- AND u.active = 'Y'
    AND (
        u.uf_department ='[5]'
    )
GROUP BY 
    d.assigned_by_id,
    u.last_name,
    u.name,
    u.second_name,
    t.active_tasks_count
ORDER BY 
    -- u.active DESC,
    "Получено заявок" DESC;





WITH total_sales AS (
    SELECT 
        SUM(CAST(di.ufcrm7_1731586319 AS NUMERIC)) as total_plan,
        SUM(CAST(di.ufcrm7_1731586774 AS NUMERIC)) as total_fact
    FROM dynamic_item_fields_1036 di
)

SELECT 
    total_plan,
    total_fact,
    CASE 
        WHEN total_plan > 0 THEN
            ROUND((total_fact / total_plan * 100)::numeric, 2)
        ELSE 0
    END as "Общий процент выполнения плана",
    
    -- Индикатор выполнения плана в виде прогресс-бара
    CASE 
        WHEN total_plan > 0 THEN
            REPEAT('█', LEAST(10, CAST(ROUND(total_fact / total_plan * 10) AS INTEGER))) || 
            REPEAT('░', GREATEST(0, 10 - CAST(ROUND(total_fact / total_plan * 10) AS INTEGER)))
        ELSE '░░░░░░░░░░'
    END as "Индикатор прогресса"

FROM total_sales;



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


-- Запрос 1: Общее количество целевых компаний без активных задач
WITH target_companies AS (
    SELECT c.bitrix_id
    FROM company_fields c
    WHERE c.uf_crm_1665145412270 = '803'
),
companies_with_active_tasks AS (
    SELECT DISTINCT 
        SUBSTRING(unnest(uf_crm_task), 4)::varchar as company_id
    FROM task_fields
    WHERE uf_crm_task IS NOT NULL
    AND uf_crm_task::text LIKE '%CO_%'
    AND CAST(status AS INTEGER) < 5
)

SELECT 
    COUNT(*) as "Всего целевых компаний без активных задач"
FROM target_companies tc
LEFT JOIN companies_with_active_tasks cwt ON tc.bitrix_id::varchar = cwt.company_id
WHERE cwt.company_id IS NULL;