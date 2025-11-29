# universal_characteristics_extractor_v3.py
# Полностью переписанная и исправленная версия

import re
import json
import math
import logging
from pathlib import Path
from typing import List, Dict, Tuple
from collections import Counter, defaultdict

import pandas as pd
import chardet
import torch
from tqdm import tqdm
from sentence_transformers import SentenceTransformer, util

# ============================= CONFIG =============================

CSV_PATH = "py_back/rexexp/data/result_itr4.csv"
OUTPUT_DIR = "result"

MIN_SUPPORT = 5
TOP_K = 15
SIMILARITY_THRESHOLD = 0.85

MODEL_NAME = "ai-forever/sbert_large_mt_nlu_ru"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("v3.log", encoding="utf-8")]
)
logger = logging.getLogger(__name__)

# ============================= NORMALIZATION MAP =============================
# Полная нормализация ключей по словарю
NORMALIZATION_MAP = {
    # Общие
    "вид": "Вид",
    "вид продукции": "Вид",
    "вид товаров": "Вид",
    "вид продукции товары": "Вид",
    "вид шин, покрышек и камер резиновых": "Тип шины",
    "вид шин": "Тип шины",
    "вид запчасти": "Тип запчасти",

    # Шины
    "номинальная ширина профиля": "Ширина профиля",
    "обозначение номинальной ширины профиля": "Ширина профиля",
    "ширина профиля": "Ширина профиля",

    "номинальный посадочный диаметр обода": "Диаметр посадочный",
    "диаметр посадочный": "Диаметр посадочный",
    "посадочный диаметр": "Диаметр посадочный",

    "номинальное отношение высоты профиля": "Отношение профиля",
    "отношение высоты профиля": "Отношение профиля",
    "высота профиля": "Отношение профиля",

    # Дополнительные
    "назначение пневматических шин": "Назначение",
    "категория использования шины": "Категория использования",

    "модель": "Модель",
    "производитель": "Производитель",
    "страна происхождения": "Страна",
    "страна": "Страна",

    "индекс нагрузки": "Индекс нагрузки",
    "индекс категории скорости": "Индекс скорости",
    "индекс скорости": "Индекс скорости",

    "тип": "Тип",
    "тип конструкции пневматических шин": "Тип конструкции",
}

STOP_WORDS = {"нет", "да", "none", "nan", "null", "undefined", "", "-"}

# ============================= MODEL =============================
try:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(MODEL_NAME, device=device)
    logger.info(f"Эмбеддинг-модель загружена ({device})")
except Exception as e:
    logger.error(f"Ошибка загрузки эмбеддингов: {e}")
    model = None


# ============================= TEXT UTILS =============================

def detect_encoding(path: str) -> str:
    with open(path, "rb") as f:
        return chardet.detect(f.read(20000)).get("encoding", "utf-8")


