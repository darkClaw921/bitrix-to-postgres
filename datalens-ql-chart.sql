-- Группировка по месяцам
SELECT 
    date_trunc('day', d.date_create::timestamp) as creation_date,
    COUNT(*) as total_leads,
    -- Считаем проигранные сделки только в интервале closedate
    SUM(CASE 
        WHEN d.stage_semantic_id = 'F' 
        AND d.closedate::timestamp >= {{interval_from}}
        AND d.closedate::timestamp <= {{interval_to}}
        THEN 1 
        ELSE 0 
    END) as rejected_leads,
    -- Считаем обработанные заявки (те, которые не в начальном статусе)
    SUM(CASE WHEN d.stage_id != 'NEW' THEN 1 ELSE 0 END) as processed_leads,
    -- Процент обработанных заявок
    ROUND(
        (SUM(CASE WHEN d.stage_id != 'NEW' THEN 1 ELSE 0 END)::float / 
        NULLIF(COUNT(*), 0) * 100)::numeric, 
        2
    ) as processed_percentage,
    -- Информация о менеджере
    d.assigned_by_id,
    -- Формируем полное имя менеджера
    CONCAT(
        COALESCE(u.last_name, ''), 
        ' ',
        COALESCE(u.name, ''),
        ' ',
        COALESCE(u.second_name, '')
    ) as manager_name,
    COUNT(*) as leads_per_manager
FROM deal_fields d
LEFT JOIN user_fields u ON d.assigned_by_id = u.bitrix_id
WHERE 
    d.date_create IS NOT NULL
    AND d.date_create::timestamp >= {{interval_from}}
    AND d.date_create::timestamp <= {{interval_to}}
GROUP BY 
    date_trunc('day', d.date_create::timestamp),
    d.assigned_by_id,
    u.last_name,
    u.name,
    u.second_name
ORDER BY 
    creation_date DESC,
    leads_per_manager DESC;
