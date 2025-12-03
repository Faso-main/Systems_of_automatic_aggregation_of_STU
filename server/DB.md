# База `th3_db` — структура и DDL

## 0. Установка PostgreSQL и создание БД

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib

# Проверка, что postgres запущен
sudo systemctl status postgresql

# Заходим под системным пользователем postgres
sudo -u postgres psql
````

Внутри `psql`:

```sql
-- создаём роль для приложения
CREATE ROLE th3_app WITH LOGIN PASSWORD '1234';

-- создаём базу и назначаем владельца
CREATE DATABASE th3_db OWNER th3_app;

GRANT ALL PRIVILEGES ON DATABASE th3_db TO th3_app;

-- при необходимости можно выдать суперправа (dev-режим)
ALTER USER th3_app WITH SUPERUSER;
```

Подключение от приложения/локально:

```bash
psql -h localhost -U th3_app -d th3_db
```

---

## 1. Базовая схема (public)

Ниже — DDL для логической схемы. В реальной БД она уже есть (см. `all_structure.sql`), здесь — человекочитаемый вариант.

### 1.1. Таблица запусков генерации `generation_run`

История запусков моделей/скриптов, чтобы потом понимать, откуда взялись категории/фичи и т.п.

```sql
CREATE TABLE generation_run (
    id           BIGSERIAL PRIMARY KEY,
    run_type     TEXT     NOT NULL,              -- тип/источник запуска (например, 'runtime_v2', 'ontology_v4')
    source_csv   TEXT,                           -- файл-источник (если есть)
    model_name   TEXT,                           -- имя модели/пайплайна
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    meta         JSONB                           -- произвольный JSON о запуске
);

CREATE INDEX IF NOT EXISTS idx_generation_run_type
    ON generation_run(run_type);
```

---

### 1.2. Категории товаров `product_category`

Логические категории, которые видит фронт.

```sql
CREATE TABLE product_category (
    id                     BIGINT PRIMARY KEY,   -- id категории (можно брать из внешнего источника)
    name                   TEXT    NOT NULL,     -- название категории
    short_description      TEXT,                 -- краткое описание для фронта
    generated_at           TIMESTAMPTZ,          -- когда модель сгенерировала/обновила категорию
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),

    admin_status           TEXT    NOT NULL DEFAULT 'new', -- 'new' | 'approved' | 'rejected' | ...
    admin_rating           SMALLINT,                       -- 1..5 (оценка админом)

    last_generation_run_id BIGINT REFERENCES generation_run(id),

    has_new_items          BOOLEAN NOT NULL DEFAULT FALSE, -- есть новые товары после генерации
    new_items_count        INTEGER NOT NULL DEFAULT 0,     -- их количество

    CONSTRAINT chk_product_category_admin_rating
        CHECK (admin_rating IS NULL OR (admin_rating BETWEEN 1 AND 5))
);
```

> Во фронте это маппится на поля вида `status`, `rating`, `hasNewItems`, `newItemsCount` и т.д. (через API) — в БД они хранятся как `admin_status`, `admin_rating`, `has_new_items`, `new_items_count`. 

---

### 1.3. Товары / СТЕ `product`

Каждый товар (СТЕ) может быть привязан к категории.

```sql
CREATE TABLE product (
    id                   BIGINT PRIMARY KEY,          -- id СТЕ
    category_id          BIGINT REFERENCES product_category(id)
                           ON DELETE SET NULL,        -- при удалении категории товары остаются "без категории"

    name                 TEXT    NOT NULL,            -- название товара
    producer             TEXT,
    country              TEXT,
    image_url            TEXT,                        -- URL картинки (опционально)

    raw_specs            JSONB,                       -- сырые характеристики (если нужно хранить как json)

    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    imported_at          TIMESTAMPTZ NOT NULL DEFAULT now(), -- когда товар "завезли" в систему

    is_used_for_training BOOLEAN NOT NULL DEFAULT FALSE,      -- использовался ли в обучении
    training_used_at     TIMESTAMPTZ                           -- когда использовали в обучении
);

CREATE INDEX IF NOT EXISTS idx_product_category_id
    ON product(category_id);
```

---

### 1.4. Уникальные характеристики категорий `category_feature`

