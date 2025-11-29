#!/usr/bin/env python
import csv
import json
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_batch, Json

CSV_PATH = Path("py_back/rexexp/data/result_itr4.csv")

DB_CONFIG = {
    "dbname": "th3_db",
    "user": "th3_app",
    "password": "1234",      # поправь, если у тебя другой пароль
    "host": "localhost",
    "port": 5432,
}

BATCH_SIZE = 1000


def build_raw_specs(row: dict) -> list[dict]:
    """
    Собираем spec1..spec31 в массив
    [
      {"key": "Ширина профиля", "value": "256 мм"},
      ...
    ]
    """
    specs = []
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
            specs.append({"key": k.strip(), "value": v.strip()})
        else:
            specs.append({"key": None, "value": value})
    return specs


def main():
    if not CSV_PATH.exists():
        raise SystemExit(f"Файл {CSV_PATH} не найден")

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    # SQL с UPSERT по id
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
    batch = []

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

            # id категории (как в CSV)
            cat_raw = row.get("id_категории")
            try:
                category_id = int(cat_raw) if cat_raw not in (None, "", "NaN") else None
            except ValueError:
                category_id = None

            product = {
                "id": product_id,
                "category_id": category_id,
                "name": (row.get("название_сте") or "").strip() or None,
                "producer": (row.get("производитель") or "").strip() or None,
                "country": (row.get("страна_происхождения") or "").strip() or None,
                "image_url": (row.get("ссылка_на_картинку") or "").strip() or None,
                # raw_specs - JSON-массив
                "raw_specs": Json(build_raw_specs(row)),
            }

            batch.append(product)
            total += 1

            if len(batch) >= BATCH_SIZE:
                execute_batch(cur, sql, batch, page_size=BATCH_SIZE)
                conn.commit()
                print(f"Импортировано {total} строк...")
                batch.clear()

    if batch:
        execute_batch(cur, sql, batch, page_size=BATCH_SIZE)
        conn.commit()
        print(f"Импортировано всего {total} строк.")

    cur.close()
    conn.close()
    print("Готово: импорт СТЕ из result_itr4.csv завершён.")


if __name__ == "__main__":
    main()
