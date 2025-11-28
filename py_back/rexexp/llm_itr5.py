# universal_characteristics_extractor_v2.py

import re
import json
import math
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import chardet
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer, util
from tqdm import tqdm

# ============================= КОНФИГУРАЦИЯ =============================
CSV_PATH = "py_back/rexexp/data/result_itr4.csv"
OUTPUT_DIR = "result"

MIN_SUPPORT = 5           # минимальное число товаров с характеристиками в категории
TOP_K = 15               # макс. число характеристик на категорию
SIMILARITY_THRESHOLD = 0.85
MODEL_NAME = "ai-forever/sbert_large_mt_nlu_ru"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("universal_characteristics_v2.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ============================= УНИВЕРСАЛЬНЫЕ ПАТТЕРНЫ =============================
UNIVERSAL_PATTERNS = [
    # Размеры и измерения
    r"(размер|диаметр|ширина|высота|глубина|толщина|длина)[\s:]*([0-9.,]+\s*(?:мм|см|м|дюйм|″|\"|см³|м²|л|кг|г|мг)?)",
    r"([0-9.,]+\s*(?:мм|см|м|дюйм|″|\"|×|x|\*))\s*(?:размер|диаметр|ширина|высота)?",

    # Вес и объем
    r"(вес|масса|объем|ёмкость)[\s:]*([0-9.,]+\s*(?:кг|г|мг|л|мл|см³|м³))",
    r"([0-9.,]+\s*(?:кг|г|мг|л|мл))\s*(?:вес|масса|объем)?",

    # Цвета
    r"(цвет|окрас)[\s:]*([а-яё\s-]{3,20})",
    r"\b(черный|чёрный|белый|красный|синий|зеленый|зелёный|желтый|жёлтый|оранжевый|фиолетовый|розовый|коричневый|серый|голубой|серебристый|золотой|бежевый)\b",

    # Материалы
    r"(материал|изготовлен|сделан)[\s:]*([а-яё\s-]{3,30})",
    r"\b(дерево|металл|сталь|алюминий|пластик|стекло|керамика|текстиль|хлопок|шерсть|кожа|резина|полимер|пвх|силикон)\b",

    # Бренды и производители
    r"\b([A-Z][a-zA-Z0-9&\.\-]{2,20})\b",
    r"(бренд|производитель|марка|brand|maker)[\s:]*([^;\n]{2,30})",

    # Технические характеристики
    r"(мощность|напряжение|ток|частота)[\s:]*([0-9.,]+\s*(?:Вт|кВт|В|А|Гц|кГц|МГц))",
    r"([0-9.,]+\s*(?:Вт|кВт|В|А|Гц))\s*(?:мощность|напряжение)?",

    # Страны и происхождение
    r"\b(россия|рф|китай|германия|сша|япония|корея|франция|италия|испания|турция|индия|тайвань|вьетнам)\b",
    r"(страна|происхождение|made in|страна производства)[\s:]*([^;\n]{3,20})",

    # Упаковка и количество
    r"(упаковка|комплект|количество|в комплекте)[\s:]*([0-9]+\s*(?:шт|уп|пак|набор)?)",
    r"([0-9]+\s*(?:шт|уп|пак|набор))\s*(?:в комплекте)?",

    # Гарантия и сроки
    r"(гарантия|срок службы|срок годности)[\s:]*([0-9]+\s*(?:мес|месяц|месяцев|год|года|лет))",

    # Общие свойства
    r"(тип|вид|категория|назначение)[\s:]*([^;\n]{3,40})",
    r"(модель|артикул|код)[\s:]*([a-zA-Z0-9\-_]{2,40})",

    # Булевы характеристики
    r"\b(да|нет|есть|имеется|наличие|поддержка)\b[\s:]*([^;\n]{2,30})",

    # Цифровые значения с единицами
    r"([0-9.,]+\s*(?:°C|°F|об/мин|ккал|кДж|бар|атм|Па|кПа|МПа))",

    # Специфичные для электроники (про запас)
    r"(процессор|память|оперативная память|hdd|ssd|дисплей|экран)[\s:]*([^;\n]{3,40})",

    # Для одежды/обуви (про запас)
    r"(размер)[\s:]*([0-9xl\s\-]+)",
]

STOP_WORDS = {
    "null",
    "нет",
    "да",
    "не указано",
    "не указан",
    "отсутствует",
    "пусто",
    "empty",
    "none",
    "nan",
    "undefined",
    "0",
    "1",
}

# ============================= МОДЕЛЬ ЭМБЕДДИНГОВ =============================
try:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(MODEL_NAME, device=device)
    logger.info(f"Модель {MODEL_NAME} загружена на {device}")
except Exception as e:
    logger.error(f"Ошибка при загрузке модели эмбеддингов: {e}")
    model = None


# ============================= LLM-НОРМАЛИЗАТОР (ЗАГОТОВКА) =============================
class LLMNormalizer:
    """
    Заготовка под нормализацию характеристик через LLM.

    Идея:
    - На вход: сырая строка "Номинальное посадочное ...: 16.50000 дюйм"
    - На выход:
        norm_key  -> "Диаметр посадочный"
        norm_value -> '16.5"'
        type -> "numeric"/"categorical"/"boolean"/...

    В данном файле реализуем чисто интерфейс и простой фолбэк
    (LLM можно подключить отдельно, не ломая основной пайплайн).
    """

    def __init__(self):
        # Здесь можно подгрузить кэш нормализаций из файла
        self.cache: Dict[str, Dict[str, str]] = {}

    def normalize(self, raw_char: str) -> Tuple[str, str]:
        """
        Нормализует характеристику формата "Ключ: Значение" в (norm_key, norm_value).
        Пока что используем простую эвристику.
        """
        if raw_char in self.cache:
            data = self.cache[raw_char]
            return data["norm_key"], data["norm_value"]

        # Простейший парсинг "ключ: значение"
        if ":" in raw_char:
            key_part, value_part = raw_char.split(":", 1)
            key = key_part.strip()
            value = value_part.strip()
        else:
            key = "Характеристика"
            value = raw_char.strip()

        # Эвристическая нормализация ключа
        key_low = key.lower()

        replacements = [
            (["номинальное отношение высоты профиля шины к ее ширине"], "Отношение высоты к ширине"),
            (["номинальная ширина профиля", "обозначение номинальной ширины профиля"], "Ширина профиля"),
            (["номинальный посадочный диаметр обода", "диаметр посадочный"], "Диаметр посадочный"),
            (["категория использования шины"], "Категория использования"),
            (["наличие шипов", "шипы"], "Наличие шипов"),
            (["индекс нагрузки"], "Индекс нагрузки"),
            (["индекс категории скорости", "индекс скорости"], "Индекс скорости"),
        ]

        norm_key = key
        for keys, repl in replacements:
            if any(k in key_low for k in keys):
                norm_key = repl
                break

        # Упрощённая нормализация значения
        value = value.replace("  ", " ").strip()

        self.cache[raw_char] = {
            "norm_key": norm_key,
            "norm_value": value,
        }
        return norm_key, value


llm_normalizer = LLMNormalizer()


# ============================= УМНЫЙ ПАРСЕР ХАРАКТЕРИСТИК =============================
class UniversalCharacteristicsExtractor:
    def __init__(self):
        self.compiled_patterns = [re.compile(p, re.IGNORECASE) for p in UNIVERSAL_PATTERNS]

    def extract_from_text(self, text: str) -> List[str]:
        """
        Извлекает сырые характеристики из произвольного текста.
        Возвращает список строк формата "Ключ: Значение".
        """
        if not text or len(str(text)) < 5:
            return []

        text = self.preprocess_text(str(text))
        characteristics = []

        for pattern in self.compiled_patterns:
            matches = pattern.findall(text)
            for match in matches:
                if isinstance(match, tuple):
                    if len(match) >= 2:
                        key, value = match[0].strip(), match[1].strip()
                    else:
                        # Одинарный матч, без явного ключа
                        key, value = "", str(match[0]).strip() if match else ("", "")
                else:
                    key, value = "", str(match).strip()

                char = self.clean_characteristic(key, value)
                if char and self.is_valid_characteristic(char):
                    characteristics.append(char)

        return list(set(characteristics))

    @staticmethod
    def preprocess_text(text: str) -> str:
        # Заменяем разделители на пробелы
        text = re.sub(r"[;,\|/]", " ", text)
        # Убираем лишние пробелы
        text = re.sub(r"\s+", " ", text)
        # Добавляем пробелы вокруг двоеточий
        text = re.sub(r":", " : ", text)
        return text.lower().strip()

    def clean_characteristic(self, key: str, value: str) -> str:
        if not value or len(value) < 2 or len(value) > 80:
            return ""

        # Фильтрация стоп-слов
        if any(stop_word in value.lower() for stop_word in STOP_WORDS):
            return ""

        if not key:
            key = "характеристика"
        else:
            key = key.replace("_", " ").strip()
            if len(key) > 60:
                key = key[:60]
            # Чуть-чуть нормализуем регистр
            key = key.capitalize()

        # Очистка значения
        value = re.sub(r"[^\w\s\d.,°\-/]", "", value, flags=re.UNICODE)
        value = re.sub(r"\s+", " ", value).strip()

        if not value:
            return ""

        return f"{key}: {value}"

    @staticmethod
    def is_valid_characteristic(char: str) -> bool:
        if len(char) < 5 or len(char) > 120:
            return False

        invalid_patterns = [
            r"^[0-9\s\.\,]+$",  # только цифры
            r"http",            # URL
            r"@",               # Email
        ]
        return not any(re.search(p, char, re.IGNORECASE) for p in invalid_patterns)


# ============================= ЗАГРУЗКА ДАННЫХ =============================
def detect_encoding(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return chardet.detect(f.read(10000)).get("encoding", "utf-8")


def load_data() -> pd.DataFrame:
    logger.info("Загрузка данных...")

    encoding = detect_encoding(CSV_PATH)
    logger.info(f"Определена кодировка: {encoding}")

    try:
        df = pd.read_csv(CSV_PATH, dtype=str, low_memory=False, encoding=encoding).fillna("")
    except UnicodeDecodeError:
        for enc in ["windows-1251", "cp1251", "latin-1"]:
            try:
                df = pd.read_csv(CSV_PATH, dtype=str, low_memory=False, encoding=enc).fillna("")
                logger.info(f"Загружено с кодировкой: {enc}")
                break
            except Exception:
                continue
        else:
            df = pd.read_csv(
                CSV_PATH,
                dtype=str,
                low_memory=False,
                encoding="utf-8",
                on_bad_lines="skip",
            ).fillna("")

    required_cols = ["id_сте", "id_категории"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        logger.error(f"Отсутствуют колонки: {missing_cols}")
        raise ValueError(f"Отсутствуют колонки: {missing_cols}")

    # Колонки спецификаций
    spec_cols = [col for col in df.columns if col.startswith("spec")]

    # Явно требуемые поля по ТЗ
    base_text_cols = []
    for col in ["название_сте", "страна_происхождения", "производитель", "название_категории"]:
        if col in df.columns:
            base_text_cols.append(col)

    text_cols = base_text_cols + spec_cols

    # Дополнительно все колонки, содержащие "страна"
    for col in df.columns:
        if "страна" in col.lower() and col not in text_cols:
            text_cols.append(col)

    logger.info(f"Колонки для анализа: {text_cols}")

    df["all_text_data"] = df[text_cols].apply(
        lambda row: " ; ".join(
            [str(x) for x in row if str(x) not in ["nan", "", "None"]]
        ),
        axis=1,
    )

    initial_count = len(df)
    df = df[df["all_text_data"].str.len() > 10]

    logger.info(f"Загружено строк всего: {initial_count:,}")
    logger.info(f"После фильтрации по тексту: {len(df):,}")
    logger.info(f"Уникальных категорий: {df['id_категории'].nunique()}")

    return df


# ============================= ОБРАБОТКА КАТЕГОРИЙ =============================
def process_categories_with_universal_extractor(
    dataframe: pd.DataFrame,
) -> Tuple[Dict[str, List[str]], Dict[str, List[str]], Dict[str, int]]:
    logger.info("Универсальное извлечение характеристик по категориям...")

    extractor = UniversalCharacteristicsExtractor()
    category_chars: Dict[str, List[str]] = defaultdict(list)
    category_item_ids: Dict[str, List[str]] = defaultdict(list)
    category_counts: Dict[str, int] = defaultdict(int)

    for _, row in tqdm(dataframe.iterrows(), total=len(dataframe)):
        category_id = str(row["id_категории"])
        item_id = str(row["id_сте"])
        text_data = row["all_text_data"]

        chars = extractor.extract_from_text(text_data)

        if chars:
            category_chars[category_id].extend(chars)
            category_item_ids[category_id].append(item_id)
            category_counts[category_id] += 1

    logger.info("Извлечение характеристик завершено.")
    return category_chars, category_item_ids, category_counts


# ============================= УМНАЯ ДЕДУПЛИКАЦИЯ =============================
def smart_deduplicate_features(features: List[str], top_k: int = TOP_K) -> List[str]:
    """
    Дедупликация характеристик с использованием частот и эмбеддингов.
    """
    if not features:
        return []

    if len(features) <= top_k:
        return list(dict.fromkeys(features))  # уникальные, сохранив порядок

    # Частотная фильтрация
    counter = Counter(features)
    common_features = [feat for feat, _ in counter.most_common(top_k * 2)]

    if len(common_features) <= top_k:
        return common_features

    if model is None:
        # Если нет модели эмбеддингов, просто берём по частоте
        return [feat for feat, _ in counter.most_common(top_k)]

    try:
        embeddings = model.encode(common_features, convert_to_tensor=True)
        kept_indices: List[int] = []

        for i in range(len(common_features)):
            if len(kept_indices) >= top_k:
                break

            is_similar = False
            for kept_idx in kept_indices:
                sim = util.cos_sim(embeddings[i], embeddings[kept_idx]).item()
                if sim > SIMILARITY_THRESHOLD:
                    is_similar = True
                    break

            if not is_similar:
                kept_indices.append(i)

        return [common_features[i] for i in kept_indices[:top_k]]

    except Exception as e:
        logger.warning(f"Ошибка дедупликации через эмбеддинги: {e}")
        return [feat for feat, _ in Counter(features).most_common(top_k)]


# ============================= TF-IDF-ПОДОБНАЯ ЗНАЧИМОСТЬ =============================
def compute_significant_features(
    category_chars: Dict[str, List[str]],
    top_k: int = TOP_K,
    min_support: int = MIN_SUPPORT,
) -> Dict[str, List[str]]:
    """
    Для каждой категории считает значимость характеристик по TF-IDF-подобной схеме.

    score(cat, feat) = TF(cat, feat) * log((1 + N_cat) / (1 + DF(feat)))
    """
    logger.info("Подсчёт значимых характеристик (TF-IDF-подобный скоринг)...")

    # Считаем TF по категориям
    cat_counters: Dict[str, Counter] = {
        cat: Counter(chars) for cat, chars in category_chars.items()
    }

    # DF по признаку: в скольких категориях встретился
    feat_df: Counter = Counter()
    for cat, counter in cat_counters.items():
        for feat in counter.keys():
            feat_df[feat] += 1

    N_cat = len(cat_counters)
    result: Dict[str, List[str]] = {}

    for cat, counter in cat_counters.items():
        total_feats = sum(counter.values())
        if total_feats < min_support:
            continue

        scored_feats: List[Tuple[str, float]] = []
        for feat, cnt in counter.items():
            df_val = feat_df[feat]
            idf = math.log((1 + N_cat) / (1 + df_val))
            score = cnt * idf
            scored_feats.append((feat, score))

        scored_feats.sort(key=lambda x: x[1], reverse=True)
        top_feats = [f for f, _ in scored_feats[: top_k * 2]]

        # Нормализация через LLM + дедупликация
        normalized_feats = []
        for char in top_feats:
            norm_key, norm_value = llm_normalizer.normalize(char)
            normalized_feats.append(f"{norm_key}: {norm_value}")

        dedup_feats = smart_deduplicate_features(normalized_feats, top_k=top_k)
        result[cat] = dedup_feats

    logger.info(
        f"Подсчитаны значимые характеристики для {len(result)} категорий (из {N_cat})"
    )
    return result


# ============================= ГЕНЕРАЦИЯ ОНТОЛОГИИ =============================
def generate_universal_ontology(
    significant_chars: Dict[str, List[str]],
    category_item_ids: Dict[str, List[str]],
    category_counts: Dict[str, int],
) -> Tuple[Dict[str, List[str]], Dict[str, Dict[str, Any]]]:
    logger.info("Генерация универсальной онтологии характеристик...")

    ontology: Dict[str, List[str]] = {}
    category_metadata: Dict[str, Dict[str, Any]] = {}

    for category, chars in tqdm(significant_chars.items()):
        if category_counts.get(category, 0) < MIN_SUPPORT:
            continue

        if len(chars) < 3:
            continue

        unique_chars = smart_deduplicate_features(chars, top_k=TOP_K)

        if len(unique_chars) >= 3:
            items = list(set(category_item_ids.get(category, [])))
            category_metadata[category] = {
                "total_items": category_counts.get(category, 0),
                "item_ids": items,
                "characteristics_count": len(unique_chars),
                "sample_characteristics": unique_chars[:5],
            }
            ontology[category] = unique_chars

    logger.info(f"Сгенерировано категорий с онтологией: {len(ontology)}")
    return ontology, category_metadata


# ============================= СОХРАНЕНИЕ РЕЗУЛЬТАТОВ =============================
def save_universal_results(
    ontology: Dict[str, List[str]],
    metadata: Dict[str, Dict[str, Any]],
    total_rows: int,
) -> Dict[str, Any]:
    Path(OUTPUT_DIR).mkdir(exist_ok=True)

    output_data: Dict[str, Any] = {
        "metadata": {
            "source_file": CSV_PATH,
            "processed_rows": total_rows,
            "total_categories": len(ontology),
            "min_support_threshold": MIN_SUPPORT,
            "max_characteristics_per_category": TOP_K,
            "model": MODEL_NAME,
            "note": "Универсальная онтология значимых характеристик для всех категорий товаров",
        },
        "categories": {},
    }

    for cat_id, chars in ontology.items():
        output_data["categories"][cat_id] = {
            "characteristics": chars,
            "metadata": metadata[cat_id],
        }

    json_path = Path(OUTPUT_DIR) / "universal_characteristics_ontology_v2.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Универсальная онтология сохранена: {json_path}")

    # Дополнительный CSV для быстрого анализа в табличке
    csv_data = []
    for cat_id, cat_data in output_data["categories"].items():
        for char in cat_data["characteristics"]:
            csv_data.append(
                {
                    "category_id": cat_id,
                    "characteristic": char,
                    "total_items": cat_data["metadata"]["total_items"],
                    "sample_item_ids": ", ".join(
                        cat_data["metadata"]["item_ids"][:3]
                    ),
                }
            )

    csv_path = Path(OUTPUT_DIR) / "universal_characteristics_for_analysis_v2.csv"
    pd.DataFrame(csv_data).to_csv(csv_path, index=False, encoding="utf-8")
    logger.info(f"CSV для анализа сохранён: {csv_path}")

    return output_data


# ============================= АНАЛИЗ РЕЗУЛЬТАТОВ =============================
def analyze_results(ontology: Dict[str, List[str]]) -> None:
    logger.info("Анализ качества извлечённых характеристик...")

    if not ontology:
        logger.warning("Онтология пуста, анализ пропущен.")
        return

    total_chars = sum(len(chars) for chars in ontology.values())
    avg_chars_per_cat = total_chars / len(ontology)

    char_types = Counter()
    for chars in ontology.values():
        for char in chars:
            low = char.lower()
            if any(word in low for word in ["размер", "ширина", "высота", "диаметр"]):
                char_types["размеры"] += 1
            elif "цвет" in low:
                char_types["цвета"] += 1
            elif "материал" in low:
                char_types["материалы"] += 1
            elif any(word in low for word in ["бренд", "производитель", "марка"]):
                char_types["бренды"] += 1
            elif any(unit in char for unit in ["кг", "г", "л", "мл"]):
                char_types["вес_объем"] += 1
            elif any(unit in char for unit in ["мм", "см", "дюйм"]):
                char_types["размеры"] += 1
            else:
                char_types["прочие"] += 1

    logger.info("=== СТАТИСТИКА ИЗВЛЕЧЕНИЯ ===")
    logger.info(f"Всего категорий в онтологии: {len(ontology)}")
    logger.info(f"Всего характеристик: {total_chars}")
    logger.info(f"Среднее характеристик на категорию: {avg_chars_per_cat:.1f}")
    logger.info("Распределение по типам:")
    for t, cnt in char_types.most_common():
        logger.info(f"  {t}: {cnt}")


# ============================= MAIN =============================
def main():
    try:
        logger.info("🚀 ЗАПУСК УНИВЕРСАЛЬНОГО ИЗВЛЕЧЕНИЯ ХАРАКТЕРИСТИК V2")

        # 1. Загрузка данных
        data = load_data()

        # 2. Извлечение сырых характеристик по товарам и категориям
        category_chars, category_item_ids, category_counts = (
            process_categories_with_universal_extractor(data)
        )

        # 3. Подсчёт значимых характеристик (TF-IDF + LLM-нормализация + эмбеддинги)
        significant_chars = compute_significant_features(
            category_chars, top_k=TOP_K, min_support=MIN_SUPPORT
        )

        # 4. Генерация онтологии на основе значимых характеристик
        ontology, metadata = generate_universal_ontology(
            significant_chars, category_item_ids, category_counts
        )

        # 5. Сохранение результатов
        save_universal_results(ontology, metadata, len(data))

        # 6. Анализ результатов
        analyze_results(ontology)

        logger.info("✅ УНИВЕРСАЛЬНАЯ ОНТОЛОГИЯ ХАРАКТЕРИСТИК ГОТОВА!")

    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        raise


if __name__ == "__main__":
    main()
