import psycopg2
import psycopg2.extras

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple


PG_DSN = "postgresql://th3_app:1234@localhost:5432/th3_db"

# веса / пороги
KEY_WEIGHT = 0.3        # вклад структуры (набор ключей)
TOKEN_WEIGHT = 0.7      # вклад значений (key=value)
SIM_THRESHOLD = 0.6     # минимум, чтобы считать товары похожими
MIN_KEY_SIM = 0.3       # если по ключам меньше этого — даже не считаем дальше

# если хочешь жёстко ограничить число связей на товар — можно включить TOP_K
TOP_K_NEIGHBORS = None  # или, например, 10; None = без ограничения


@dataclass
class ProductFeatures:
    product_id: int
    name: str
    family_id: int  # может быть None, если семья не найдена
    keys: Set[str]
    tokens: Set[str]  # key=value


def jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union > 0 else 0.0


def load_product_features(conn) -> List[ProductFeatures]:
    """
    Загружаем товары, их семейства категорий и характеристики.

    Ожидаем схему (подгони под себя, если нужно):
      - product (id, name, category_id)
      - category_family_member (family_id, category_id)
      - product_feature (product_id, key, value)
    """
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(
            """
            SELECT
              p.id                   AS product_id,
              p.name                 AS product_name,
              cfam.family_id         AS family_id,
              pf.key                 AS feature_key,
              array_agg(DISTINCT pf.value) AS values
            FROM product p
            LEFT JOIN product_feature pf
              ON pf.product_id = p.id
            LEFT JOIN product_category pc
              ON pc.id = p.category_id
            LEFT JOIN category_family_member cfam
              ON cfam.category_id = pc.id
            GROUP BY p.id, p.name, cfam.family_id, pf.key
            ORDER BY cfam.family_id NULLS LAST, p.id, pf.key;
            """
        )

        by_prod: Dict[int, Dict[str, List[str]]] = {}
        prod_names: Dict[int, str] = {}
        prod_family: Dict[int, int] = {}

        for row in cur:
            pid = int(row["product_id"])
            name = row["product_name"] or ""
            family_id = row["family_id"]
            key = row["feature_key"]
            values = row["values"] or []

            prod_names[pid] = name
            if family_id is not None:
                prod_family[pid] = int(family_id)

            if key is None:
                # товаров без характеристик можно либо брать, либо пропустить
                continue

            if pid not in by_prod:
                by_prod[pid] = {}
            by_prod[pid][key] = [v for v in values if v is not None]

    result: List[ProductFeatures] = []
    for pid, kv in by_prod.items():
        keys = set(kv.keys())
        if not keys:
            continue

        # токены key=value
        tokens: Set[str] = set()
        for k, vs in kv.items():
            for v in vs:
                tokens.add(f"{k}={v}")

        family_id = prod_family.get(pid)  # может быть None

        result.append(
            ProductFeatures(
                product_id=pid,
                name=prod_names.get(pid, ""),
                family_id=family_id,
                keys=keys,
                tokens=tokens,
            )
        )

    print(f"[load_product_features] товаров: {len(result)}")
    return result


def rebuild_product_similarity():
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = False

    try:
        products = load_product_features(conn)
        n = len(products)
        print(f"[prod_sim] считаем похожесть для {n} товаров (без нейросетей)")

        if n == 0:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE product_similarity;")
            conn.commit()
            print("[prod_sim] нет товаров с фичами, таблица product_similarity очищена.")
            return

        # Разбиваем товары по семействам категорий (family_id)
        by_family: Dict[int, List[ProductFeatures]] = {}
        no_family: List[ProductFeatures] = []

        for p in products:
            if p.family_id is None:
                no_family.append(p)
            else:
                by_family.setdefault(p.family_id, []).append(p)

        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE product_similarity;")

        rows_to_insert = []
        seen_pairs = set()

        def process_bucket(bucket_name: str, prods: List[ProductFeatures]):
            m = len(prods)
            print(f"[prod_sim] bucket={bucket_name}, товаров={m}")
            for i in range(m):
                a = prods[i]
                local_candidates: List[Tuple[int, float, float, float]] = []

                for j in range(i + 1, m):
                    b = prods[j]

                    key_sim = jaccard(a.keys, b.keys)
                    if key_sim < MIN_KEY_SIM:
                        continue

                    token_sim = jaccard(a.tokens, b.tokens)
                    total_sim = KEY_WEIGHT * key_sim + TOKEN_WEIGHT * token_sim

                    if total_sim < SIM_THRESHOLD:
                        continue

                    local_candidates.append((j, total_sim, key_sim, token_sim))

                # если хотим ограничивать количество связей на товар
                if TOP_K_NEIGHBORS is not None and local_candidates:
                    local_candidates.sort(key=lambda x: x[1], reverse=True)
                    local_candidates_cut = local_candidates[:TOP_K_NEIGHBORS]
                else:
                    local_candidates_cut = local_candidates

                for j, total_sim, key_sim, token_sim in local_candidates_cut:
                    b = prods[j]
                    a_id = a.product_id
                    b_id = b.product_id

                    if a_id == b_id:
                        continue
                    if a_id > b_id:
                        a_id, b_id = b_id, a_id
                        a_keys, b_keys = b.keys, a.keys
                    else:
                        a_keys, b_keys = a.keys, b.keys

                    pair_key = (a_id, b_id)
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    common_keys = sorted(a_keys & b_keys)
                    only_a_keys = sorted(a_keys - b_keys)
                    only_b_keys = sorted(b_keys - a_keys)

                    rows_to_insert.append(
                        (
                            a_id,
                            b_id,
                            round(float(total_sim), 4),    # similarity (итог)
                            round(float(key_sim), 4),      # по структуре
                            round(float(token_sim), 4),    # по значениям (key=value)
                            common_keys,
                            only_a_keys,
                            only_b_keys,
                        )
                    )

        # 1) обработать все семейства
        for fam_id, prods in by_family.items():
            process_bucket(f"family_{fam_id}", prods)

        # 2) товары без семейства — одним бакетом (как "прочие")
        if no_family:
            process_bucket("no_family", no_family)

        print(f"[prod_sim] всего пар для вставки: {len(rows_to_insert)}")

        if rows_to_insert:
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO product_similarity (
                        product_id_a,
                        product_id_b,
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
        print("[prod_sim] готово, таблица product_similarity обновлена (без SBERT).")
    except Exception as e:
        conn.rollback()
        print("[prod_sim] ОШИБКА, откат:", e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    rebuild_product_similarity()
