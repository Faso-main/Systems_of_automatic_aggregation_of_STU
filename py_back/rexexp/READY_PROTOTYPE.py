# 28_11_bert12_final.py
# Финальная версия: чистая онтология + экспорт в CSV для агрегации СТЕ
# Готова к интеграции в веб (Flask) для ТЗ хакатона

import re
import json
import logging
from collections import Counter, defaultdict
from sentence_transformers import SentenceTransformer, util
import pandas as pd
from pathlib import Path
import torch  # Для фикса device

# Прогресс-бар (если tqdm доступен, иначе пропуск)
try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x: x

# ============================= КОНФИГУРАЦИЯ =============================
CSV_PATH = "py_back/rexexp/data/split.csv"
OUTPUT_DIR = "result"
MIN_SUPPORT = 8  # Увеличил до 8 для надёжности (меньше шума)
TOP_K = 12
SIMILARITY_THRESHOLD = 0.90  # Чуть поднял для жёсткой дедупликации
MODEL_NAME = "ai-forever/sbert_large_mt_nlu_ru"

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ontology_final.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================= ИНИЦИАЛИЗАЦИЯ МОДЕЛИ =============================
try:
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = SentenceTransformer(MODEL_NAME, device=device)
    logger.info(f"Модель {MODEL_NAME} загружена на {device}")
except Exception as e:
    logger.error(f"Ошибка модели: {e}")
    raise

# ============================= ПАТТЕРНЫ (финальные, с нормализацией) =============================
FEATURE_PATTERNS = [
    # Размеры (расширил захват)
    r'(диаметр\s*(?:внешний|внутренний)?)[\s:]+([0-9.,\s]+ ?[мк]?м)',
    r'(длина(?:\s+(?:кабеля|шнура|провода|антенны|люверса)?)?)[\s:]+([0-9.,]+ ?[мсм]?м?)',
    r'(ширина)[\s:]+([0-9.,]+ ?[мсм]?м?)',
    r'(высота)[\s:]+([0-9.,]+ ?[мсм]?м?)',
    r'(толщина)[\s:]+([0-9.,]+ ?[мк]?м)',

    # Электрика
    r'(мощность(?:\s+(?:rms|пиковая|звука)?)?)[\s:]+([0-9.,]+ ?[вкм]?вт?)',
    r'(частота\s+(?:процессора|обновления|дискретизации|экрана)?)[\s:]+([0-9.,\-]+ ?[ггцмгц]+)',
    r'(импеданс|сопротивление)[\s:]+([0-9]+ ?[омк]?)',
    r'(чувствительность)[\s:]+([0-9\-]+ ?дб)',

    # Объёмы/память
    r'(объ[её]м|ёмкость|объем)[\s:]+([0-9.,]+ ?[лмлгкм]?[бг]?[б]?[а]?[х]?)',
    r'(память|озу|оперативная|встроенная)[\s:]+([0-9]+ ?[гтгб]+)',

    # Экраны
    r'(диагональ|экран)[\s:]+([0-9.,]+ ?["″′″ дюйм"]+)',
    r'(разрешение)[\s:]+([0-9x]+)',
    r'(матрица|тип\s+матрицы)[\s:]+([a-zA-Z0-9\*\+\/]+)',

    # Процессоры
    r'(процессор|cpu|чип)[\s:]+([a-zA-Z0-9\-+ \.]{4,})',

    # Вес/количество
    r'(вес)[\s:]+([0-9.,]+ ?[кгг]+)',
    r'(количество\s+(?:в\s+упаковке|шт\.?|листов|страниц|отверстий))[\s:]+([0-9]+)',

    # Цвет (с нормализацией / и дубликатов)
    r'(цвет(?:\s+(?:корпуса|экрана|фона|покрытия|оттиска|порошка|чернил|тонера|ленты|шрифта)?)?)[\s:]+([^;\n"\'{},]{3,50})(?=\s*[;,\n]|$)',

    # Материал
    r'(материал(?:\s+(?:корпуса|рамы|покрытия|ткани|ленты|бейджа|картриджа|проводника|стенда|рамки|отделений|карманов|вставки|задника|багета)?)?)[\s:]+([^;\n"\'{},]{3,60})(?=\s*[;,\n]|$)',

    # Страна
    r'(страна\s+(?:производства|происхождения|изготовления)?)[\s:]+([А-Яа-яЁёA-Za-z]+)',

    # Картриджи/принтеры (финальные, с ресурсом в страницах)
    r'(ресурс|количество\s+страниц|страниц\s+на\s+картридже?|минимальный\s+ресурс)[\s:]+([0-9\s]+(?:\s*стра?н?)?)',
    r'(совместим(?:ые|ая)\s+(?:модели?|принтеры?|мфу))[\s:]+([^;\n"\'{}]{10,150})',
    r'(оригинальн?ый|совместимый|аналог)',
    r'(наличие\s+чипа|чип)[\s:]+(да|нет|есть|1|0)',
    r'(тип\s+(?:картриджа|расходника|расходного|материала|печати))[\s:]+([^\n";,]{5,50})',
    r'(модель\s+(?:картриджа|расходника|комплектующего|аппарата))[\s:]+([A-Z0-9\-\/]{4,30})',
]

