#!/usr/bin/env python
import csv
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_batch, Json

# Путь к CSV с результатами импорта
CSV_PATH = Path("py_back/rexexp/data/result_itr4.csv")

# Настройки подключения к БД
DB_CONFIG = {
    "dbname": "th3_db",
    "user": "th3_app",
    "password": "1234",      # поправь, если пароль другой
    "host": "localhost",
    "port": 5432,
}

BATCH_SIZE = 1000


def build_specs_as_text(row: dict) -> str | None:
    """
    Собираем spec1..specN в одну строку:

    "Плотность ткани: 235 гр/м2; Цвет: Тёмно-синий; Размер: XL"

    Если нет ни одной непустой spec — возвращаем None.
    """
    parts: list[str] = []

    for key, value in row.items():
        if not key.startswith("spec"):
            continue
        if value is None:
            continue

        value = str(value).strip()
        if not value:
            continue

        if ":" in value:
            k, v = value.split(":", 1)
            parts.append(f"{k.strip()}: {v.strip()}")
        else:
            parts.append(value)

    return "; ".join(parts) if parts else None


def main():
    if not CSV_PATH.exists():
        raise SystemExit(f"Файл {CSV_PATH} не найден")

    print(f"Использую CSV: {CSV_PATH.resolve()}")

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    # SQL с UPSERT по id
    # product.raw_specs имеет тип JSON/JSONB → кладём туда JSON-строку.
    sql = """
    INSERT INTO product (
        id,
        category_id,
        name,
        producer,
        country,
        image_url,
        raw_specs,
        imported_at,
        is_used_for_training
    )
    VALUES (
        %(id)s,
        %(category_id)s,
        %(name)s,
        %(producer)s,
        %(country)s,
        %(image_url)s,
        %(raw_specs)s,
        NOW(),
        FALSE
    )
    ON CONFLICT (id) DO UPDATE SET
        category_id          = EXCLUDED.category_id,
        name                 = EXCLUDED.name,
        producer             = EXCLUDED.producer,
        country              = EXCLUDED.country,
        image_url            = EXCLUDED.image_url,
        raw_specs            = EXCLUDED.raw_specs,
        imported_at          = EXCLUDED.imported_at,
        is_used_for_training = EXCLUDED.is_used_for_training;
    """

    total = 0
    skipped_no_name = 0
    batch: list[dict] = []

    with CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            # id СТЕ
            try:
                product_id = int(row.get("id_сте") or 0)
            except ValueError:
                continue
            if not product_id:
                continue

            # id категории
            cat_raw = row.get("id_категории")
            try:
                category_id = (
                    int(cat_raw) if cat_raw not in (None, "", "NaN") else None
                )
            except ValueError:
                category_id = None

            # имя товара — ОБЯЗАТЕЛЬНО, иначе пропускаем строку
            raw_name = (row.get("название_сте") or "").strip()
            if not raw_name:
                skipped_no_name += 1
                continue

            # Собираем все spec* в одну строку
            specs_text = build_specs_as_text(row)

            product = {
                "id": product_id,
                "category_id": category_id,
                "name": raw_name,
                "producer": (row.get("производитель") or "").strip() or None,
                "country": (row.get("страна_происхождения") or "").strip() or None,
                "image_url": (row.get("ссылка_на_картинку") or "").strip() or None,
                # ВАЖНО: оборачиваем в Json(...) → в колонку JSON попадёт валидная JSON-строка
                "raw_specs": Json(specs_text) if specs_text is not None else None,
            }

            batch.append(product)
            total += 1

            if len(batch) >= BATCH_SIZE:
                execute_batch(cur, sql, batch, page_size=BATCH_SIZE)
                conn.commit()
                print(
                    f"Импортировано {total} строк (пока), "
                    f"пропущено без name: {skipped_no_name}"
                )
                batch.clear()

    if batch:
        execute_batch(cur, sql, batch, page_size=BATCH_SIZE)
        conn.commit()
        print(
            f"Импортировано всего {total} строк, "
            f"пропущено без name: {skipped_no_name}"
        )

    cur.close()
    conn.close()
    print("Готово: импорт СТЕ из result_itr4.csv завершён.")


if __name__ == "__main__":
    main()