Характеристики, выделенные для категорий (то, что фронт показывает как “Основные характеристики категории”).

```sql
CREATE TABLE category_feature (
    id            BIGSERIAL PRIMARY KEY,
    category_id   BIGINT NOT NULL REFERENCES product_category(id)
                               ON DELETE CASCADE,
    key           TEXT   NOT NULL,       -- название характеристики
    value         TEXT   NOT NULL,       -- значение (может быть нормализовано)
    original_text TEXT,                  -- исходная строка (как пришла из источника)
    sort_order    INTEGER,               -- порядок показа

    UNIQUE (category_id, key, value)
);

CREATE INDEX IF NOT EXISTS idx_category_feature_category
    ON category_feature(category_id);

CREATE INDEX IF NOT EXISTS idx_category_feature_key
    ON category_feature(key);
```

---

### 1.5. Характеристики товаров `product_feature`

Характеристики по каждому товару.

```sql
CREATE TABLE product_feature (
    id                BIGSERIAL PRIMARY KEY,
    product_id        BIGINT NOT NULL REFERENCES product(id)
                               ON DELETE CASCADE,
    key               TEXT   NOT NULL,
    value             TEXT   NOT NULL,
    original_text     TEXT,
    is_selected       BOOLEAN NOT NULL DEFAULT TRUE,   -- можно "отключать" фичу руками
    source            TEXT,                            -- 'runtime_v2', 'llm_manual', ...
    generation_run_id BIGINT REFERENCES generation_run(id),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_product_feature_product
    ON product_feature(product_id);

CREATE INDEX IF NOT EXISTS idx_product_feature_key
    ON product_feature(key);
```

---

### 1.6. Семейства категорий

Используются для группировки близких категорий.

#### 1.6.1. `category_family`

