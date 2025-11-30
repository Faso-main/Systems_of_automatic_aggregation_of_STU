import psycopg2
import psycopg2.extras

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple
from collections import defaultdict


PG_DSN = "postgresql://th3_app:1234@localhost:5432/th3_db"

# --- НАСТРОЙКИ СХОЖЕСТИ ---

# итоговая метрика = token_sim (т.к. ключи в бакете одинаковые)
SIM_THRESHOLD = 0.7          # минимум по token_sim

# минимальное число общих токенов, чтобы вообще считать Jaccard
MIN_COMMON_TOKENS = 2

# ограничение на размер бакета по одному токену:
# если токен встречается у > N товаров, он считается слишком общим и пропускается
MAX_TOKEN_BUCKET_SIZE = 100

# максимум соседей на один товар (чтобы не было "звёзд")
TOP_K_NEIGHBORS = 5


@dataclass
class ProductFeatures:
    product_id: int
    name: str
    family_id: int  # может быть None, если семейство не найдено
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
      - product_category (id)
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
                # товар без характеристик — пока пропускаем
                continue

            if pid not in by_prod:
                by_prod[pid] = {}
            by_prod[pid][key] = [v for v in values if v is not None]

    result: List[ProductFeatures] = []
    for pid, kv in by_prod.items():
        keys = set(kv.keys())
        if not keys:
            continue

        # токены вида "Ключ=Значение"
        tokens: Set[str] = set()
        for k, vs in kv.items():
            for v in vs:
                tokens.add(f"{k}={v}")

        family_id = prod_family.get(pid)

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
        print(
            f"[prod_sim] считаем похожесть для {n} товаров "
            f"(по характеристикам без нейросетей, SIM_THRESHOLD={SIM_THRESHOLD})"
        )

        if n == 0:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE product_similarity;")
            conn.commit()
            print("[prod_sim] нет товаров с фичами, таблица product_similarity очищена.")
            return

        # 1. Разбиваем по семействам категорий
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
            if m <= 1:
                return

            # 2. Внутри семейства разбиваем по набору ключей (fingerprint)
            buckets_by_keys: Dict[str, List[ProductFeatures]] = defaultdict(list)
            for p in prods:
                fp = "||".join(sorted(p.keys))
                buckets_by_keys[fp].append(p)

            bucket_pairs_count = 0

            for fp, bucket_prods in buckets_by_keys.items():
                size = len(bucket_prods)
                if size <= 1:
                    continue

                print(f"[prod_sim]   ключи={fp}, товаров={size}")

                # Индекс по токенам внутри этого ключевого бакета
                token_index: Dict[str, List[int]] = defaultdict(list)
                for idx, prod in enumerate(bucket_prods):
                    for token in prod.tokens:
                        token_index[token].append(idx)

                # pair_scores[(i,j)] = количество общих токенов
                pair_scores: Dict[Tuple[int, int], int] = defaultdict(int)

                for token, idx_list in token_index.items():
                    L = len(idx_list)
                    if L <= 1:
                        continue
                    if L > MAX_TOKEN_BUCKET_SIZE:
                        # слишком частый токен, пропускаем
                        continue

                    for pos_i in range(L):
                        i = idx_list[pos_i]
                        for pos_j in range(pos_i + 1, L):
                            j = idx_list[pos_j]
                            if i == j:
                                continue
                            a_idx, b_idx = (i, j) if i < j else (j, i)
                            pair_scores[(a_idx, b_idx)] += 1

                # Считаем Jaccard по токенам только для пар с достаточным пересечением
                neighbors_by_idx: Dict[int, List[Tuple[int, float]]] = defaultdict(list)

                for (i, j), common_count in pair_scores.items():
                    if common_count < MIN_COMMON_TOKENS:
                        continue

                    a = bucket_prods[i]
                    b = bucket_prods[j]

                    token_sim = jaccard(a.tokens, b.tokens)
                    if token_sim < SIM_THRESHOLD:
                        continue

                    neighbors_by_idx[i].append((j, token_sim))
                    neighbors_by_idx[j].append((i, token_sim))

                # Ограничиваем TOP_K_NEIGHBORS для каждого товара и записываем пары
                local_pairs = []

                for i, neigh_list in neighbors_by_idx.items():
                    if not neigh_list:
                        continue

                    if TOP_K_NEIGHBORS is not None and len(neigh_list) > TOP_K_NEIGHBORS:
                        neigh_list.sort(key=lambda x: x[1], reverse=True)
                        neigh_list = neigh_list[:TOP_K_NEIGHBORS]

                    for j, token_sim in neigh_list:
                        a = bucket_prods[i]
                        b = bucket_prods[j]
                        a_id = a.product_id
                        b_id = b.product_id

                        if a_id == b_id:
                            continue
                        if a_id > b_id:
                            a_id, b_id = b_id, a_id
                        pair_key = (a_id, b_id)
                        if pair_key in seen_pairs:
                            continue
                        seen_pairs.add(pair_key)

                        # ключи одинаковые в бакете => key_similarity = 1.0
                        key_sim = 1.0
                        # общие/отсутствующие ключи — для инфы
                        a_keys = a.keys
                        b_keys = b.keys
                        common_keys = sorted(a_keys & b_keys)
                        only_a_keys = sorted(a_keys - b_keys)
                        only_b_keys = sorted(b_keys - a_keys)

                        local_pairs.append(
                            (
                                a_id,
                                b_id,
                                round(float(token_sim), 4),  # similarity = token_sim
                                round(float(key_sim), 4),    # = 1.0
                                round(float(token_sim), 4),  # value_similarity = token_sim
                                common_keys,
                                only_a_keys,
                                only_b_keys,
                            )
                        )

                bucket_pairs_count += len(local_pairs)
                rows_to_insert.extend(local_pairs)

            print(f"[prod_sim] bucket={bucket_name}: пар после фильтров={bucket_pairs_count}")

        # 1) Обрабатываем все семейства
        for fam_id, prods in by_family.items():
            process_bucket(f"family_{fam_id}", prods)

        # 2) Товары без семейства — один общий бакет
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
        print(
            "[prod_sim] готово, таблица product_similarity обновлена "
            "(по характеристикам, с разбиением по ключам)."
        )
    except Exception as e:
        conn.rollback()
        print("[prod_sim] ОШИБКА, откат:", e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    rebuild_product_similarity()
