import psycopg2
import psycopg2.extras

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple
from collections import defaultdict


PG_DSN = "postgresql://th3_app:1234@localhost:5432/th3_db"

# --- НАСТРОЙКИ СХОЖЕСТИ ---

SIM_THRESHOLD = 0.7          # минимум по Jaccard токенов (key=value)
MIN_COMMON_TOKENS = 2        # минимум общих токенов, чтобы вообще считать
MAX_TOKEN_BUCKET_SIZE = 100  # слишком частые токены выкидываем
TOP_K_NEIGHBORS = 5          # максимум соседей на товар

# для удобства: технические имена супергрупп
SF_SHINY          = "shiny"
SF_SPETSODEZHDA   = "spetsodezhda"
SF_ODEZHDA_VERH   = "odezhda_verh"
SF_ODEZHDA_MED    = "odezhda_med"
SF_ODEZHDA_OBYCH  = "odezhda_obych"
SF_OBUV           = "obuv"
SF_PERCHATKI      = "perchatki"
SF_SIZ            = "siz"
SF_HOZ            = "hoz"
SF_MED_IZD        = "med_izd"
SF_INSTRUMENT     = "instrument"
SF_HIM            = "him"
SF_ZAPCHASTI      = "zapchasti"
SF_SPETSOSNASTKA  = "spetsosnastka"
SF_OTHER          = "other"


@dataclass
class ProductFeatures:
    product_id: int
    name: str
    family_id: int  # может быть None
    super_family: str
    keys: Set[str]
    tokens: Set[str]  # key=value


def jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union > 0 else 0.0


def detect_super_family(name: str, keys: Set[str]) -> str:
    """
    Простая правиловая классификация товара в одну из супергрупп.
    Используем:
      - название (name)
      - набор ключей характеристик (keys)
    """
    if not name:
        name_l = ""
    else:
        name_l = name.lower()

    keys_l = {k.lower() for k in keys}

    # 1. ШИНЫ — по ключам и словам
    tyre_keys = {
        "диаметр посадочный",
        "индекс нагрузки",
        "индекс скорости",
        "отношение профиля",
        "ширина профиля",
        "норма слойности",
        "рисунок протектора",
        "протектор",
        "назначение шины",
    }
    if keys_l & tyre_keys:
        return SF_SHINY
    if any(sub in name_l for sub in ["шина ", "шины ", "покрышк", "r13", "r14", "r15", "r16", "r17", "r18"]):
        return SF_SHINY

    # 2. ОБУВЬ
    if any(
        sub in name_l
        for sub in ["обувь", "ботинк", "туфл", "сапог", "полуботин", "кроссовк", "галош", "валенк", "сланц", "сандал"]
    ):
        return SF_OBUV

    # 3. ПЕРЧАТКИ
    if any(sub in name_l for sub in ["перчатк", "рукавиц", "варежк", "нарукавник"]):
        return SF_PERCHATKI

    # 4. СИЗ (каски, очки, респираторы и т.п.)
    if any(
        sub in name_l
        for sub in [
            "респиратор",
            "каска",
            "щиток",
            "защитн",  # в сочетании с очками / шлемами и т.п.
            "очки защит",
            "наушники противошум",
            "противошумные",
            "привязь",
            "страховоч",
            "самоспасател",
        ]
    ):
        return SF_SIZ

    # 5. СПЕЦОДЕЖДА (защитная, сигнальная и т.п.)
    if any(
        sub in name_l
        for sub in [
            "одежда специальная",
            "спецодежд",
            "костюм сигналь",
            "костюм защитн",
            "боевоя одежда пожарного",
            "боеприпас"  # осторожно, но пусть будет
        ]
    ):
        return SF_SPETSODEZHDA

    # 6. ОДЕЖДА МЕД
    if "медицинск" in name_l or "пациент" in name_l:
        # но если это не обувь/перчатки/СИЗ
        if not any(sub in name_l for sub in ["ботинк", "туфл", "сапог", "перчатк", "респиратор", "каска"]):
            return SF_ODEZHDA_MED

    # 7. ОДЕЖДА ВЕРХНЯЯ (куртки, жилеты, пальто, ветровки)
    if any(
        sub in name_l
        for sub in ["куртк", "ветровк", "пальто", "полупальто", "парка", "анорак", "жилет"]
    ):
        # если в названии явно мед/спец — тогда те классifikаторы уже сработали выше
        return SF_ODEZHDA_VERH

    # 8. ОДЕЖДА ОБЫЧНАЯ (брюки/сорочки/футболки/юбки/платья и т.п.)
    if any(
        sub in name_l
        for sub in [
            "брюк",
            "сорочк",
            "рубашк",
            "футболк",
            "платье",
            "юбк",
            "шорт",
            "джемпер",
            "свитер",
            "толстовк",
            "жилет",
        ]
    ):
        return SF_ODEZHDA_OBYCH

    # 9. МЕДИЦИНСКИЕ ИЗДЕЛИЯ (не одежда)
    if any(
        sub in name_l
        for sub in [
            "шприц",
            "катетер",
            "бинт",
            "марл",
            "пластыр",
            "игл",
            "скальпел",
            "инфуз",
            "система перелив",
            "зонд",
            "раствор для инъек",
        ]
    ):
        return SF_MED_IZD

    # 10. ЖИДКОСТИ / ХИМИЯ
    if any(
        sub in name_l
        for sub in [
            "масло",
            "смазк",
            "раствор",
            "жидк",
            "кислот",
            "щелоч",
            "реагент",
            "растворител",
            "моющ",
            "шампун",
            "антисепт",
            "спирт",
        ]
    ):
        return SF_HIM

    # 11. МЕШКИ / ХОЗТОВАРЫ
    if any(
        sub in name_l
        for sub in [
            "мешок",
            "мешки",
            "полотенц",
            "салфетк",
            "ведро",
            "таз",
            "швабр",
            "тряпк",
            "хоз",
            "пакет",
        ]
    ):
        return SF_HOZ

    # 12. ИНСТРУМЕНТЫ
    if any(
        sub in name_l
        for sub in [
            "ключ",
            "отвертк",
            "молоток",
            "кусач",
            "пассатиж",
            "инструмент",
            "шуруповерт",
            "дрель",
            "пила",
        ]
    ):
        return SF_INSTRUMENT

    # 13. ЗАПЧАСТИ
    if any(
        sub in name_l
        for sub in [
            "запчаст",
            "запасная часть",
            "фильтр",
            "подшипн",
            "сальник",
            "патрубок",
            "шланг",
            "муфта",
            "колодк",
            "клапан",
        ]
    ):
        return SF_ZAPCHASTI

    # 14. СПЕЦОСНАСТКА / СНАРЯЖЕНИЕ
    if any(
        sub in name_l
        for sub in [
            "снаряжен",
            "оснастк",
            "строп",
            "карабин",
            "такелаж",
            "стропы",
            "анкер",
            "стяжка ременная",
        ]
    ):
        return SF_SPETSOSNASTKA

    # 15. По ключам можно ещё раз понять одежду
    if any(k in keys_l for k in ["размер", "рост", "обхват груди"]):
        return SF_ODEZHDA_OBYCH

    return SF_OTHER


