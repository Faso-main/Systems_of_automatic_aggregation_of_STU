import json
import psycopg2

ONTOLOGY_PATH = "result/A__llm_itr6.json"
DB_DSN = "postgresql://th3_app:1234@localhost:5432/th3_db"


def main():
    with open(ONTOLOGY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = data.get("meta") or data.get("metadata") or {}
    cats = data.get("categories", {})

    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor()

    # 1) создаём запись о запуске генерации онтологии
    cur.execute(
        """
        INSERT INTO generation_run (run_type, source_csv, model_name, meta)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (
            "ontology_v4",
            meta.get("source_file") or meta.get("source_csv"),
            meta.get("model") or meta.get("model_name"),
            json.dumps(meta, ensure_ascii=False),
        ),
    )
    generation_run_id = cur.fetchone()[0]
    print(f"[ontology] generation_run_id = {generation_run_id}")

    # 2) прогоняем категории
    for cat_id, cat_data in cats.items():
        cat_id_int = int(cat_id)
        category_name = cat_data.get("category_name") or cat_data.get("name") or ""
        characteristics = cat_data.get("characteristics", [])

        # простое краткое описание: первые несколько характеристик в одну строку
        short_desc = "; ".join(characteristics[:5]) if characteristics else None

        # upsert категории
        cur.execute(
            """
            INSERT INTO product_category (id, name, short_description, generated_at, last_generation_run_id)
            VALUES (%s, %s, %s, NOW(), %s)
            ON CONFLICT (id) DO UPDATE
                SET name = EXCLUDED.name,
                    short_description = COALESCE(product_category.short_description, EXCLUDED.short_description),
                    generated_at = EXCLUDED.generated_at,
                    last_generation_run_id = EXCLUDED.last_generation_run_id
            """,
            (cat_id_int, category_name, short_desc, generation_run_id),
        )

        # удаляем старые фичи категории
        cur.execute("DELETE FROM category_feature WHERE category_id = %s", (cat_id_int,))

        # записываем новые
        for idx, ch in enumerate(characteristics):
            if ":" in ch:
                key, value = ch.split(":", 1)
                key = key.strip()
                value = value.strip()
            else:
                key = "Характеристика"
                value = ch

            cur.execute(
                """
                INSERT INTO category_feature
                    (category_id, key, value, original_text, sort_order)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (cat_id_int, key, value, ch, idx),
            )

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Онтология категорий загружена в PostgreSQL.")


if __name__ == "__main__":
    main()
