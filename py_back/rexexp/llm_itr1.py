# 28_11_bert12_final_enhanced.py
# Финальная версия: чистая онтология + сбор id СТЕ + экспорт в CSV для агрегации СТЕ
# Готова к интеграции в веб (Flask) для ТЗ хакатона

import re
import json
import logging
from collections import Counter, defaultdict
from sentence_transformers import SentenceTransformer, util
import pandas as pd
from pathlib import Path
import torch
import chardet

try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x: x

# ============================= КОНФИГУРАЦИЯ =============================
CSV_PATH = "py_back/rexexp/data/exploded_characteristics.csv"  # Обнови путь
OUTPUT_DIR = "result"
MIN_SUPPORT = 8
TOP_K = 12
SIMILARITY_THRESHOLD = 0.90
MODEL_NAME = "ai-forever/sbert_large_mt_nlu_ru"

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

# ============================= ПАТТЕРНЫ ДЛЯ ШИН =============================
FEATURE_PATTERNS = [
    # Размеры шин
    r'(диаметр\s*(?:посадочный|внешний)?)[\s:]+([0-9.,\s]+ ?[дюйм"″]*)',
    r'(ширина\s*(?:профиля|колеса)?)[\s:]+([0-9.,]+ ?[ммсм]*)',
    r'(высота\s*(?:профиля|колеса)?)[\s:]+([0-9.,]+ ?[%ммсм]*)',
    r'(радиус)[\s:]+([0-9.,]+ ?[дюйм]*)',
    
    # Индексы
    r'(индекс\s*(?:нагрузки|скорости))[\s:]+([0-9A-Z/]+)',
    r'(индекс\s*(?:нагрузки/скорости))[\s:]+([0-9A-Z/]+)',
    
    # Типоразмеры
    r'(типоразмер|размерность)[\s:]+([0-9./Rr\- ]+)',
    r'(размер\s*(?:шины|колеса)?)[\s:]+([0-9./Rr\- ]+)',
    
    # Конструкция
    r'(тип\s*(?:конструкции|шины)?)[\s:]+([радиальная|диагональная|бескамерная|камерная]+)',
    r'(конструкция)[\s:]+([радиальная|диагональная]+)',
    r'(способ\s*герметизации)[\s:]+([бескамерные|камерные]+)',
    
    # Сезонность
    r'(сезонность|категория\s*использования)[\s:]+([летняя|зимняя|всесезонная|всесезон]+)',
    
    # Шипы
    r'(шипы|наличие\s*шипов)[\s:]+([да|нет|1|0]+)',
    
    # Протектор
    r'(рисунок\s*протектора|протектор)[\s:]+([^;\n]{3,50})',
    r'(тип\s*рисунка)[\s:]+([^;\n]{3,50})',
    
    # Слойность
    r'(слойность|норма\s*слойности|pr)[\s:]+([0-9]+)',
    
    # Назначение
    r'(назначение|применение)[\s:]+([^;\n]{5,80})',
    r'(применяемость\s*оси)[\s:]+([^;\n]{3,50})',
    
    # Вес
    r'(вес)[\s:]+([0-9.,]+ ?[кг]+)',
    
    # Бренд/модель (уже есть в данных)
    r'(бренд)[\s:]+([^;\n]{2,30})',
    r'(модель\s*(?:шины)?)[\s:]+([^;\n]{2,50})'
]

# ============================= ОПРЕДЕЛЕНИЕ КОДИРОВКИ =============================
def detect_encoding(file_path):
    """Определяет кодировку файла"""
    with open(file_path, 'rb') as f:
        raw_data = f.read(10000)  # Читаем первые 10KB для определения
        result = chardet.detect(raw_data)
        encoding = result.get('encoding', 'utf-8')
        confidence = result.get('confidence', 0)
        logger.info(f"Определена кодировка: {encoding} (уверенность: {confidence:.2f})")
        return encoding

