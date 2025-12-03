# universal_characteristics_extractor_v5.py
# V5: всё из V4 + построение схемы атрибутов (attributes) по категориям

import re
import json
import math
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import Counter, defaultdict

import pandas as pd
import chardet
import torch
from tqdm import tqdm
from sentence_transformers import SentenceTransformer, util

# ============================= CONFIG =============================

CSV_PATH = "py_back/rexexp/data/result_itr4.csv"
OUTPUT_DIR = "result"

MIN_SUPPORT = 5          # минимум товаров с характеристиками в категории
TOP_K = 15              # целевое число характеристик на категорию
SIMILARITY_THRESHOLD = 0.85
GLOBAL_DF_FRACTION = 0.4  # если признак встречается > 40% категорий — выкидываем как неинформативный

MODEL_NAME = "ai-forever/sbert_large_mt_nlu_ru"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("universal_characteristics_v5.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ============================= НОРМАЛИЗАЦИЯ КЛЮЧЕЙ =============================

NORMALIZATION_MAP = {
    # Общие
    "вид продукции товары": "Вид",
    "вид продукции": "Вид",
    "вид товаров": "Вид",
    "вид": "Вид",

    # Шины
    "вид шин, покрышек и камер резиновых": "Тип шины",
    "вид шин пневматические": "Тип шины",
    "вид шин": "Тип шины",
    "вид запчасти": "Тип запчасти",

    "номинальная ширина профиля": "Ширина профиля",
    "обозначение номинальной ширины профиля": "Ширина профиля",
    "ширина профиля": "Ширина профиля",

    "номинальный посадочный диаметр обода": "Диаметр посадочный",
    "диаметр посадочный": "Диаметр посадочный",
    "посадочный диаметр": "Диаметр посадочный",

    "номинальное отношение высоты профиля": "Отношение профиля",
    "отношение высоты профиля": "Отношение профиля",
    "высота профиля": "Отношение профиля",

    "назначение пневматических шин": "Назначение",
    "категория использования шины": "Категория использования",

    "модель": "Модель",
    "производитель": "Производитель",
    "страна происхождения": "Страна",
    "страна": "Страна",

    "индекс нагрузки": "Индекс нагрузки",
    "индекс категории скорости": "Индекс скорости",
    "индекс скорости": "Индекс скорости",

    "тип конструкции пневматических шин": "Тип конструкции",
    "тип конструкции": "Тип конструкции",
    "тип": "Тип",
}

STOP_WORDS = {"нет", "да", "none", "nan", "null", "undefined", "", "-", "0", "1"}

GENERIC_VID_VALUES = {
    "товары",
    "одежда",
    "одежда для взрослых",
    "транспортные средства",
    "запасные части",
    "спецодежда (специальная экипировка)",
    "головные уборы",
    "одежда специальная",
    "стандартный",
    "стандартный вид",
}

GENERIC_STD_TOKENS = {
    "тр тс",
    "тp тс",
    "gost",
    "гост",
    "en ",
    "iso",
    "стандарты",
    "стандарт",
    "заключение минпромторга",
}

BOOLEAN_VALUES_TRUE = {"да", "true", "есть", "имеется"}
BOOLEAN_VALUES_FALSE = {"нет", "false", "отсутствует"}


# ============================= МОДЕЛЬ ЭМБЕДДИНГОВ =============================

try:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(MODEL_NAME, device=device)
    logger.info(f"Эмбеддинг-модель {MODEL_NAME} загружена на {device}")
except Exception as e:
    logger.error(f"Ошибка загрузки эмбеддингов: {e}")
    model = None


# ============================= УТИЛИТЫ =============================

def detect_encoding(path: str) -> str:
    with open(path, "rb") as f:
        return chardet.detect(f.read(20000)).get("encoding", "utf-8")


def preprocess(text: str) -> str:
    text = str(text)
    text = text.replace(";", " ; ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ============================= ИЗВЛЕЧЕНИЕ "КЛЮЧ: ЗНАЧЕНИЕ" =============================

def extract_key_value_pairs(text: str) -> List[Tuple[str, str]]:
    """
    Извлекаем только полноценные "Ключ: Значение".
    """
    text = preprocess(text)

    pattern = r'([A-Za-zА-Яа-яёЁ0-9 ,\-()"«»]{2,80}?)\s*:\s*([^;,\n]+)'
    matches = re.findall(pattern, text)

    pairs: List[Tuple[str, str]] = []

    for key, value in matches:
        key = key.strip()
        value = value.strip()

        if not key or not value:
            continue

        key_low = key.lower()
        value_low = value.lower()

        if key_low in STOP_WORDS or value_low in STOP_WORDS:
            continue

        if len(value) > 200:
            continue

        pairs.append((key, value))

    return pairs


# ============================= НОРМАЛИЗАЦИЯ КЛЮЧЕЙ И ФИЛЬТРАЦИЯ =============================

def normalize_key(key: str) -> str:
    k = key.lower().strip()

    for raw, norm in NORMALIZATION_MAP.items():
        if raw in k:
            return norm

    return key.strip().capitalize()


def is_generic_pair(norm_key: str, value: str) -> bool:
    vk = norm_key.lower()
    vv = value.lower().strip()

    if norm_key == "Вид" and vv in GENERIC_VID_VALUES:
        return True

    if any(tok in vv for tok in GENERIC_STD_TOKENS) or any(tok in vk for tok in GENERIC_STD_TOKENS):
        return True

    if vv in {"универсальный", "стандартный", "стандартный размер"}:
        return True

    return False


def normalize_characters(pairs: List[Tuple[str, str]]) -> List[str]:
    normalized: List[str] = []

    for key, value in pairs:
        norm_key = normalize_key(key)
        value = value.strip()

        if not value or value.lower() in STOP_WORDS:
            continue

        if is_generic_pair(norm_key, value):
            continue

        normalized.append(f"{norm_key}: {value}")

    return normalized


# ============================= ДЕДУПЛИКАЦИЯ =============================

def smart_dedupe(features: List[str], top_k: int) -> List[str]:
    if not features:
        return []

    counter = Counter(features)
    common = [feat for feat, _ in counter.most_common(top_k * 2)]

    if model is None or len(common) <= top_k:
        return common[:top_k]

    try:
        embeddings = model.encode(common, convert_to_tensor=True)
    except Exception as e:
        logger.warning(f"Ошибка эмбеддингов, откат к частотам: {e}")
        return common[:top_k]

    kept_indices: List[int] = []

    for i in range(len(common)):
        if len(kept_indices) >= top_k:
            break

        is_similar = False
        for j in kept_indices:
            sim = util.cos_sim(embeddings[i], embeddings[j]).item()
            if sim > SIMILARITY_THRESHOLD:
                is_similar = True
                break

        if not is_similar:
            kept_indices.append(i)

    return [common[i] for i in kept_indices]


# ============================= TF-IDF ПО ХАРАКТЕРИСТИКАМ =============================

def compute_significant_features(category_chars: Dict[str, List[str]]) -> Dict[str, List[str]]:
    logger.info("Вычисление значимых признаков (TF-IDF + глобальная фильтрация)…")

    cat_tf: Dict[str, Counter] = {cat: Counter(chars) for cat, chars in category_chars.items()}

    df = Counter()
    for counter in cat_tf.values():
        for feat in counter:
            df[feat] += 1

    N_cat = len(cat_tf)
    df_threshold = max(1, int(GLOBAL_DF_FRACTION * N_cat))
    logger.info(f"Глобальный DF-порог: {df_threshold} (из {N_cat} категорий)")

    result: Dict[str, List[str]] = {}

    for cat, counter in cat_tf.items():
        if sum(counter.values()) < MIN_SUPPORT:
            continue

        scored: List[Tuple[str, float]] = []

        for feat, cnt in counter.items():
            feat_df = df[feat]
            if feat_df > df_threshold:
                continue

            idf = math.log((1 + N_cat) / (1 + feat_df))
            score = cnt * idf
            scored.append((feat, score))

        if not scored:
            continue

        scored.sort(key=lambda x: x[1], reverse=True)
        top_feats = [f for f, _ in scored[:TOP_K * 3]]

        dedup = smart_dedupe(top_feats, top_k=TOP_K)
        result[cat] = dedup

    return result


# ============================= ПАЙПЛАЙН ПО КАТЕГОРИЯМ =============================

def load_data() -> pd.DataFrame:
    enc = detect_encoding(CSV_PATH)
    logger.info(f"Определённая кодировка: {enc}")

    df = pd.read_csv(CSV_PATH, dtype=str, low_memory=False, encoding=enc).fillna("")

    required = ["id_сте", "id_категории"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Отсутствуют обязательные колонки: {missing}")

    spec_cols = [c for c in df.columns if c.startswith("spec")]

    text_cols: List[str] = []
    for col in ["название_сте", "производитель", "страна_происхождения", "название_категории"]:
        if col in df.columns:
            text_cols.append(col)

    text_cols += spec_cols

    df["all_text"] = df[text_cols].apply(
        lambda row: " ; ".join(
            [str(x) for x in row if str(x) not in ("", "nan", "None")]
        ),
        axis=1,
    )

    df = df[df["all_text"].str.len() > 5]
    logger.info(f"Строк после фильтрации по тексту: {len(df)}")

    return df


def extract_by_categories(df: pd.DataFrame):
    """
    Возвращаем:
      - category_chars: cat_id -> [ "Key: Value", ... ]
      - category_counts: cat_id -> num_items_with_chars
      - category_names: cat_id -> название_категории
    """
    category_chars: Dict[str, List[str]] = defaultdict(list)
    category_counts: Dict[str, int] = defaultdict(int)

    for _, row in tqdm(df.iterrows(), total=len(df)):
        cat = str(row["id_категории"])
        text = row["all_text"]

        raw_pairs = extract_key_value_pairs(text)
        normalized = normalize_characters(raw_pairs)

        if normalized:
            category_chars[cat].extend(normalized)
            category_counts[cat] += 1

    category_names: Dict[str, str] = {}
    if "название_категории" in df.columns:
        grouped = df.groupby("id_категории")["название_категории"]
        for cat_id, series in grouped:
            name = ""
            for v in series:
                v = str(v).strip()
                if v and v not in ("nan", "None"):
                    name = v
                    break
            category_names[str(cat_id)] = name

    return category_chars, category_counts, category_names


# ============================= ПОСТРОЕНИЕ СХЕМЫ АТРИБУТОВ =============================

def split_char(char: str) -> Optional[Tuple[str, str]]:
    """
    "Key: Value" -> (Key, Value)
    """
    if ":" not in char:
        return None
    key, value = char.split(":", 1)
    return key.strip(), value.strip()


def parse_numeric_with_unit(value: str) -> Tuple[Optional[float], str]:
    """
    Пытаемся выделить число + юнит из строки.
    Примеры:
      "16.00000 дюйм" -> (16.0, "дюйм")
      "0.215 м" -> (0.215, "м")
    """
    v = value.strip()
    # Вытаскиваем первую "числовую группу" + остаток как потенциальную единицу
    m = re.match(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*(.*)$", v)
    if not m:
        return None, ""

    num_str = m.group(1).replace(",", ".")
    unit = m.group(2).strip()

    try:
        num = float(num_str)
        return num, unit
    except ValueError:
        return None, unit


def infer_attribute_type_and_stats(values: List[str]) -> Dict[str, any]:
    """
    По списку сырых значений атрибута определяем:
      - type
      - unit (если numeric)
      - min/max (если numeric)
      - top_values
    """
    cleaned_values = [str(v).strip() for v in values if str(v).strip()]
    if not cleaned_values:
        return {
            "type": "text",
            "unit": None,
            "min": None,
            "max": None,
            "top_values": [],
        }

    # Boolean?
    lower_vals = [v.lower() for v in cleaned_values]
    unique_lower = set(lower_vals)
    if unique_lower.issubset(BOOLEAN_VALUES_TRUE.union(BOOLEAN_VALUES_FALSE)):
        # boolean
        cnt = Counter(lower_vals)
        top_vals = [v for v, _ in cnt.most_common(2)]
        return {
            "type": "boolean",
            "unit": None,
            "min": None,
            "max": None,
            "top_values": top_vals,
        }

    # Numeric?
    numeric_values: List[float] = []
    units: List[str] = []
    for v in cleaned_values:
        num, unit = parse_numeric_with_unit(v)
        if num is not None:
            numeric_values.append(num)
            if unit:
                units.append(unit)

    numeric_ratio = len(numeric_values) / len(cleaned_values)

    if numeric_values and numeric_ratio >= 0.7:
        unit = None
        if units:
            unit = Counter(units).most_common(1)[0][0]

        cnt = Counter(cleaned_values)
        top_vals = [v for v, _ in cnt.most_common(10)]

        return {
            "type": "numeric",
            "unit": unit,
            "min": min(numeric_values),
            "max": max(numeric_values),
            "top_values": top_vals,
        }

    # Categorical vs text
    cnt = Counter(cleaned_values)
    unique_count = len(cnt)

    if unique_count <= 20 or len(cleaned_values) >= 5:
        # считаем категориальным
        top_vals = [v for v, _ in cnt.most_common(10)]
        return {
            "type": "categorical",
            "unit": None,
            "min": None,
            "max": None,
            "top_values": top_vals,
        }

    # Иначе текст
    top_vals = [v for v, _ in cnt.most_common(10)]
    return {
        "type": "text",
        "unit": None,
        "min": None,
        "max": None,
        "top_values": top_vals,
    }


def build_attribute_schema(
    significant: Dict[str, List[str]],
    category_chars: Dict[str, List[str]],
) -> Dict[str, List[Dict[str, any]]]:
    """
    Превращаем significant["cat_id"] = ["Key: Value", ...]
    и category_chars["cat_id"] = ["Key: Value", ...] в
    attributes["cat_id"] = [ { name, type, unit, top_values, min, max }, ... ]
    """
    attributes_by_cat: Dict[str, List[Dict[str, any]]] = {}

    for cat, feats in significant.items():
        if cat not in category_chars:
            continue

        # Собираем набор ключей, которые считаем важными для этой категории
        keys_to_keep = set()
        for char in feats:
            split = split_char(char)
            if not split:
                continue
            key, _ = split
            keys_to_keep.add(key)

        # Собираем значения по этим ключам из ВСЕХ характеристик категории
        key_values: Dict[str, List[str]] = defaultdict(list)
        for char in category_chars[cat]:
            split = split_char(char)
            if not split:
                continue
            key, value = split
            if key in keys_to_keep:
                key_values[key].append(value)

        # Строим атрибуты
        attrs_for_cat: List[Dict[str, any]] = []
        for key in sorted(key_values.keys()):
            values = key_values[key]
            if not values:
                continue

            stats = infer_attribute_type_and_stats(values)
            attr = {
                "name": key,
                "type": stats["type"],
                "unit": stats["unit"],
                "min": stats["min"],
                "max": stats["max"],
                "top_values": stats["top_values"],
            }
            attrs_for_cat.append(attr)

        attributes_by_cat[cat] = attrs_for_cat

    return attributes_by_cat


# ============================= СОХРАНЕНИЕ ОНТОЛОГИИ =============================

def save_ontology(
    significant: Dict[str, List[str]],
    attributes: Dict[str, List[Dict[str, any]]],
    counts: Dict[str, int],
    category_names: Dict[str, str],
    total_rows: int,
):
    Path(OUTPUT_DIR).mkdir(exist_ok=True)

    out = {
        "meta": {
            "total_rows": total_rows,
            "categories": len(significant),
            "min_support": MIN_SUPPORT,
            "top_k": TOP_K,
            "model": MODEL_NAME,
            "global_df_fraction": GLOBAL_DF_FRACTION,
        },
        "categories": {},
    }

    for cat, chars in significant.items():
        out["categories"][cat] = {
            "category_name": category_names.get(cat, ""),
            "characteristics": chars,                    # плоский список "Key: Value"
            "attributes": attributes.get(cat, []),       # структурированная схема
            "total_items": counts.get(cat, 0),
        }

    json_path = Path(OUTPUT_DIR) / "universal_characteristics_ontology_v5.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    logger.info(f"Онтология V5 сохранена в {json_path}")

    # CSV для быстрого просмотра атрибутов
    csv_rows = []
    for cat, data in out["categories"].items():
        cat_name = data.get("category_name", "")
        total_items = data.get("total_items", 0)
        for attr in data.get("attributes", []):
            csv_rows.append(
                {
                    "category_id": cat,
                    "category_name": cat_name,
                    "attribute_name": attr["name"],
                    "type": attr["type"],
                    "unit": attr["unit"],
                    "min": attr["min"],
                    "max": attr["max"],
                    "top_values": ", ".join(map(str, attr["top_values"])),
                    "total_items": total_items,
                }
            )

    csv_path = Path(OUTPUT_DIR) / "universal_attributes_schema_v5.csv"
    pd.DataFrame(csv_rows).to_csv(csv_path, index=False, encoding="utf-8")
    logger.info(f"CSV V5 со схемой атрибутов сохранён в {csv_path}")


# ============================= MAIN =============================

def main():
    logger.info("Старт universal_characteristics_extractor_v5")

    df = load_data()
    category_chars, category_counts, category_names = extract_by_categories(df)

    significant = compute_significant_features(category_chars)

    attributes = build_attribute_schema(significant, category_chars)

    save_ontology(significant, attributes, category_counts, category_names, len(df))

    logger.info("Онтология V5 построена.")


if __name__ == "__main__":
    main()
