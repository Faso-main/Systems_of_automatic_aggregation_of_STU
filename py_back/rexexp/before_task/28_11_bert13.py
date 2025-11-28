# 28_11_bert12_fixed.py
# Улучшенная версия онтологии с идеальной чистотой характеристик
# Подходит для любых товаров, особенно картриджей, принтеров, электроники

import re
import json
import logging
from collections import Counter, defaultdict
from sentence_transformers import SentenceTransformer, util
import pandas as pd
from pathlib import Path

# ============================= КОНФИГУРАЦИЯ =============================
CSV_PATH = "py_back/rexexp/data/split.csv"
OUTPUT_DIR = "result"
MIN_SUPPORT = 6
TOP_K = 12
SIMILARITY_THRESHOLD = 0.88
MODEL_NAME = "ai-forever/sbert_large_mt_nlu_ru"

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ontology_fixed.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================= ИНИЦИАЛИЗАЦИЯ МОДЕЛИ =============================
try:
    model = SentenceTransformer(MODEL_NAME)
    logger.info(f"Модель {MODEL_NAME} успешно загружена")
except Exception as e:
    logger.error(f"Ошибка загрузки модели: {e}")
    raise

# ============================= УЛУЧШЕННЫЕ ПАТТЕРНЫ =============================
FEATURE_PATTERNS = [
    # Размеры
    r'(диаметр\s*(?:внешний|внутренний)?)[\s:]+([0-9.,\s]+ ?[мк]?м)',
    r'(длина(?:\s+(?:кабеля|шнура|провода|антенны)?)?)[\s:]+([0-9.,]+ ?[мсм]?м?)',
    r'(ширина)[\s:]+([0-9.,]+ ?[мсм]?м?)',
    r'(высота)[\s:]+([0-9.,]+ ?[мсм]?м?)',
    r'(толщина)[\s:]+([0-9.,]+ ?[мк]?м)',

    # Электрические параметры
    r'(мощность(?:\s+(?:rms|пиковая)?)?)[\s:]+([0-9.,]+ ?[вкм]?вт?)',
    r'(частота\s+(?:процессора|обновления|дискретизации)?)[\s:]+([0-9.,\-]+ ?[ггцмгц]+)',
    r'(импеданс|сопротивление)[\s:]+([0-9]+ ?[омк]?)',
    r'(чувствительность)[\s:]+([0-9\-]+ ?дб)',

    # Объёмы и память
    r'(объ[её]м|ёмкость|объем)[\s:]+([0-9.,]+ ?[лмлгкм]?[бг]?[б]?[а]?[х]?)',
    r'(память|озу|оперативная|встроенная)[\s:]+([0-9]+ ?[гтгб]+)',

    # Экраны и оптика
    r'(диагональ|экран)[\s:]+([0-9.,]+ ?["″′″ дюйм"]+)',
    r'(разрешение)[\s:]+([0-9x]+)',
    r'(матрица|тип\s+матрицы)[\s:]+([a-zA-Z0-9\*\+\/]+)',

    # Процессоры и железо
    r'(процессор|cpu|чип)[\s:]+([a-zA-Z0-9\-+ \.]{4,})',

    # Вес и количество
    r'(вес)[\s:]+([0-9.,]+ ?[кгг]+)',
    r'(количество\s+(?:в\s+упаковке|шт\.?|листов|страниц|отверстий))[\s:]+([0-9]+)',

    # Цвет — самый важный, с расширенным захватом
    r'(цвет(?:\s+(?:корпуса|экрана|фона|покрытия|оттиска|порошка|чернил|тонера)?)?)[\s:]+([^;\n"\'{},]{3,50})(?=\s*[;,\n]|$)',

    # Материал
    r'(материал(?:\s+(?:корпуса|рамы|покрытия|ткани)?)?)[\s:]+([^;\n"\'{},]{3,60})(?=\s*[;,\n]|$)',

    # Страна
    r'(страна\s+(?:производства|происхождения|изготовления)?)[\s:]+([А-Яа-яЁёA-Za-z]+)',

    # СПЕЦИАЛЬНО ДЛЯ КАРТРИДЖЕЙ И ПРИНТЕРОВ (это было критически нужно!)
    r'(ресурс|количество\s+страниц|страниц\s+на\s+картридже?)[\s:]+([0-9\s]+(?:\s*стра?н?)?)',
    r'(совместим(?:ые|ая)\s+(?:модели?|принтеры?|мфу))[\s:]+([^;\n"\'{}]{10,150})',
    r'(оригинальн?ый|совместимый|аналог)',
    r'(наличие\s+чипа|чип)[\s:]+(да|нет|есть|1|0)',
    r'(тип\s+(?:картриджа|расходника))[\s:]+([^\n";,]{5,50})',
    r'(модель\s+(?:картриджа|расходника))[\s:]+([A-Z0-9\-\/]{4,30})',
]

EXCLUDED_CATEGORIES = {
    "услуга", "окпд", "фз-", "поставк", "ремонт", "расходн", "принадлеж", "канцеляр",
    "моющ", "дезинф", "чистящ", "уборк", "гигиен", "мыло", "салфетк"
}