# ============================= ЗАГРУЗКА ДАННЫХ =============================
def load_and_prepare_data():
    logger.info("Загрузка CSV...")
    
    # Определяем кодировку
    encoding = detect_encoding(CSV_PATH)
    
    try:
        # Пробуем загрузить с определенной кодировкой
        df = pd.read_csv(
            CSV_PATH, 
            dtype=str, 
            low_memory=False, 
            encoding=encoding
        ).fillna("")
        logger.info(f"Успешно загружено с кодировкой: {encoding}")
        
    except UnicodeDecodeError:
        logger.warning(f"Ошибка с кодировкой {encoding}, пробуем windows-1251")
        try:
            df = pd.read_csv(
                CSV_PATH, 
                dtype=str, 
                low_memory=False, 
                encoding='windows-1251'
            ).fillna("")
            logger.info("Успешно загружено с кодировкой: windows-1251")
        except UnicodeDecodeError:
            logger.warning("Ошибка с windows-1251, пробуем latin-1")
            df = pd.read_csv(
                CSV_PATH, 
                dtype=str, 
                low_memory=False, 
                encoding='latin-1'
            ).fillna("")
            logger.info("Успешно загружено с кодировкой: latin-1")
    
    except Exception as e:
        logger.error(f"Ошибка загрузки CSV: {e}")
        # Последняя попытка с обработкой ошибок
        df = pd.read_csv(
            CSV_PATH, 
            dtype=str, 
            low_memory=False, 
            encoding='utf-8',
            on_bad_lines='skip',
            quoting=0
        ).fillna("")
        logger.info("Загружено с обработкой ошибок")

    # Проверяем наличие необходимых колонок
    required_columns = ['id_сте', 'id_категории', 'название_категории']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        logger.error(f"Отсутствуют колонки: {missing_columns}")
        logger.info(f"Доступные колонки: {list(df.columns)}")
        raise ValueError(f"Отсутствуют необходимые колонки: {missing_columns}")

    # Используем правильные колонки
    spec_cols = [col for col in df.columns if col.startswith('spec')]
    logger.info(f"Найдено колонок с характеристиками: {len(spec_cols)}")
    
    df = df[['id_сте', 'id_категории', 'название_категории'] + spec_cols].copy()
    
    df['id_сте'] = df['id_сте'].astype(str).str.strip()
    df['id_категории'] = df['id_категории'].astype(str).str.strip()
    
    # Объединяем все spec колонки в один текст
    df['all_specs'] = df[spec_cols].apply(
        lambda row: ' ; '.join([str(x) for x in row if str(x) not in ['nan', '', 'None']]), 
        axis=1
    )

    # Фильтруем пустые характеристики
    initial_count = len(df)
    df = df[df['all_specs'].str.len() > 10]
    filtered_count = len(df)
    
    logger.info(f"Загружено строк: {initial_count:,}")
    logger.info(f"После фильтрации пустых характеристик: {filtered_count:,}")
    logger.info(f"Уникальных категорий: {df['id_категории'].nunique()}")
    
    return df

# ============================= ИЗВЛЕЧЕНИЕ ХАРАКТЕРИСТИК =============================
def extract_characteristics(text):
    if not text or len(str(text)) < 10:
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

            # Очистка значения
            value = re.sub(r'[.;\'\n\r\t].*', '', value)
            value = re.sub(r'\s+', ' ', value).strip()
            value = re.sub(r'\/+', '/', value)

            if not value or len(value) < 2 or len(value) > 80:
                continue

            # Нормализация ключей
            key = key.replace("индекс нагрузки", "индекс_нагрузки")
            key = key.replace("индекс скорости", "индекс_скорости")
            key = key.replace("высота профиля", "высота_профиля")
            key = key.replace("ширина профиля", "ширина_профиля")
            key = key.replace("посадочный диаметр", "диаметр")
            key = key.replace("рисунок протектора", "протектор")

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

