sudo apt update
sudo apt install postgresql postgresql-contrib

sudo systemctl status postgresql

sudo -u postgres psql

CREATE ROLE th3_app WITH LOGIN PASSWORD '1234';

CREATE DATABASE th3_db OWNER th3_app;

GRANT ALL PRIVILEGES ON DATABASE th3_db TO th3_app;

ALTER USER th3_app WITH SUPERUSER;

psql -h localhost -U th3_app -d th3_db


---

-- =========================
-- ЧИСТИМ СТАРЬЁ (аккуратно)
-- =========================

DROP TABLE IF EXISTS product_feature CASCADE;
DROP TABLE IF EXISTS category_feature CASCADE;
DROP TABLE IF EXISTS product CASCADE;
DROP TABLE IF EXISTS product_category CASCADE;
DROP TABLE IF EXISTS generation_run CASCADE;


-- =========================
-- 1. Метаданные запусков генерации (на будущее)
-- =========================

CREATE TABLE generation_run (
    id              BIGSERIAL PRIMARY KEY,
    run_type        TEXT NOT NULL,                      -- 'ontology_v4_from_runtime_v2', 'runtime_v2', ...
    source_csv      TEXT,
    model_name      TEXT,
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT now(), -- когда модель отработала
    meta            JSONB                               -- meta-блок из json'ов (как есть)
);

CREATE INDEX IF NOT EXISTS idx_generation_run_type ON generation_run(run_type);


-- =========================
-- 2. Категории товаров
--    (под фронт: id, name, description, createdAt, status, rating, productIds, features)
-- =========================

CREATE TABLE product_category (
    id                      BIGINT PRIMARY KEY,         -- id_категории
    name                    TEXT NOT NULL,              -- название категории
    short_description       TEXT,                       -- краткое описание (description)
    generated_at            TIMESTAMPTZ,                -- дата генерации категории моделью (из онтологии)
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),  -- когда попала в БД
    admin_status            TEXT NOT NULL DEFAULT 'new',         -- статус_категории: 'new'/'approved'/'rejected'/...
    admin_rating            SMALLINT,                   -- оценка категории админом 1..5
    last_generation_run_id  BIGINT REFERENCES generation_run(id) -- последний run модели (опционально, можно не заполнять)
);

ALTER TABLE product_category
    ADD CONSTRAINT chk_product_category_admin_rating
        CHECK (admin_rating IS NULL OR (admin_rating BETWEEN 1 AND 5));


-- =========================
-- 3. Товары / СТЕ
--    (id_сте + привязка к категории + базовые поля)
-- =========================

CREATE TABLE product (
    id              BIGINT PRIMARY KEY,                 -- id_сте
    category_id     BIGINT REFERENCES product_category(id) ON DELETE SET NULL,
    name            TEXT NOT NULL,                      -- название_сте (raw_name из PROD_runtime_V2_READY)
    producer        TEXT,                               -- производитель
    country         TEXT,                               -- страна_происхождения
    image_url       TEXT,                               -- ссылка на картинку (если потом понадобится)
    raw_specs       JSONB,                              -- опционально: сырые spec*, если будем сохранять
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_product_category_id ON product(category_id);


-- =========================
-- 4. Уникальные характеристики категорий
--    (из universal_characteristics_ontology_v4.json)
-- =========================

CREATE TABLE category_feature (
    id              BIGSERIAL PRIMARY KEY,
    category_id     BIGINT NOT NULL REFERENCES product_category(id) ON DELETE CASCADE,
    key             TEXT NOT NULL,                      -- "Индекс нагрузки"
    value           TEXT NOT NULL,                      -- "97"
    original_text   TEXT,                               -- исходная строка "Индекс нагрузки: 97" (по желанию)
    sort_order      INTEGER,                            -- чтобы красиво упорядочить на фронте
    UNIQUE(category_id, key, value)
);

CREATE INDEX IF NOT EXISTS idx_category_feature_category ON category_feature(category_id);
CREATE INDEX IF NOT EXISTS idx_category_feature_key ON category_feature(key);


-- =========================
-- 5. Характеристики товаров
--    (из PROD_runtime_V2_READY.json)
-- =========================

CREATE TABLE product_feature (
    id                  BIGSERIAL PRIMARY KEY,
    product_id          BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    key                 TEXT NOT NULL,                  -- "Ширина профиля"
    value               TEXT NOT NULL,                  -- "215.00000 мм"
    original_text       TEXT,                           -- "Ширина профиля: 215.00000 мм"
    is_selected         BOOLEAN NOT NULL DEFAULT TRUE,  -- можно будет выключать руками
    source              TEXT,                           -- 'runtime_v2', 'llm_manual', ...
    generation_run_id   BIGINT REFERENCES generation_run(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_product_feature_product ON product_feature(product_id);
CREATE INDEX IF NOT EXISTS idx_product_feature_key ON product_feature(key);


-- =========================
-- 6. Быстрая проверка, что всё создалось
-- =========================

-- \dt   -- в psql можно увидеть список таблиц


---

SELECT
    c.id                                      AS id_категории,
    c.name                                    AS название_категории,
    c.short_description                       AS краткое_описание,
    c.generated_at                            AS дата_генерации_моделью,
    c.admin_rating                            AS оценка_категории_админом,
    c.admin_status                            AS статус_категории,

    ARRAY_AGG(DISTINCT p.id ORDER BY p.id)    AS product_ids,

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
GROUP BY c.id, c.name, c.short_description, c.generated_at, c.admin_rating, c.admin_status;