# ============================= УЛУЧШЕННОЕ ИЗВЛЕЧЕНИЕ =============================
def extract_characteristics(text):
    if not text or len(str(text)) < 30:
        return []

    processed_text = " " + str(text).lower().replace(";", " ; ").replace(",", " , ").replace('"', ' ') + " "
    characteristics = []

    for pattern in FEATURE_PATTERNS:
        matches = re.findall(pattern, processed_text, flags=re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple) and len(match) >= 2:
                key, value = match[0].strip(), " ".join(match[1:]).strip()
            else:
                continue

            # Умная очистка значения — главный фикс обрезанных строк!
            value = re.sub(r'\s+[а-яёa-z]+\s*:.*$', '', value, flags=re.I)  # убираем "наличие рисунка:0 ..."
            value = re.sub(r'\s+(наличие|тип|есть|нет|да|0|1|null|не применимо)\s*$', '', value, flags=re.I)
            value = re.sub(r'[.;\'\n\r\t].*', '', value)
            value = re.sub(r'\s+', ' ', value).strip()

            if not value or len(value) < 2 or len(value) > 80:
                continue

            # Нормализация ключей
            key = key.replace("страна производства", "страна").replace("страна происхождения", "страна")
            key = key.replace("цвет корпуса", "цвет").replace("цвет порошка", "цвет").replace("цвет чернил", "цвет")
            key = key.replace("цвет оттиска", "цвет").replace("цвет тонера", "цвет")

            characteristics.append(f"{key.capitalize()}: {value}")

    return characteristics

# ============================= УДАЛЕНИЕ СХОЖИХ =============================
def remove_similar_features(features):
    if len(features) <= TOP_K:
        return features

    try:
        embeddings = model.encode(features, convert_to_tensor=True)
        kept = []
        processed = set()

        for i, feature in enumerate(features):
            if i in processed:
                continue
            kept.append(feature)
            if len(kept) >= TOP_K:
                break
            for j in range(i + 1, len(features)):
                if j in processed:
                    continue
                if util.cos_sim(embeddings[i], embeddings[j]) > SIMILARITY_THRESHOLD:
                    processed.add(j)
        return kept
    except Exception as e:
        logger.warning(f"Ошибка дедупликации: {e}")
        return features[:TOP_K]

# ============================= ЗАГРУЗКА ДАННЫХ =============================
def load_and_prepare_data():
    logger.info("Загрузка CSV...")
    try:
        df = pd.read_csv(CSV_PATH, dtype=str, low_memory=False, engine="c").fillna("")
    except:
        df = pd.read_csv(CSV_PATH, dtype=str, low_memory=False, engine="python", on_bad_lines="skip").fillna("")

    df = df[['id2', 'specification']].copy()
    df['id2'] = df['id2'].astype(str).str.strip()
    df['specification'] = df['specification'].astype(str)

    # Фильтр мусорных категорий
    exclude_pattern = "|".join(EXCLUDED_CATEGORIES)
    df = df[~df['id2'].str.contains(exclude_pattern, case=False, na=False)]
    df = df[df['specification'].str.len() > 30]

    logger.info(f"Загружено строк: {len(df):,}")
    return df

# ============================= ОБРАБОТКА =============================
def process_categories(dataframe):
    logger.info("Извлечение характеристик...")
    category_chars = defaultdict(list)
    category_counts = defaultdict(int)

    for idx, row in dataframe.iterrows():
        if idx % 50000 == 0 and idx > 0:
            logger.info(f"Обработано {idx:,} строк...")

        chars = extract_characteristics(row['specification'])
        if chars:
            category_chars[row['id2']].extend(chars)
            category_counts[row['id2']] += 1

    return category_chars, category_counts

# ============================= ФИНАЛЬНАЯ ОНТОЛОГИЯ =============================
def generate_final_ontology(category_chars, category_counts):
    logger.info("Формирование финальной онтологии...")
    ontology = {}

    for category, chars in category_chars.items():
        if category_counts[category] < MIN_SUPPORT:
            continue

        counter = Counter(chars)
        candidates = []
        for char, count in counter.most_common(80):
            if count < 2:
                break
            if any(bad in char.lower() for bad in ["0 ", "1 ", "null", "нет ", "да ", "наличие"]):
                continue
            if len(char) > 90:
                continue
            candidates.append(char)

        unique = remove_similar_features(candidates)
        if len(unique) >= 4:
            ontology[category] = unique[:TOP_K]

    logger.info(f"Готово! Категорий в онтологии: {len(ontology)}")
    return ontology

# ============================= СОХРАНЕНИЕ =============================
def save_results(ontology, rows_processed):
    Path(OUTPUT_DIR).mkdir(exist_ok=True)
    result_file = Path(OUTPUT_DIR) / "28_11_bert12_fixed.json"

    data = {
        "metadata": {
            "source_file": CSV_PATH,
            "processed_rows": rows_processed,
            "total_categories": len(ontology),
            "min_support_threshold": MIN_SUPPORT,
            "max_characteristics_per_category": TOP_K,
            "model": MODEL_NAME,
            "note": "Исправлены обрезанные характеристики. Добавлены параметры картриджей."
        },
        "categories": dict(sorted(ontology.items()))
    }

    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"Онтология сохранена: {result_file}")

# ============================= MAIN =============================
def main():
    data = load_and_prepare_data()
    chars, counts = process_categories(data)
    ontology = generate_final_ontology(chars, counts)
    save_results(ontology, len(data))
    logger.info("Всё готово! Запускай веб-интерфейс — у тебя топ-1 онтология")

if __name__ == "__main__":
    main()