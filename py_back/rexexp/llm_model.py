# universal_characteristics_extractor_v4.py
# Улучшенная версия: агрессивная чистка мусорных характеристик + TF-IDF + эмбеддинги
# + сохранение названия категории в онтологию
# + runtime-модель, принимающая категорию и поля товара и выдающая характеристики

import re
import json
import math
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Union
from collections import Counter, defaultdict

import pandas as pd
import chardet
import torch
from tqdm import tqdm
from sentence_transformers import SentenceTransformer, util

# ============================= CONFIG =============================

CSV_PATH = "py_back/rexexp/data/result_itr4.csv"
OUTPUT_DIR = "result"

MIN_SUPPORT = 5           # минимум товаров с характеристиками в категории
TOP_K = 15               # целевое число характеристик на категорию
SIMILARITY_THRESHOLD = 0.85
GLOBAL_DF_FRACTION = 0.4  # если признак встречается > 40% категорий — выкидываем как неинформативный

MODEL_NAME = "ai-forever/sbert_large_mt_nlu_ru"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("universal_characteristics_v4.log", encoding="utf-8"),
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
    "вид шин": "Тип шины",
    "вид шин пневматические": "Тип шины",
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

# generic "Вид: ..." значения, которые почти никогда не полезны
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

# слишком общие значения стандартов / норм / ТР ТС
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
    # упростим разделители, чтобы паттерн "ключ: значение" находился стабильнее
    text = text.replace(";", " ; ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ============================= ИЗВЛЕЧЕНИЕ "КЛЮЧ: ЗНАЧЕНИЕ" =============================

def extract_key_value_pairs(text: str) -> List[Tuple[str, str]]:
    """
    Извлекаем только полноценные "Ключ: Значение" (без обрезаний и мусора).
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

    # жадно ищем по словарю
    for raw, norm in NORMALIZATION_MAP.items():
        if raw in k:
            return norm

    # по умолчанию: просто аккуратно капитализируем
    return key.strip().capitalize()


def is_generic_pair(norm_key: str, value: str) -> bool:
    """
    Явно выкидываем очевидные мусорные сочетания.
    """
    vk = norm_key.lower()
    vv = value.lower().strip()

    # "Вид: Товары" / "Вид: Одежда" / "Вид: Транспортные средства" и т.п.
    if norm_key == "Вид" and vv in GENERIC_VID_VALUES:
        return True

    # "Стандарты: ТР ТС 019/2011", "Гост: ..." и т.п.
    if any(tok in vv for tok in GENERIC_STD_TOKENS) or any(tok in vk for tok in GENERIC_STD_TOKENS):
        return True

    # Совсем пустые / слишком общие значения
    if vv in {"универсальный", "стандартный", "стандартный размер"}:
        return True

    return False


def normalize_characters(pairs: List[Tuple[str, str]]) -> List[str]:
    """
    Пары (key, value) → нормализованные "NormKey: Value" + фильтрация мусора.
    """
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
    """
    Дедупликация через частотность + эмбеддинги.
    """
    if not features:
        return []

    counter = Counter(features)
    common = [feat for feat, _ in counter.most_common(top_k * 2)]

    if model is None or len(common) <= top_k:
        # нет модели / мало признаков — просто берем по частоте
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
    """
    TF-IDF-подобный скоринг по признакам "NormKey: Value" с обрезкой
    суперчастых (df > GLOBAL_DF_FRACTION*N_cat) + дедупликация.
    """
    logger.info("Вычисление значимых признаков (TF-IDF + глобальная фильтрация)…")

    # TF по категориям
    cat_tf: Dict[str, Counter] = {cat: Counter(chars) for cat, chars in category_chars.items()}

    # DF: в скольких категориях встречается каждый признак
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

            # отсекаем слишком частые признаки ("Вид: Одежда", "Стандарты: ТР ТС" и т.п.)
            if feat_df > df_threshold:
                continue

            # TF-IDF
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
    Для каждой категории собираем список нормализованных "NormKey: Value".
    Возвращаем:
      - category_chars: cat_id -> [chars]
      - category_counts: cat_id -> num_items_with_chars
      - category_names: cat_id -> название_категории (первое непустое)
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

    # мапа id_категории -> название_категории (первое непустое значение)
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


# ============================= СОХРАНЕНИЕ ОНТОЛОГИИ =============================

def save_ontology(
    significant: Dict[str, List[str]],
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
            "characteristics": chars,
            "total_items": counts.get(cat, 0),
        }

    json_path = Path(OUTPUT_DIR) / "llm_model.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    logger.info(f"Онтология V4 сохранена в {json_path}")

    # CSV-шорткат для быстрого просмотра
    csv_rows = []
    for cat, data in out["categories"].items():
        for ch in data["characteristics"]:
            csv_rows.append(
                {
                    "category_id": cat,
                    "category_name": data.get("category_name", ""),
                    "characteristic": ch,
                    "total_items": data["total_items"],
                }
            )

    csv_path = Path(OUTPUT_DIR) / "llm_model.csv"
    pd.DataFrame(csv_rows).to_csv(csv_path, index=False, encoding="utf-8")
    logger.info(f"CSV V4 для анализа сохранён в {csv_path}")


# ============================= RUNTIME-МОДЕЛЬ =============================

class CharacteristicsRuntimeModel:
    """
    Runtime-модель, которая:
      - загружает готовую онтологию V4
      - по категории и полям товара извлекает релевантные характеристики
    """

    def __init__(self, ontology_path: Union[str, Path]):
        ontology_path = Path(ontology_path)
        if not ontology_path.exists():
            raise FileNotFoundError(f"Онтология не найдена: {ontology_path}")

        with open(ontology_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # ожидаем структуру как в save_ontology()
        self.meta = data.get("meta", {})
        self.categories = data.get("categories", {})

        logger.info(
            f"Загружена онтология V4: {len(self.categories)} категорий, "
            f"файл = {ontology_path}"
        )

    def _build_text_from_item(self, item_fields: Dict[str, str]) -> str:
        """
        Собираем текст из полей товара:
          - название_сте
          - страна_происхождения
          - производитель
          - название_категории (если есть)
          - все spec*
        """
        parts: List[str] = []

        for col in ["название_сте", "страна_происхождения", "производитель", "название_категории"]:
            if col in item_fields and item_fields[col]:
                val = str(item_fields[col]).strip()
                if val and val not in ("nan", "None"):
                    parts.append(val)

        for key, val in item_fields.items():
            if key.startswith("spec") and val:
                v = str(val).strip()
                if v and v not in ("nan", "None"):
                    parts.append(v)

        return " ; ".join(parts)

    def extract_for_item(self, category_id: str, item_fields: Dict[str, str]) -> List[str]:
        """
        Главный метод:

        Вход:
          - category_id (строка)
          - item_fields: словарь с полями товара (название_сте, страна_происхождения, производитель, spec1..specN)

        Выход:
          - список нормализованных характеристик, отфильтрованных под категорию
        """
        cat_id = str(category_id)
        if cat_id not in self.categories:
            # Категории нет в онтологии — просто делаем "сырой" парсинг без фильтра
            logger.warning(
                f"Категория {cat_id} отсутствует в онтологии, вернём сырой набор характеристик."
            )
            text = self._build_text_from_item(item_fields)
            pairs = extract_key_value_pairs(text)
            normalized = normalize_characters(pairs)
            return smart_dedupe(normalized, top_k=TOP_K)

        # 1. Получаем список "значимых" характеристик для категории из онтологии
        cat_info = self.categories[cat_id]
        cat_chars: List[str] = cat_info.get("characteristics", [])

        important_keys = {
            ch.split(":", 1)[0].strip()
            for ch in cat_chars
            if ":" in ch
        }

        # 2. Собираем текст по товару и извлекаем характеристики
        text = self._build_text_from_item(item_fields)
        pairs = extract_key_value_pairs(text)
        normalized = normalize_characters(pairs)  # "NormKey: Value"

        # 3. Фильтруем только по "важным" ключам для этой категории
        filtered: List[str] = []
        for ch in normalized:
            if ":" not in ch:
                continue
            key, _ = ch.split(":", 1)
            key = key.strip()
            if key in important_keys:
                filtered.append(ch)

        # если после фильтрации пусто — вернём хотя бы нормализованный набор
        if not filtered:
            logger.info(
                f"Для категории {cat_id} после фильтрации по онтологии пусто, "
                f"вернём нормализованный набор без фильтра."
            )
            return smart_dedupe(normalized, top_k=TOP_K)

        # 4. Дедупликация
        return smart_dedupe(filtered, top_k=TOP_K)


def load_runtime_model(
    ontology_path: Union[str, Path] = Path(OUTPUT_DIR) / "universal_characteristics_ontology_v4.json",
) -> CharacteristicsRuntimeModel:
    """
    Утилита для удобной инициализации runtime-модели.
    """
    return CharacteristicsRuntimeModel(ontology_path)


# ============================= MAIN =============================

def main():
    logger.info("🚀 Старт universal_characteristics_extractor_v4")

    df = load_data()
    category_chars, category_counts, category_names = extract_by_categories(df)

    significant = compute_significant_features(category_chars)

    save_ontology(significant, category_counts, category_names, len(df))

    logger.info("✅ Онтология V4 построена.")


if __name__ == "__main__":
    main()
