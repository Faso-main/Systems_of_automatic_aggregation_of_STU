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
-- 1. Метаданные запусков генерации
-- =========================

CREATE TABLE generation_run (
    id              BIGSERIAL PRIMARY KEY,
    run_type        TEXT NOT NULL,                      -- 'ontology_v4', 'runtime_v2', ...
    source_csv      TEXT,
    model_name      TEXT,
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT now(), -- когда модель отработала
    meta            JSONB                               -- весь meta-блок из json'ов
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
    generated_at            TIMESTAMPTZ,                -- дата генерации категории моделью
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),  -- когда попала в БД
    admin_status            TEXT,                       -- статус_категории: 'pending'/'approved'/'rejected'
    admin_rating            SMALLINT,                   -- оценка категории админом 1..5
    last_generation_run_id  BIGINT REFERENCES generation_run(id) -- последний run модели
);

ALTER TABLE product_category
    ADD CONSTRAINT chk_product_category_admin_rating
        CHECK (admin_rating IS NULL OR (admin_rating BETWEEN 1 AND 5));


-- =========================
-- 3. Товары / СТЕ
-- =========================

CREATE TABLE product (
    id              BIGINT PRIMARY KEY,                 -- id_сте
    category_id     BIGINT NOT NULL REFERENCES product_category(id),
    name            TEXT NOT NULL,                      -- название_сте (raw_name)
    producer        TEXT,                               -- производитель
    country         TEXT,                               -- страна_происхождения
    image_url       TEXT,                               -- если есть ссылка на картинку
    raw_specs       JSONB,                              -- сырой json со всеми spec*, если захотим хранить
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
    original_text   TEXT,                               -- "Индекс нагрузки: 97"
    sort_order      INTEGER,                            -- чтобы красиво упорядочить
    UNIQUE(category_id, key, value)
);

CREATE INDEX IF NOT EXISTS idx_category_feature_category ON category_feature(category_id);
CREATE INDEX IF NOT EXISTS idx_category_feature_key ON category_feature(key);


-- =========================
-- 5. Характеристики товаров (из PROD_runtime_V2_READY / runtime_llm)
-- =========================

CREATE TABLE product_feature (
    id                  BIGSERIAL PRIMARY KEY,
    product_id          BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    key                 TEXT NOT NULL,                  -- "Ширина профиля"
    value               TEXT NOT NULL,                  -- "215.00000 мм"
    original_text       TEXT,                           -- "Ширина профиля: 215.00000 мм"
    is_selected         BOOLEAN NOT NULL DEFAULT TRUE,  -- можем выключить руками
    source              TEXT,                           -- 'runtime_v2', 'llm_manual', ...
    generation_run_id   BIGINT REFERENCES generation_run(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_product_feature_product ON product_feature(product_id);
CREATE INDEX IF NOT EXISTS idx_product_feature_key ON product_feature(key);

\dt

---

SELECT * FROM generation_run LIMIT 1;
SELECT * FROM product_category LIMIT 1;
SELECT * FROM product LIMIT 1;
SELECT * FROM product_feature LIMIT 1;
SELECT * FROM category_feature LIMIT 1;
