import os
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

import psycopg2
import psycopg2.extras

import numpy as np
import torch
from transformers import AutoTokenizer, AutoModel


PG_DSN = "postgresql://th3_app:1234@localhost:5432/th3_db"

# та же модель, что и в train_characteristics_model_v4 / runtime_characteristics_model_v4
BASE_MODEL_NAME = "ai-forever/sbert_large_mt_nlu_ru"

# веса и пороги "интеллектуальности"
KEY_WEIGHT = 0.3       # вклад Jaccard по ключам
EMB_WEIGHT = 0.7       # вклад семантического сходства по эмбеддингам
SIM_THRESHOLD = 0.55   # итоговый порог: чем выше, тем "родственнее" пары


@dataclass
class CategoryFeatures:
    category_id: int
    name: str
    keys: Set[str]
    key_values: Dict[str, List[str]]  # key -> список значений (array_agg)


def jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
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
              c.id   AS category_id,
              c.name AS category_name,
              cf.key AS feature_key,
              array_agg(DISTINCT cf.value) AS values
            FROM product_category c
            LEFT JOIN category_feature cf
              ON cf.category_id = c.id
            GROUP BY c.id, c.name, cf.key
            ORDER BY c.id, cf.key;
            """
        )

        by_cat: Dict[int, Dict[str, List[str]]] = {}
        cat_names: Dict[int, str] = {}

        for row in cur:
            cat_id = int(row["category_id"])
            name = row["category_name"] or ""
            key = row["feature_key"]
            values = row["values"] or []

            cat_names[cat_id] = name

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
        result.append(
            CategoryFeatures(
                category_id=cat_id,
                name=cat_names.get(cat_id, ""),
                keys=keys,
                key_values=kv,
            )
        )

    print(f"[load_category_features] категорий: {len(result)}")
    return result


def build_category_text(cat: CategoryFeatures) -> str:
    """
    Собираем текстовое представление категории для эмбеддинга:
    - название категории
    - перечисление "Ключ: значение1, значение2, ..."
    """
    parts: List[str] = []
    if cat.name:
        parts.append(cat.name)

    for key, values in cat.key_values.items():
        if not values:
            continue
        val_str = ", ".join(sorted(set(str(v) for v in values if v)))
        if val_str:
            parts.append(f"{key}: {val_str}")

    return " ; ".join(parts)


def encode_texts(texts: List[str], device: str = None) -> np.ndarray:
    """
    Кодируем список текстов в эмбеддинги SBERT (mean pooling).
    Возвращаем numpy-массив shape (N, hidden_size).
    """
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
            batch_texts = texts[start:start + batch_size]
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
            last_hidden = outputs.last_hidden_state  # (B, L, H)

            # mean pooling по маске
            mask = attention_mask.unsqueeze(-1)  # (B, L, 1)
            masked_hidden = last_hidden * mask
            summed = masked_hidden.sum(dim=1)          # (B, H)
            counts = mask.sum(dim=1).clamp(min=1e-9)   # (B, 1)
            mean_pooled = summed / counts              # (B, H)

            emb = mean_pooled.cpu().numpy()
            all_embeddings.append(emb)

    return np.vstack(all_embeddings)  # (N, H)


def cosine_sim_matrix(emb: np.ndarray) -> np.ndarray:
    """
    Косинусное сходство всех со всеми.
    emb: (N, H)
    return: (N, N)
    """
    # L2-нормировка
    norms = np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9
    normed = emb / norms
    return normed @ normed.T


def rebuild_similarity_table():
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = False

    try:
        cats = load_category_features(conn)
        n = len(cats)
        print(f"[rebuild_similarity] считаем попарное сходство для {n} категорий")

        if n == 0:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE category_similarity;")
            conn.commit()
            print("[rebuild_similarity] нет категорий с фичами, таблица очищена.")
            return

        # 1) Строим тексты и эмбеддинги
        texts = [build_category_text(c) for c in cats]
        print("[rebuild_similarity] кодируем тексты в эмбеддинги...")
        emb = encode_texts(texts)  # (N, H)
        print("[rebuild_similarity] эмбеддинги готовы, считаем косинусную матрицу...")
        cos_mat = cosine_sim_matrix(emb)  # (N, N)

        # 2) Чистим таблицу
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE category_similarity;")

        # 3) Считаем сочетания пар
        rows_to_insert = []

        for i in range(n):
            a = cats[i]
            for j in range(i + 1, n):
                b = cats[j]

                # сходство по структуре (Jaccard по ключам)
                key_sim = jaccard(a.keys, b.keys)

                # семантическое сходство по эмбеддингам
                emb_sim = float(cos_mat[i, j])

                # комбинируем
                total_sim = KEY_WEIGHT * key_sim + EMB_WEIGHT * emb_sim

                if total_sim < SIM_THRESHOLD:
                    continue

                common_keys = sorted(a.keys & b.keys)
                only_a_keys = sorted(a.keys - b.keys)
                only_b_keys = sorted(b.keys - a.keys)

                rows_to_insert.append(
                    (
                        a.category_id,
                        b.category_id,
                        round(total_sim, 4),  # итоговая умная метрика
                        round(key_sim, 4),    # структура
                        round(emb_sim, 4),    # семантика (эмбеддинг)
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