```sql
CREATE TABLE category_family (
    id         BIGSERIAL PRIMARY KEY,
    name       TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### 1.6.2. `category_family_member`

Связь многие-ко-многим: семейство ↔ категории.

```sql
CREATE TABLE category_family_member (
    family_id   BIGINT NOT NULL REFERENCES category_family(id)
                              ON DELETE CASCADE,
    category_id BIGINT NOT NULL REFERENCES product_category(id),
    PRIMARY KEY (family_id, category_id)
);
```

---

### 1.7. Группы товаров

Логические группы товаров (если нужно объединять товары не только через категории).

#### 1.7.1. `product_group`

```sql
CREATE TABLE product_group (
    id         BIGSERIAL PRIMARY KEY,
    name       TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### 1.7.2. `product_group_member`

```sql
CREATE TABLE product_group_member (
    group_id  BIGINT NOT NULL REFERENCES product_group(id)
                             ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES product(id),
    PRIMARY KEY (group_id, product_id)
);
```

---

### 1.8. Сходство категорий `category_similarity`

Результаты расчёта similarity между категориями по их фичам.

```sql
CREATE TABLE category_similarity (
    category_id_a   BIGINT NOT NULL,
    category_id_b   BIGINT NOT NULL,
    similarity      NUMERIC(5,4) NOT NULL,  -- общая метрика
    common_keys     TEXT[]      NOT NULL,
    only_a_keys     TEXT[]      NOT NULL,
    only_b_keys     TEXT[]      NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    key_similarity  NUMERIC(5,4),
    value_similarity NUMERIC(5,4),

    PRIMARY KEY (category_id_a, category_id_b)
);
```

---

### 1.9. Сходство товаров `product_similarity`

Аналогично `category_similarity`, только для товаров.

```sql
CREATE TABLE product_similarity (
    product_id_a    BIGINT NOT NULL,
    product_id_b    BIGINT NOT NULL,
    similarity      NUMERIC(5,4) NOT NULL,
    key_similarity  NUMERIC(5,4),
    value_similarity NUMERIC(5,4),
    common_keys     TEXT[]      NOT NULL,
    only_a_keys     TEXT[]      NOT NULL,
    only_b_keys     TEXT[]      NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (product_id_a, product_id_b)
);
```

---

## 2. Функции и триггеры

### 2.1. Обновление флагов новых товаров `refresh_new_items_for_category`

Используется триггерами на `product`, чтобы поддерживать `has_new_items` и `new_items_count` в `product_category`. Логика взята из `all_structure.sql`. 

```sql
CREATE OR REPLACE FUNCTION refresh_new_items_for_category(cat_id BIGINT)
RETURNS void AS $$
DECLARE
    gen_ts   TIMESTAMPTZ;
    new_cnt  INTEGER;
BEGIN
    SELECT COALESCE(generated_at, created_at)
    INTO gen_ts
    FROM product_category
    WHERE id = cat_id;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    SELECT COUNT(*)
    INTO new_cnt
    FROM product p
    WHERE p.category_id = cat_id
      AND p.imported_at > gen_ts;

    UPDATE product_category c
    SET
        has_new_items   = (new_cnt > 0),
        new_items_count = new_cnt
    WHERE c.id = cat_id;
END;
$$ LANGUAGE plpgsql;
```

### 2.2. Триггеры на таблице `product`

#### AFTER INSERT

```sql
CREATE OR REPLACE FUNCTION trg_product_after_insert()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM refresh_new_items_for_category(NEW.category_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER product_after_insert
AFTER INSERT ON product
FOR EACH ROW
EXECUTE FUNCTION trg_product_after_insert();
```

#### AFTER DELETE

```sql
CREATE OR REPLACE FUNCTION trg_product_after_delete()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM refresh_new_items_for_category(OLD.category_id);
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER product_after_delete
AFTER DELETE ON product
FOR EACH ROW
EXECUTE FUNCTION trg_product_after_delete();
```

#### AFTER UPDATE

```sql
CREATE OR REPLACE FUNCTION trg_product_after_update()
RETURNS TRIGGER AS $$
BEGIN
    -- если категория не изменилась, ничего не трогаем
    IF NEW.category_id = OLD.category_id THEN
        RETURN NEW;
    END IF;

    PERFORM refresh_new_items_for_category(OLD.category_id);
    PERFORM refresh_new_items_for_category(NEW.category_id);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER product_after_update
AFTER UPDATE ON product
FOR EACH ROW
EXECUTE FUNCTION trg_product_after_update();
```

---

## 3. Полезные выборки

### 3.1. Вытащить категории с товарами и фичами (в виде, удобном для API)

```sql
SELECT
    c.id,
    c.name,
    c.short_description,
    c.generated_at,
    c.created_at,
    c.admin_status,
    c.admin_rating,
    c.has_new_items,
    c.new_items_count,

    ARRAY_AGG(DISTINCT p.id ORDER BY p.id) AS product_ids,

    (
        SELECT JSON_AGG(x ORDER BY x->>'key')
        FROM (
            SELECT DISTINCT JSONB_BUILD_OBJECT('key', cf.key, 'value', cf.value) AS x
            FROM category_feature cf
            WHERE cf.category_id = c.id
        ) t
    ) AS category_features

FROM product_category c
LEFT JOIN product p ON p.category_id = c.id
GROUP BY
    c.id,
    c.name,
    c.short_description,
    c.generated_at,
    c.created_at,
    c.admin_status,
    c.admin_rating,
    c.has_new_items,
    c.new_items_count;
```

> Это примерно то, что потом маппится во фронт: `id`, `name`, `description`, `generatedAt`, `status`, `rating`, `hasNewItems`, `newItemsCount`, `productIds`, `features` и т.д.

---

## 4. Очистка/переинициализация схемы

Если нужно снести схему и поднять её с нуля (dev-режим):

```sql
DROP TABLE IF EXISTS product_group_member CASCADE;
DROP TABLE IF EXISTS product_group CASCADE;
DROP TABLE IF EXISTS product_similarity CASCADE;
DROP TABLE IF EXISTS category_similarity CASCADE;
DROP TABLE IF EXISTS category_family_member CASCADE;
DROP TABLE IF EXISTS category_family CASCADE;
DROP TABLE IF EXISTS product_feature CASCADE;
DROP TABLE IF EXISTS category_feature CASCADE;
DROP TABLE IF EXISTS product CASCADE;
DROP TABLE IF EXISTS product_category CASCADE;
DROP TABLE IF EXISTS generation_run CASCADE;
```

Дальше — применяем DDL из разделов **1–2** поверх пустой базы.

---

