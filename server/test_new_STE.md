```bash
psql -h localhost -U th3_app -d th3_db
```

---

## Шаг 1. Пометить все текущие товары как обученные

Сделаем так, чтобы *все существующие* СТЕ стали `is_used_for_training = true`:

```sql
UPDATE product
SET
  is_used_for_training = TRUE,
  training_used_at     = NOW()
WHERE is_used_for_training = FALSE;
```

Проверим, что необученных больше нет:

```sql
SELECT
  COUNT(*) AS total_products,
  SUM(CASE WHEN is_used_for_training = FALSE THEN 1 ELSE 0 END) AS untrained_products
FROM product;
```

Ожидаем `untrained_products = 0`.

---

## Шаг 2. Выберем категорию для теста

Ты уже показывал товары для категории `793370560` (колготки), давай её и возьмём.

Проверим, сколько там сейчас товаров и что все они обучены:

```sql
SELECT
  COUNT(*) AS total,
  SUM(CASE WHEN is_used_for_training = FALSE THEN 1 ELSE 0 END) AS untrained
FROM product
WHERE category_id = 793370560;
```

Ожидаем `untrained = 0`.

---

## Шаг 3. Добавляем тестовый товар в эту категорию

Сначала узнаем свободный ID (возьмём `max(id) + 1`):

```sql
SELECT MAX(id) FROM product;
```

Допустим, вернуло `19680000`.
Придумаем тестовый ID, например `19690000` (любой больше max, главное — уникальный).

Теперь добавляем тестовый товар:

```sql
INSERT INTO product (
  id,
  category_id,
  name,
  producer,
  country,
  image_url,
  raw_specs
) VALUES (
  39085884,                        -- подставь свой ID > max(id)
  793370560,                       -- тестируемую категорию
  'ТЕСТОВЫЕ КОЛГОТКИ ДЛЯ ОБУЧЕНИЯ',
  'Тестовый производитель',
  'РОССИЯ',
  NULL,
  '"Размер: TEST; Цвет: тестовый; Состав: 100% тест"'::jsonb
);
```

⚠️ Важно: `is_used_for_training` и `created_at/imported_at` не указываем, т.к.:

* `is_used_for_training` по дефолту `false` (как раз то, что надо);
* даты сами проставятся `now()`.

Проверим, что он добавился и помечен как **не обученный**:

```sql
SELECT id, category_id, name, is_used_for_training, training_used_at
FROM product
WHERE id = 39085884;
```

Ожидаем `is_used_for_training = f`, `training_used_at = NULL`.

---

## Шаг 4. Проверим агрегат по категории (SQL, без API)

Посмотрим, как теперь смотрится категория `793370560`:

```sql
SELECT
  c.id,
  c.name,
  COUNT(p.*) AS total_products,
  SUM(CASE WHEN p.is_used_for_training = FALSE THEN 1 ELSE 0 END) AS untrained_products
FROM product_category c
LEFT JOIN product p ON p.category_id = c.id
WHERE c.id = 793370560
GROUP BY c.id, c.name;
```

Ожидаем:

* `total_products` = старое количество + 1,
* `untrained_products` = **1**.

Это как раз то, что сейчас показывает твой бэкенд в полях `hasUntrainedItems` / `untrainedItemsCount`.

Если хочешь проверить, что бэкенд видит то же самое:

```bash
curl -s https://faso312.ru/api/categories/793370560 | jq .
```

В ответе у категории должно быть:

```json
{
  "hasUntrainedItems": true,
  "untrainedItemsCount": 1
}
```

---

## Шаг 5. Удалим тестовый товар

Когда убедились, что всё работает как задумано, просто удаляем его:

```sql
DELETE FROM product
WHERE id = 19690000;
```

Проверим, что его больше нет:

```sql
SELECT *
FROM product
WHERE id = 19690000;
```

И ещё раз убедимся, что в категории опять нет необученных:

```sql
SELECT
  c.id,
  c.name,
  COUNT(p.*) AS total_products,
  SUM(CASE WHEN p.is_used_for_training = FALSE THEN 1 ELSE 0 END) AS untrained_products
FROM product_category c
LEFT JOIN product p ON p.category_id = c.id
WHERE c.id = 793370560
GROUP BY c.id, c.name;
```

Ожидаем `untrained_products = 0`.

---

Если хочешь, дальше можем:

* добавить REST-метод `/api/training/mark-used`, чтобы твой train-скрипт не писал SQL руками, а просто отправлял список `product_id`,
* или сделать отдельную «диагностическую» вкладку: какие категории сколько необученных СТЕ имеют (табличка типа `category_id / name / total / untrained`).