def load_product_features(conn) -> List[ProductFeatures]:
    """
    Тянем товары, семейства категорий и характеристики.

    Ожидаем схему:
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
                continue

            if pid not in by_prod:
                by_prod[pid] = {}
            by_prod[pid][key] = [v for v in values if v is not None]

    result: List[ProductFeatures] = []
    for pid, kv in by_prod.items():
        keys = set(kv.keys())
        if not keys:
            continue

        tokens: Set[str] = set()
        for k, vs in kv.items():
            for v in vs:
                tokens.add(f"{k}={v}")

        family_id = prod_family.get(pid)
        name = prod_names.get(pid, "")

        sf = detect_super_family(name, keys)

        result.append(
            ProductFeatures(
                product_id=pid,
                name=name,
                family_id=family_id,
                super_family=sf,
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
            f"(супергруппы + по характеристикам, SIM_THRESHOLD={SIM_THRESHOLD})"
        )

        if n == 0:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE product_similarity;")
            conn.commit()
            print("[prod_sim] нет товаров с фичами, таблица product_similarity очищена.")
            return

        # 1. Разбиваем по семействам категорий (для производительности)
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

            # 2. Внутри семейства делим по super_family + набору ключей
            buckets: Dict[Tuple[str, str], List[ProductFeatures]] = defaultdict(list)
            for p in prods:
                fp_keys = "||".join(sorted(p.keys))
                key = (p.super_family, fp_keys)
                buckets[key].append(p)

            for (sf, fp_keys), bucket_prods in buckets.items():
                size = len(bucket_prods)
                if size <= 1:
                    continue

                print(f"[prod_sim]   super_family={sf}, ключи={fp_keys}, товаров={size}")

                # индекс по токенам внутри этого бакета
                token_index: Dict[str, List[int]] = defaultdict(list)
                for idx, prod in enumerate(bucket_prods):
                    for token in prod.tokens:
                        token_index[token].append(idx)

                pair_scores: Dict[Tuple[int, int], int] = defaultdict(int)

                for token, idx_list in token_index.items():
                    L = len(idx_list)
                    if L <= 1:
                        continue
                    if L > MAX_TOKEN_BUCKET_SIZE:
                        continue

                    for pos_i in range(L):
                        i = idx_list[pos_i]
                        for pos_j in range(pos_i + 1, L):
                            j = idx_list[pos_j]
                            if i == j:
                                continue
                            a_idx, b_idx = (i, j) if i < j else (j, i)
                            pair_scores[(a_idx, b_idx)] += 1

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

                        # ключи в бакете одинаковые => key_sim = 1.0
                        key_sim = 1.0
                        a_keys = a.keys
                        b_keys = b.keys
                        common_keys = sorted(a_keys & b_keys)
                        only_a_keys = sorted(a_keys - b_keys)
                        only_b_keys = sorted(b_keys - a_keys)

                        local_pairs.append(
                            (
                                a_id,
                                b_id,
                                round(float(token_sim), 4),  # similarity
                                round(float(key_sim), 4),    # key_similarity
                                round(float(token_sim), 4),  # value_similarity
                                common_keys,
                                only_a_keys,
                                only_b_keys,
                            )
                        )

                print(
                    f"[prod_sim]   super_family={sf}, ключи={fp_keys}: "
                    f"пар после фильтров={len(local_pairs)}"
                )
                rows_to_insert.extend(local_pairs)

        # 1) семейства
        for fam_id, prods in by_family.items():
            process_bucket(f"family_{fam_id}", prods)

        # 2) товары без семейства
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
            "(с учётом супергрупп и характеристик)."
        )
    except Exception as e:
        conn.rollback()
        print("[prod_sim] ОШИБКА, откат:", e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    rebuild_product_similarity()
