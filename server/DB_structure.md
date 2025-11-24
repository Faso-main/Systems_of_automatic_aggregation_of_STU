Отличная идея! Вот команды для вывода полной структуры БД:

## 1. Получение информации о таблицах и схемах

```sql
-- Список всех таблиц в схеме store
SELECT 
    table_name,
    table_type,
    row_estimate,
    pg_size_pretty(total_bytes) AS size
FROM information_schema.tables 
JOIN (
    SELECT 
        schemaname, 
        tablename,
        SUM(pg_total_relation_size(schemaname||'.'||tablename)) as total_bytes
    FROM pg_tables 
    WHERE schemaname = 'store'
    GROUP BY schemaname, tablename
) AS sizes ON table_name = sizes.tablename
WHERE table_schema = 'store'
ORDER BY table_name;
```

## 2. Структура всех таблиц с колонками

```sql
-- Детальная структура всех таблиц
SELECT 
    t.table_name,
    c.column_name,
    c.data_type,
    c.is_nullable,
    c.column_default,
    tc.constraint_type,
    kcu.column_name as key_column
FROM information_schema.tables t
JOIN information_schema.columns c ON t.table_name = c.table_name
LEFT JOIN information_schema.key_column_usage kcu ON c.table_name = kcu.table_name AND c.column_name = kcu.column_name
LEFT JOIN information_schema.table_constraints tc ON kcu.constraint_name = tc.constraint_name
WHERE t.table_schema = 'store'
ORDER BY t.table_name, c.ordinal_position;
```

## 3. Внешние ключи и связи

```sql
-- Все внешние ключи в базе
SELECT
    tc.table_name, 
    kcu.column_name, 
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    tc.constraint_name
FROM information_schema.table_constraints AS tc 
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY' 
    AND tc.table_schema = 'store'
ORDER BY tc.table_name;
```

## 4. Индексы

```sql
-- Все индексы в схеме store
SELECT 
    tablename,
    indexname,
    indexdef
FROM pg_indexes 
WHERE schemaname = 'store'
ORDER BY tablename, indexname;
```

## 5. Триггеры

```sql
-- Триггеры в базе
SELECT 
    trigger_name,
    event_manipulation,
    event_object_table,
    action_timing,
    action_statement
FROM information_schema.triggers 
WHERE trigger_schema = 'store'
ORDER BY event_object_table;
```

## 6. Последовательности (sequences)

```sql
-- Последовательности для автоинкремента
SELECT 
    sequence_schema,
    sequence_name,
    data_type,
    start_value,
    increment
FROM information_schema.sequences 
WHERE sequence_schema = 'store'
ORDER BY sequence_name;
```

## 7. Права доступа пользователей

```sql
-- Права пользователей на таблицы
SELECT 
    grantee,
    table_schema,
    table_name,
    privilege_type
FROM information_schema.table_privileges 
WHERE table_schema = 'store'
ORDER BY grantee, table_name;
```

## 8. Компактный обзор всей структуры

```sql
-- Компактный обзор всей БД
SELECT 
    'Tables' as type,
    table_name as name,
    '' as details
FROM information_schema.tables 
WHERE table_schema = 'store'

UNION ALL

SELECT 
    'Columns' as type,
    table_name as name,
    STRING_AGG(column_name || ' ' || data_type, ', ') as details
FROM information_schema.columns 
WHERE table_schema = 'store'
GROUP BY table_name

UNION ALL

SELECT 
    'Indexes' as type,
    tablename as name,
    STRING_AGG(indexname, ', ') as details
FROM pg_indexes 
WHERE schemaname = 'store'
GROUP BY tablename

ORDER BY type, name;
```

## 9. Экспорт полной схемы БД

```sql
-- Генерация SQL для воссоздания схемы (без данных)
SELECT 
    '-- Tables' as sql_line
UNION ALL
SELECT 
    'CREATE TABLE ' || table_name || ' (' || 
    STRING_AGG(
        column_name || ' ' || data_type || 
        CASE WHEN is_nullable = 'NO' THEN ' NOT NULL' ELSE '' END ||
        CASE WHEN column_default IS NOT NULL THEN ' DEFAULT ' || column_default ELSE '' END,
        ', '
    ) || ');' as sql_line
FROM information_schema.columns 
WHERE table_schema = 'store'
GROUP BY table_name

UNION ALL
SELECT '-- Foreign Keys' as sql_line
UNION ALL
SELECT 
    'ALTER TABLE ' || tc.table_name || 
    ' ADD CONSTRAINT ' || tc.constraint_name ||
    ' FOREIGN KEY (' || kcu.column_name || ') REFERENCES ' ||
    ccu.table_name || '(' || ccu.column_name || ');' as sql_line
FROM information_schema.table_constraints AS tc 
JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'store'

UNION ALL
SELECT '-- Indexes' as sql_line
UNION ALL
SELECT indexdef || ';' as sql_line
FROM pg_indexes 
WHERE schemaname = 'store'
ORDER BY sql_line;
```

## 10. Проверка данных (статистика)

```sql
-- Статистика по данным в таблицах
SELECT 
    table_name,
    (SELECT COUNT(*) FROM store.users) as users_count,
    (SELECT COUNT(*) FROM store.categories) as categories_count,
    (SELECT COUNT(*) FROM store.products) as products_count,
    (SELECT COUNT(*) FROM store.procurements) as procurements_count,
    (SELECT COUNT(*) FROM store.procurement_products) as procurement_products_count,
    (SELECT COUNT(*) FROM store.procurement_participants) as participants_count;
```

## Ключевые команды для быстрого доступа:

```bash
# Подключение к БД
psql -U store_app1 -d online_store1 -h localhost

# Экспорт структуры в файл
pg_dump -U store_app1 -d online_store1 -h localhost --schema-only -s > schema.sql

# Экспорт структуры с данными
pg_dump -U store_app1 -d online_store1 -h localhost > full_dump.sql
```

Эти команды дадут полное представление о структуре БД для работы в других чатах! 🗃️