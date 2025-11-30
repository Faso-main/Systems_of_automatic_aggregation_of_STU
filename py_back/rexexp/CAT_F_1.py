import os
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

import psycopg2
import psycopg2.extras


# ========= КОНФИГ БАЗЫ =========

PG_DSN = "postgresql://th3_app:1234@localhost:5432/th3_db"


@dataclass
class CategoryFeatures:
    category_id: int
    keys: Set[str]
    key_values: Dict[str, List[str]]


def jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union > 0 else 0.0


def load_category_features(conn) -> List[CategoryFeatures]:
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(
            """
            SELECT
              c.id AS category_id,
              cf.key AS feature_key,
              array_agg(DISTINCT cf.value) AS values
            FROM product_category c
            LEFT JOIN category_feature cf
              ON cf.category_id = c.id
            GROUP BY c.id, cf.key
            ORDER BY c.id, cf.key;
            """
        )

        by_cat = {}

        for row in cur:
            cat_id = int(row["category_id"])
            key = row["feature_key"]
            values = row["values"] or []
            if key is None:
                continue

            if cat_id not in by_cat:
                by_cat[cat_id] = {}

            by_cat[cat_id][key] = [v for v in values if v is not None]

    result = []
    for cat_id, kv in by_cat.items():
        keys = set(kv.keys())
        result.append(CategoryFeatures(cat_id, keys, kv))

    print(f"[load_category_features] категорий: {len(result)}")
    return result


def diff_for_pair(a: CategoryFeatures, b: CategoryFeatures):
    common = sorted(a.keys & b.keys)
    only_a = sorted(a.keys - b.keys)
    only_b = sorted(b.keys - a.keys)
    return common, only_a, only_b


SIMILARITY_THRESHOLD = 0.6


def rebuild_similarity_table():
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = False

    try:
        cats = load_category_features(conn)

        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE category_similarity;")

        rows_to_insert = []
        n = len(cats)

        for i in range(n):
            a = cats[i]
            for j in range(i + 1, n):
                b = cats[j]

                sim = jaccard(a.keys, b.keys)
                if sim < SIMILARITY_THRESHOLD:
                    continue

                common, only_a, only_b = diff_for_pair(a, b)

                rows_to_insert.append(
                    (
                        a.category_id,
                        b.category_id,
                        round(sim, 4),
                        common,
                        only_a,
                        only_b,
                    )
                )

        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO category_similarity (
                    category_id_a,
                    category_id_b,
                    similarity,
                    common_keys,
                    only_a_keys,
                    only_b_keys
                ) VALUES %s
                """,
                rows_to_insert,
            )

        conn.commit()
        print("[OK] similarity пересчитана")
    except Exception as e:
        conn.rollback()
        print("[ERROR]:", e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    rebuild_similarity_table()