# ============================= ОБРАБОТКА КАТЕГОРИЙ =============================
def process_categories(dataframe):
    logger.info("Извлечение характеристик...")
    category_chars = defaultdict(list)
    category_item_ids = defaultdict(list)
    category_counts = defaultdict(int)

    for _, row in tqdm(dataframe.iterrows(), total=len(dataframe)):
        category_id = row['id_категории']
        item_id = row['id_сте']
        specs_text = row['all_specs']
        
        chars = extract_characteristics(specs_text)
        if chars:
            category_chars[category_id].extend(chars)
            category_item_ids[category_id].append(item_id)
            category_counts[category_id] += 1

    return category_chars, category_item_ids, category_counts

# ============================= ГЕНЕРАЦИЯ ОНТОЛОГИИ =============================
def generate_final_ontology(category_chars, category_item_ids, category_counts):
    logger.info("Формирование онтологии...")
    ontology = {}
    category_metadata = {}

    for category, chars in tqdm(category_chars.items()):
        if category_counts[category] < MIN_SUPPORT:
            continue

        counter = Counter(chars)
        candidates = []
        
        for char, count in counter.most_common(100):
            if count < 2:
                break
            if any(bad in char.lower() for bad in ["0 ", "1 ", "null", "нет ", "да "]):
                continue
            if len(char) > 90:
                continue
            candidates.append(char)

        unique_chars = remove_similar_features(candidates)
        
        if len(unique_chars) >= 4:
            category_metadata[category] = {
                "total_items": category_counts[category],
                "item_ids": list(set(category_item_ids[category])),
                "characteristics_count": len(unique_chars)
            }
            
            ontology[category] = unique_chars[:TOP_K]

    logger.info(f"Готово! Категорий: {len(ontology)}")
    return ontology, category_metadata

# ============================= СОХРАНЕНИЕ РЕЗУЛЬТАТОВ =============================
def save_results(ontology, metadata, rows_processed):
    Path(OUTPUT_DIR).mkdir(exist_ok=True)
    
    # Сохраняем полный JSON с метаданными
    json_file = Path(OUTPUT_DIR) / "tires_ontology_with_ids.json"

    data = {
        "metadata": {
            "source_file": CSV_PATH,
            "processed_rows": rows_processed,
            "total_categories": len(ontology),
            "min_support_threshold": MIN_SUPPORT,
            "max_characteristics_per_category": TOP_K,
            "model": MODEL_NAME,
            "note": "Финал: характеристики шин + id СТЕ для агрегации"
        },
        "categories": {}
    }

    for category_id, chars in ontology.items():
        data["categories"][category_id] = {
            "characteristics": chars,
            "metadata": metadata[category_id]
        }

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"JSON с id СТЕ сохранён: {json_file}")

    # Экспорт в CSV для анализа
    csv_data = []
    for cat_id, cat_data in data["categories"].items():
        for char in cat_data["characteristics"]:
            csv_data.append({
                "category_id": cat_id,
                "characteristic": char,
                "total_items": cat_data["metadata"]["total_items"],
                "sample_item_ids": ", ".join(cat_data["metadata"]["item_ids"][:5])
            })

    pd.DataFrame(csv_data).to_csv(
        Path(OUTPUT_DIR) / "tires_ontology_for_aggregation.csv", 
        index=False, 
        encoding="utf-8"
    )
    logger.info("CSV для агрегации готов")

# ============================= MAIN =============================
def main():
    try:
        data = load_and_prepare_data()
        chars, item_ids, counts = process_categories(data)
        ontology, metadata = generate_final_ontology(chars, item_ids, counts)
        save_results(ontology, metadata, len(data))
        
        total_items_covered = sum([meta["total_items"] for meta in metadata.values()])
        logger.info(f"Обработано товаров: {total_items_covered:,}")
        logger.info("Финал! Готово для интеграции в систему агрегации СТЕ!")
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise

if __name__ == "__main__":
    main()