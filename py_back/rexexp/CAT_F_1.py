import os
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

import psycopg2
import psycopg2.extras


PG_DSN = "postgresql://th3_app:1234@localhost:5432/th3_db"


@dataclass
class CategoryFeatures:
    category_id: int
    keys: Set[str]
    key_values: Dict[str, List[str]]  # key -> список значений (array_agg)


def jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union > 0 else 0.0


def jaccard_values(a_vals: List[str], b_vals: List[str]) -> float:
    set_a = set(a_vals or [])
    set_b = set(b_vals or [])
    if not set_a and not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union > 0 else 0.0


def load_category_features(conn) -> List[CategoryFeatures]:
    """
    Тянем категории с их характеристиками из product_category + category_feature,
    агрегируя значения по ключу.
    """
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

        by_cat: Dict[int, Dict[str, List[str]]] = {}

        for row in cur:
            cat_id = int(row["category_id"])
            key = row["feature_key"]
            values = row["values"] or []
            if key is None:
                # категория без характеристик
                continue

            if cat_id not in by_cat:
                by_cat[cat_id] = {}
            by_cat[cat_id][key] = [v for v in values if v is not None]

    result: List[CategoryFeatures] = []
    for cat_id, kv in by_cat.items():
        keys = set(kv.keys())
        if not keys:
            # категорий без фич не берём в расчёт
            continue
        result.append(CategoryFeatures(category_id=cat_id, keys=keys, key_values=kv))

    print(f"[load_category_features] категорий: {len(result)}")
    return result


def compute_value_similarity(
    a: CategoryFeatures, b: CategoryFeatures, common_keys: List[str]
) -> float:
    """Средний Jaccard по значениям для общих ключей (для информации)."""
    sims: List[float] = []
    for k in common_keys:
        av = a.key_values.get(k, [])
        bv = b.key_values.get(k, [])
        if not av and not bv:
            continue
        sims.append(jaccard_values(av, bv))

    if not sims:
        return 0.0
    return sum(sims) / len(sims)


# порог по СТРУКТУРЕ (по ключам), а не по total_sim
KEY_SIM_THRESHOLD = 0.5


def rebuild_similarity_table():
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = False

    try:
        cats = load_category_features(conn)

        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE category_similarity;")

        rows_to_insert = []
        n = len(cats)
        print(f"[rebuild_similarity] считаем попарное сходство для {n} категорий")

        for i in range(n):
            a = cats[i]
            for j in range(i + 1, n):
                b = cats[j]

                # 1) Сходство по ключам (структура характеристик)
                key_sim = jaccard(a.keys, b.keys)
                if key_sim < KEY_SIM_THRESHOLD:
                    # структура сильно разная — не считаем похожими
                    continue

                common_keys = sorted(a.keys & b.keys)

                # 2) Сходство по значениям — только для информации
                value_sim = 0.0
                if common_keys:
                    value_sim = compute_value_similarity(a, b, common_keys)

                # 3) В таблицу кладём similarity = key_sim (чёткая интерпретация)
                total_sim = key_sim

                only_a_keys = sorted(a.keys - b.keys)
                only_b_keys = sorted(b.keys - a.keys)

                rows_to_insert.append(
                    (
                        a.category_id,
                        b.category_id,
                        round(total_sim, 4),   # similarity = по структуре
                        round(key_sim, 4),     # дублируем отдельно, если нужно
                        round(value_sim, 4),   # для анализа/отображения
                        common_keys,
                        only_a_keys,
                        only_b_keys,
                    )
                )

        print(f"[rebuild_similarity] всего пар для вставки: {len(rows_to_insert)}")

        if rows_to_insert:
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO category_similarity (
                        category_id_a,
                        category_id_b,
                        similarity,
                        key_similarity,
                        value_similarity,
                        common_keys,
                        only_a_keys,
                        only_b_keys
                    ) VALUES %s
                    """,
                    rows_to_insert,
                )

        conn.commit()
        print("[rebuild_similarity] готово, транзакция зафиксирована.")
    except Exception as e:
        conn.rollback()
        print("[rebuild_similarity] ОШИБКА, откат транзакции:", e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    rebuild_similarity_table()
