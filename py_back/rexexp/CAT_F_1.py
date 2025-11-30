import psycopg2
import psycopg2.extras

from dataclasses import dataclass
from typing import Dict, List, Set

import numpy as np
import torch
from transformers import AutoTokenizer, AutoModel


PG_DSN = "postgresql://th3_app:1234@localhost:5432/th3_db"

BASE_MODEL_NAME = "ai-forever/sbert_large_mt_nlu_ru"

# веса / пороги
KEY_WEIGHT = 0.3        # вклад структуры (какие ключи есть у товара)
EMB_WEIGHT = 0.7        # вклад семантики (название + значения характеристик)
SIM_THRESHOLD = 0.7     # минимум, чтобы считать товары похожими
TOP_K_NEIGHBORS = 5     # максимум "соседей" для одного товара (как KNN-граф)


@dataclass
class ProductFeatures:
    product_id: int
    name: str
    keys: Set[str]
    key_values: Dict[str, List[str]]


def jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union > 0 else 0.0


def load_product_features(conn) -> List[ProductFeatures]:
    """
    Подгони под свою схему:
    - product: id, name
    - product_feature: product_id, key, value
    """
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(
            """
            SELECT
              p.id   AS product_id,
              p.name AS product_name,
              pf.key AS feature_key,
              array_agg(DISTINCT pf.value) AS values
            FROM product p
            LEFT JOIN product_feature pf
              ON pf.product_id = p.id
            GROUP BY p.id, p.name, pf.key
            ORDER BY p.id, pf.key;
            """
        )

        by_prod: Dict[int, Dict[str, List[str]]] = {}
        prod_names: Dict[int, str] = {}

        for row in cur:
            pid = int(row["product_id"])
            name = row["product_name"] or ""
            key = row["feature_key"]
            values = row["values"] or []

            prod_names[pid] = name

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
        result.append(
            ProductFeatures(
                product_id=pid,
                name=prod_names.get(pid, ""),
                keys=keys,
                key_values=kv,
            )
        )

    print(f"[load_product_features] товаров: {len(result)}")
    return result


def build_product_text(prod: ProductFeatures) -> str:
    """
    Текстовое представление товара для SBERT:
    - название
    - все характеристики "Ключ: значения"
    """
    parts: List[str] = []
    if prod.name:
        parts.append(prod.name)

    for key, values in prod.key_values.items():
        if not values:
            continue
        val_str = ", ".join(sorted(set(str(v) for v in values if v)))
        if val_str:
            parts.append(f"{key}: {val_str}")

    return " ; ".join(parts)


def encode_texts(texts: List[str], device: str = None) -> np.ndarray:
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_NAME)
    model = AutoModel.from_pretrained(BASE_MODEL_NAME)
    model.to(device)
    model.eval()

    all_embeddings: List[np.ndarray] = []
    batch_size = 16

    with torch.no_grad():
        for start in range(0, len(texts), batch_size):
            batch_texts = texts[start:start+batch_size]
            enc = tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="pt",
            )
            input_ids = enc["input_ids"].to(device)
            attention_mask = enc["attention_mask"].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            last_hidden = outputs.last_hidden_state  # (B,L,H)

            mask = attention_mask.unsqueeze(-1)
            masked_hidden = last_hidden * mask
            summed = masked_hidden.sum(dim=1)
            counts = mask.sum(dim=1).clamp(min=1e-9)
            mean_pooled = summed / counts

            emb = mean_pooled.cpu().numpy()
            all_embeddings.append(emb)

    return np.vstack(all_embeddings)


def cosine_sim_matrix(emb: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9
    normed = emb / norms
    return normed @ normed.T

def rebuild_product_similarity():
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = False

    try:
        products = load_product_features(conn)
        n = len(products)
        print(f"[prod_sim] считаем похожесть для {n} товаров")

        if n == 0:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE product_similarity;")
            conn.commit()
            print("[prod_sim] нет товаров с фичами, таблица очищена.")
            return

        texts = [build_product_text(p) for p in products]
        print("[prod_sim] кодируем тексты в эмбеддинги...")
        emb = encode_texts(texts)
        print("[prod_sim] считаем косинусную матрицу...")
        cos_mat = cosine_sim_matrix(emb)

        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE product_similarity;")

        rows_to_insert = []
        seen_pairs = set()

        for i in range(n):
            a = products[i]

            # для каждого товара собираем локальных кандидатов
            local_candidates = []
            for j in range(n):
                if i == j:
                    continue
                b = products[j]

                key_sim = jaccard(a.keys, b.keys)
                emb_sim = float(cos_mat[i, j])
                total_sim = KEY_WEIGHT * key_sim + EMB_WEIGHT * emb_sim

                if total_sim < SIM_THRESHOLD:
                    continue

                local_candidates.append((j, total_sim, key_sim, emb_sim))

            if not local_candidates:
                continue

            # берём максимум TOP_K_NEIGHBORS
            local_candidates.sort(key=lambda x: x[1], reverse=True)
            for j, total_sim, key_sim, emb_sim in local_candidates[:TOP_K_NEIGHBORS]:
                b = products[j]
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
                        round(float(total_sim), 4),
                        round(float(key_sim), 4),
                        round(float(emb_sim), 4),
                        common_keys,
                        only_a_keys,
                        only_b_keys,
                    )
                )

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
        print("[prod_sim] готово, таблица product_similarity обновлена.")
    except Exception as e:
        conn.rollback()
        print("[prod_sim] ОШИБКА, откат:", e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    rebuild_product_similarity()
