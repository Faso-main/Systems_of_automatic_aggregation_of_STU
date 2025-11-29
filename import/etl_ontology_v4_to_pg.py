import json
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
import os

# --------------------------
#  ПУТИ К ФАЙЛАМ
# --------------------------
RUNTIME_PATH = os.path.join("result","PROD_runtime_V2_READY.json")
ITEMS_ITR3_PATH = os.path.join("result","runtime_llm_items_itr3.json")
ONTOLOGY_PATH = os.path.join("result","UCOV4.json")

# --------------------------
#  ПОДКЛЮЧЕНИЕ К БД
# --------------------------
conn = psycopg2.connect(
    dbname="th3_db",
    user="th3_app",
    password="1234",
    host="localhost",
)
cursor = conn.cursor()


# --------------------------
#  ЧИТАЕМ JSON
# --------------------------

with open(RUNTIME_PATH, "r", encoding="utf-8") as f:
    runtime = json.load(f)

with open(ITEMS_ITR3_PATH, "r", encoding="utf-8") as f:
    items_itr3 = json.load(f)

with open(ONTOLOGY_PATH, "r", encoding="utf-8") as f:
    ontology = json.load(f)


# --------------------------
# 1) generation_run
# --------------------------

cursor.execute("""
    INSERT INTO generation_run (run_type, source_csv, model_name, generated_at, meta)
    VALUES (%s, %s, %s, %s, %s)
    RETURNING id;
""", (
    "full_runtime_import_v2",
    runtime["meta"]["source_csv"],
    runtime["meta"]["model_safetensors"],
    datetime.fromisoformat(runtime["meta"]["generated_at"]),
    json.dumps(runtime["meta"])
))

generation_run_id = cursor.fetchone()[0]
print("✓ generation_run id =", generation_run_id)


# --------------------------
# 2) Категории
# --------------------------

category_rows = []

for cat_id, cat_data in items_itr3["categories"].items():
    category_rows.append((
        int(cat_data["id_категории"]),
        cat_data["category_name"],
        "",                     # краткое описание (пока пустое)
        datetime.now(),         # дата генерации категории моделью
        "new",                  # admin_status
        None,                   # admin_rating
        generation_run_id       # last_generation_run_id
    ))

execute_values(cursor, """
    INSERT INTO product_category
    (id, name, short_description, generated_at, admin_status, admin_rating, last_generation_run_id)
    VALUES %s
    ON CONFLICT (id) DO NOTHING;
""", category_rows)

print("✓ Импорт категорий:", len(category_rows))


# --------------------------
# 3) Товары
# --------------------------

product_rows = []
product_feature_rows = []

for ste_id, item in runtime["items"].items():

    product_rows.append((
        int(item["id_сте"]),
        int(item["id_категории"]),
        item.get("raw_name", ""),
        item.get("producer", ""),
        item.get("country", ""),
        None,  # image_url
        None   # raw_specs (можем добавить позже)
    ))

    # Характеристики товара
    for ch in item.get("characteristics", []):
        if ":" not in ch:
            continue
        key, value = ch.split(":", 1)
        product_feature_rows.append((
            int(item["id_сте"]),
            key.strip(),
            value.strip(),
            ch,
            "runtime_v2",
            generation_run_id
        ))

execute_values(cursor, """
    INSERT INTO product
    (id, category_id, name, producer, country, image_url, raw_specs)
    VALUES %s
    ON CONFLICT (id) DO NOTHING;
""", product_rows)

print("✓ Импорт товаров:", len(product_rows))


# --------------------------
# 4) Характеристики категорий
# --------------------------

category_feature_rows = []

for cat_id, cat_data in ontology["categories"].items():
    for idx, feat in enumerate(cat_data["characteristics"]):
        if ":" not in feat:
            continue
        key, value = feat.split(":", 1)
        category_feature_rows.append((
            int(cat_id),
            key.strip(),
            value.strip(),
            feat,
            idx
        ))

execute_values(cursor, """
    INSERT INTO category_feature
    (category_id, key, value, original_text, sort_order)
    VALUES %s
    ON CONFLICT DO NOTHING;
""", category_feature_rows)

print("✓ Импорт характеристик категорий:", len(category_feature_rows))


# --------------------------
# 5) Загрузка характеристик товаров
# --------------------------

execute_values(cursor, """
    INSERT INTO product_feature
    (product_id, key, value, original_text, source, generation_run_id)
    VALUES %s
    ON CONFLICT DO NOTHING;
""", product_feature_rows)

print("✓ Импорт характеристик товаров:", len(product_feature_rows))

# --------------------------
# Commit
# --------------------------

conn.commit()
cursor.close()
conn.close()

print("\n🎉 Готово! Все данные загружены.")