def preprocess(text: str) -> str:
    text = str(text).replace(";", " ; ").replace(",", " , ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ============================= EXTRACTOR =============================

def extract_key_value_pairs(text: str) -> List[Tuple[str, str]]:
    """
    ВАЖНО: извлекаем только полноценные "Ключ: Значение".
    Без обрезаний, без срезов, без ломания слов.
    """
    text = preprocess(text)

    pattern = r"([A-Za-zА-Яа-яёЁ0-9 ,\-()]{2,80}?)\s*:\s*([^;,\n]+)"
    matches = re.findall(pattern, text)

    result = []

    for key, value in matches:
        key = key.strip()
        value = value.strip()

        if not key or not value:
            continue
        if key.lower() in STOP_WORDS or value.lower() in STOP_WORDS:
            continue
        if len(value) > 200:  # не брать мегадлины
            continue

        result.append((key, value))

    return result


# ============================= NORMALIZATION =============================

def normalize_key(key: str) -> str:
    k = key.lower().strip()

    for raw, norm in NORMALIZATION_MAP.items():
        if raw in k:
            return norm

    return key.capitalize()


def normalize_characters(pairs: List[Tuple[str, str]]) -> List[str]:
    """
    Пары (key, value) → "NormKey: Value"
    """
    normalized = []
    for key, value in pairs:
        norm_key = normalize_key(key)
        value = value.strip()

        if value.lower() in STOP_WORDS:
            continue

        normalized.append(f"{norm_key}: {value}")

    return normalized


# ============================= DEDUPLICATION =============================

def smart_dedupe(chars: List[str], top_k: int = TOP_K) -> List[str]:
    """
    Дедупликация через эмбеддинги + частотность.
    """
    if not chars:
        return []

    counter = Counter(chars)
    common = [c for c, _ in counter.most_common(top_k * 2)]

    if model is None or len(common) <= top_k:
        return common[:top_k]

    embeddings = model.encode(common, convert_to_tensor=True)

    kept = []
    for i, c in enumerate(common):
        if len(kept) >= top_k:
            break

        skip = False
        for j in kept:
            sim = util.cos_sim(embeddings[i], embeddings[j]).item()
            if sim > SIMILARITY_THRESHOLD:
                skip = True
                break

        if not skip:
            kept.append(i)

    return [common[i] for i in kept]


# ============================= TF-IDF SIGNIFICANCE =============================

def compute_significant_features(category_chars: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    TF-IDF оценка важности признаков для каждой категории.
    """
    logger.info("Вычисление значимых признаков (TF-IDF)…")

    cat_tf = {cat: Counter(chars) for cat, chars in category_chars.items()}

    # document frequency
    df = Counter()
    for counter in cat_tf.values():
        for feat in counter:
            df[feat] += 1

    N = len(cat_tf)
    result = {}

    for cat, counter in cat_tf.items():
        if sum(counter.values()) < MIN_SUPPORT:
            continue

        scored = []
        for feat, cnt in counter.items():
            score = cnt * math.log((1 + N) / (1 + df[feat]))
            scored.append((feat, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top = [f for f, _ in scored[:TOP_K * 2]]

        deduped = smart_dedupe(top, top_k=TOP_K)
        result[cat] = deduped

    return result


# ============================= PIPELINE =============================

def load_data() -> pd.DataFrame:
    enc = detect_encoding(CSV_PATH)
    df = pd.read_csv(CSV_PATH, dtype=str, low_memory=False, encoding=enc).fillna("")

    spec_cols = [c for c in df.columns if c.startswith("spec")]

    text_cols = []
    for col in ["название_сте", "производитель", "страна_происхождения", "название_категории"]:
        if col in df.columns:
            text_cols.append(col)

    text_cols += spec_cols

    df["all_text"] = df[text_cols].apply(
        lambda row: " ; ".join([str(x) for x in row if x not in ("", "nan", "None")]),
        axis=1
    )

    df = df[df["all_text"].str.len() > 3]
    return df


def extract_by_categories(df: pd.DataFrame):
    category_chars = defaultdict(list)
    category_counts = defaultdict(int)

    for _, row in tqdm(df.iterrows(), total=len(df)):
        cat = str(row["id_категории"])
        text = row["all_text"]

        raw_pairs = extract_key_value_pairs(text)
        normalized = normalize_characters(raw_pairs)

        if normalized:
            category_chars[cat].extend(normalized)
            category_counts[cat] += 1

    return category_chars, category_counts


# ============================= SAVE =============================

def save_ontology(result: Dict[str, List[str]], counts: Dict[str, int], total_rows: int):
    Path(OUTPUT_DIR).mkdir(exist_ok=True)

    out = {
        "meta": {
            "total_rows": total_rows,
            "categories": len(result),
            "min_support": MIN_SUPPORT,
            "top_k": TOP_K,
            "model": MODEL_NAME,
        },
        "categories": {}
    }

    for cat, chars in result.items():
        out["categories"][cat] = {
            "characteristics": chars,
            "total_items": counts.get(cat, 0)
        }

    path = Path(OUTPUT_DIR) / "ontology_v3.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    logger.info(f"Онтология сохранена в {path}")


# ============================= MAIN =============================

def main():
    logger.info("🚀 Старт universal_characteristics_extractor_v3")

    df = load_data()

    category_chars, category_counts = extract_by_categories(df)

    significant = compute_significant_features(category_chars)

    save_ontology(significant, category_counts, len(df))

    logger.info("✅ Готово: онтология V3 создана.")


if __name__ == "__main__":
    main()
