-- 1. Дополнительные поля для отслеживания "новизны"

ALTER TABLE product
    ADD COLUMN IF NOT EXISTS imported_at       TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE product_category
    ADD COLUMN IF NOT EXISTS has_new_items   BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS new_items_count INTEGER NOT NULL DEFAULT 0;

-- 2. Функция пересчитывает has_new_items / new_items_count для одной категории

CREATE OR REPLACE FUNCTION refresh_new_items_for_category(cat_id BIGINT)
RETURNS VOID AS $$
DECLARE
    gen_ts TIMESTAMPTZ;
    new_cnt INTEGER;
BEGIN
    -- Берём "опорное" время генерации категории (или её создания, если generated_at null)
    SELECT COALESCE(generated_at, created_at)
    INTO gen_ts
    FROM product_category
    WHERE id = cat_id;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    -- Считаем, сколько товаров в этой категории новее генерации
    SELECT COUNT(*)
    INTO new_cnt
    FROM product p
    WHERE p.category_id = cat_id
      AND p.imported_at > gen_ts;

    -- Обновляем флаги в категории
    UPDATE product_category c
    SET
        has_new_items   = (new_cnt > 0),
        new_items_count = new_cnt
    WHERE c.id = cat_id;
END;
$$ LANGUAGE plpgsql;

-- 3. Триггер: после добавления товара пересчитываем новые товары в категории

CREATE OR REPLACE FUNCTION trg_product_after_insert()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM refresh_new_items_for_category(NEW.category_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS product_after_insert ON product;

CREATE TRIGGER product_after_insert
AFTER INSERT ON product
FOR EACH ROW
EXECUTE FUNCTION trg_product_after_insert();

CREATE OR REPLACE FUNCTION refresh_new_items_for_category(cat_id BIGINT)
RETURNS VOID AS $$
DECLARE
    gen_ts TIMESTAMPTZ;
    new_cnt INTEGER;
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

-- DELETE
CREATE OR REPLACE FUNCTION trg_product_after_delete()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM refresh_new_items_for_category(OLD.category_id);
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS product_after_delete ON product;

CREATE TRIGGER product_after_delete
AFTER DELETE ON product
FOR EACH ROW
EXECUTE FUNCTION trg_product_after_delete();


-- UPDATE (смена категории)
CREATE OR REPLACE FUNCTION trg_product_after_update()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.category_id = OLD.category_id THEN
        RETURN NEW;
    END IF;

    PERFORM refresh_new_items_for_category(OLD.category_id);
    PERFORM refresh_new_items_for_category(NEW.category_id);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS product_after_update ON product;

CREATE TRIGGER product_after_update
AFTER UPDATE ON product
FOR EACH ROW
EXECUTE FUNCTION trg_product_after_update();