EXCLUDED_CATEGORIES = {
    "услуга", "окпд", "фз-", "поставк", "ремонт", "расходн", "принадлеж", "канцеляр",
    "моющ", "дезинф", "чистящ", "уборк", "гигиен", "мыло", "салфетк"
}

# ============================= ИЗВЛЕЧЕНИЕ (финальная версия) =============================
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

            # Финальная очистка
            value = re.sub(r'\s+[а-яёa-z]+\s*:.*$', '', value, flags=re.I)
            value = re.sub(r'\s+(наличие|тип|есть|нет|да|0|1|null|не применимо|отсутствует)\s*$', '', value, flags=re.I)
            value = re.sub(r'[.;\'\n\r\t].*', '', value)
            value = re.sub(r'\s+', ' ', value).strip()
            value = re.sub(r'\/+', '/', value)  # Нормализация слэшей

            if not value or len(value) < 2 or len(value) > 80:
                continue

            # Нормализация ключей (финал)
            key = key.replace("страна производства", "страна").replace("страна происхождения", "страна")
            key = key.replace("цвет корпуса", "цвет").replace("цвет порошка", "цвет").replace("цвет чернил", "цвет")
            key = key.replace("цвет оттиска", "цвет").replace("цвет тонера", "цвет").replace("цвет ленты", "цвет")
            key = key.replace("цвет шрифта", "цвет")

            characteristics.append(f"{key.capitalize()}: {value}")

    return characteristics

# ============================= ДЕДУПЛИКАЦИЯ =============================
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

# ============================= ЗАГРУЗКА =============================
def load_and_prepare_data():
    logger.info("Загрузка CSV...")
    try:
        df = pd.read_csv(CSV_PATH, dtype=str, low_memory=False, engine="c").fillna("")
    except:
        df = pd.read_csv(CSV_PATH, dtype=str, low_memory=False, engine="python", on_bad_lines="skip").fillna("")

    df = df[['id2', 'specification']].copy()
    df['id2'] = df['id2'].astype(str).str.strip()
    df['specification'] = df['specification'].astype(str)

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

    for _, row in tqdm(dataframe.iterrows(), total=len(dataframe)):
        chars = extract_characteristics(row['specification'])
        if chars:
            category_chars[row['id2']].extend(chars)
            category_counts[row['id2']] += 1

    return category_chars, category_counts

# ============================= ОНТОЛОГИЯ =============================
def generate_final_ontology(category_chars, category_counts):
    logger.info("Формирование онтологии...")
    ontology = {}

    for category, chars in tqdm(category_chars.items()):
        if category_counts[category] < MIN_SUPPORT:
            continue

        counter = Counter(chars)
        candidates = []
        for char, count in counter.most_common(100):  # Увеличил до 100 для большего пула
            if count < 2:
                break
            if any(bad in char.lower() for bad in ["0 ", "1 ", "null", "нет ", "да ", "наличие", "отсутствует"]):
                continue
            if len(char) > 90:
                continue
            candidates.append(char)

        unique = remove_similar_features(candidates)
        if len(unique) >= 4:
            ontology[category] = unique[:TOP_K]

    logger.info(f"Готово! Категорий: {len(ontology)}")
    return ontology

# ============================= СОХРАНЕНИЕ + CSV ЭКСПОРТ =============================
def save_results(ontology, rows_processed):
    Path(OUTPUT_DIR).mkdir(exist_ok=True)
    json_file = Path(OUTPUT_DIR) / "28_11_bert14.json"

    data = {
        "metadata": {
            "source_file": CSV_PATH,
            "processed_rows": rows_processed,
            "total_categories": len(ontology),
            "min_support_threshold": MIN_SUPPORT,
            "max_characteristics_per_category": TOP_K,
            "model": MODEL_NAME,
            "note": "Финал: нормализация, прогресс-бар, экспорт CSV для UI/агрегации СТЕ."
        },
        "categories": dict(sorted(ontology.items()))
    }

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"JSON сохранён: {json_file}")

    # Экспорт в CSV для хакатона (агрегация СТЕ по ТЗ)
    csv_data = []
    for cat, chars in ontology.items():
        for char in chars:
            csv_data.append({"category": cat, "characteristic": char})

    pd.DataFrame(csv_data).to_csv(Path(OUTPUT_DIR) / "ontology_final.csv", index=False, encoding="utf-8")
    logger.info("CSV экспорт готов: result/ontology_final.csv (для веб/UI)")

# ============================= MAIN =============================
def main():
    data = load_and_prepare_data()
    chars, counts = process_categories(data)
    ontology = generate_final_ontology(chars, counts)
    save_results(ontology, len(data))
    logger.info("Финал! Интегрируй в Flask для поиска/агрегации по ТЗ. Удачи на хакатоне!")

if __name__ == "__main__":
    main()