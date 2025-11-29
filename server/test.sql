

### Как быстро проверить, что логика работает

1. Посмотреть состояние категории **до** вставки:

```sql
SELECT id, has_new_items, new_items_count
FROM product_category
WHERE id = 793286151;  -- подставь любую существующую
```

2. Вставить тестовый товар в эту категорию:

```sql
INSERT INTO product (id, category_id, name, producer, country)
VALUES (9999999999, 793286151, 'ТЕСТОВЫЙ ТОВАР ДЛЯ ТРИГГЕРА', 'TEST', 'TESTLAND');
```

3. Проверить категорию **после**:

```sql
SELECT id, has_new_items, new_items_count
FROM product_category
WHERE id = 793286151;
```

Если всё ок — `has_new_items` станет `true`, а `new_items_count` увеличится минимум до `1`.

4. Можно удалить тестовый товар и убедиться, что триггер DELETE тоже отработал:

```sql
DELETE FROM product WHERE id = 9999999999;

SELECT id, has_new_items, new_items_count
FROM product_category
WHERE id = 793286151;
```

---

Если хочешь, следующим шагом можем:

* добавить в твой `server.js` поля `hasNewItems` и `newItemsCount` в ответ `/api/categories`;
* и визуально показать их во фронте (бейдж «Новые N» и фильтр «есть новые товары»).
