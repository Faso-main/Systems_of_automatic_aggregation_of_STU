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
        logging.FileHandler("ontology_processing.log", encoding='utf-8'),
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

# ============================= ОПРЕДЕЛЕНИЕ ПАТТЕРНОВ =============================
FEATURE_PATTERNS = [
    r'(диаметр\s*(?:внешний|внутренний)?)[\s:]+([0-9.,\s]+ ?[мк]?м)',
    r'(длина(?:\s+(?:кабеля|шнура|люверса|антенны)?)?)[\s:]+([0-9.,]+ ?[мсм]?м?)',
    r'(мощность(?:\s+(?:rms|звука)?)?)[\s:]+([0-9.,]+ ?[вкм]?вт)',
    r'(объ[её]м|ёмкость|объем)[\s:]+([0-9.,]+ ?[лмлг]+)',
    r'(память|озу|оперативная)[\s:]+([0-9]+ ?[гт]б)',
    r'(диагональ|экран)[\s:]+([0-9.,]+ ?["″′″ дюйм"]+)',
    r'(разрешение)[\s:]+([0-9x]+)',
    r'(процессор|cpu)[\s:]+([a-zA-Z0-9\-+ ]{4,})',
    r'(матрица|тип\s+матрицы)[\s:]+([a-zA-Z0-9\*\+\/]+)',
    r'(цвет|корпус|отделка)[\s:]+([^;\n"{},]{3,40})',
    r'(материал)[\s:]+([^;\n"{},]{3,50})',
    r'(страна\s+(?:производства|происхождения)?)[\s:]+([А-Яа-яЁё]+)',
    r'(частота\s+(?:дискретизации|обновления)?)[\s:]+([0-9.,\-]+ ?[гк]?гц)',
    r'(чувствительность)[\s:]+([0-9\-]+ ?дб)',
    r'(импеданс|сопротивление)[\s:]+([0-9]+ ?[омк]?)',
    r'(вес)[\s:]+([0-9.,]+ ?[кгг]+)',
    r'(количество\s+(?:в\s+упаковке|шт\.?|штук))[\s:]+([0-9]+)',
    r'(тип\s+(?:микрофона|направленности))[\s:]+([а-яА-ЯёЁ\w\s\-]+)',
    r'(дискретизация)[\s:]+([0-9.,\s]+ ?кгц)',
    r'(направленность)[\s:]+([а-яА-ЯёЁ\w\s\-]+)',
    r'(выходы)[\s:]+([a-zA-Z0-9\s\-,]+)',
    r'(поддержка\s+форматов)[\s:]+([a-zA-Z0-9\s\-,]+)',
]

# Фильтр для исключения нерелевантных категорий
EXCLUDED_CATEGORIES = {"услуга", "окпд", "фз-", "поставк", "ремонт", "расходн", "принадлеж", "канцеляр", "моющ", "дезинф"}

# ============================= ОСНОВНЫЕ ФУНКЦИИ =============================

def remove_similar_features(features):
    """
    Удаляет семантически похожие характеристики для уменьшения дублирования
    """
    if len(features) <= TOP_K:
        return features
        
    try:
        embeddings = model.encode(features, convert_to_tensor=True)
        kept_features = []
        processed_indices = set()
        
        for i, feature in enumerate(features):
            if i in processed_indices:
                continue
                
            kept_features.append(feature)
            if len(kept_features) >= TOP_K:
                break
                
            for j in range(i + 1, len(features)):
                if j in processed_indices:
                    continue
                    
                similarity = util.cos_sim(embeddings[i], embeddings[j])
                if similarity > SIMILARITY_THRESHOLD:
                    processed_indices.add(j)
                    
        return kept_features
    except Exception as e:
        logger.warning(f"Ошибка при удалении похожих характеристик: {e}")
        return features[:TOP_K]

def extract_characteristics(text):
    """
    Извлекает технические характеристики из текста с использованием regex-паттернов
    """
    if not text or len(str(text)) < 30:
        return []
        
    processed_text = " " + str(text).lower().replace(";", " ").replace('"', ' ') + " "
    characteristics = []
    
    for pattern in FEATURE_PATTERNS:
        matches = re.findall(pattern, processed_text, flags=re.IGNORECASE)
        for match in matches:
            key = match[0].strip()
            value = match[1].strip()
            value = re.sub(r'[.;\'\n\r\n].*', '', value).strip()
            
            if value and len(value) < 70:
                # Нормализация ключей
                key = key.replace("диаметр внешний", "внешний диаметр")
                key = key.replace("страна производства", "страна")
                key = key.replace("страна происхождения", "страна")
                
                characteristics.append(f"{key.capitalize()}: {value}")
                
    return characteristics

def load_and_prepare_data():
    """
    Загружает и предварительно обрабатывает данные из CSV файла
    """
    logger.info("Начало загрузки данных из CSV")
    
    try:
        dataframe = pd.read_csv(CSV_PATH, dtype=str, low_memory=False, engine="c").fillna("")
    except Exception:
        logger.warning("C-движок недоступен, используется python-движок")
        dataframe = pd.read_csv(CSV_PATH, dtype=str, low_memory=False, engine="python", on_bad_lines="skip").fillna("")

    dataframe = dataframe[['id2', 'specification']].copy()
    dataframe['id2'] = dataframe['id2'].astype(str).str.strip()
    dataframe['specification'] = dataframe['specification'].astype(str)

    # Фильтрация нерелевантных категорий
    filter_pattern = "|".join(EXCLUDED_CATEGORIES)
    dataframe = dataframe[~dataframe['id2'].str.contains(filter_pattern, case=False, na=False)]
    dataframe = dataframe[dataframe['specification'].str.len() > 30]

    logger.info(f"Данные успешно загружены: {len(dataframe):,} строк")
    return dataframe

def process_categories(dataframe):
    """
    Обрабатывает категории товаров и извлекает характеристики
    """
    logger.info("Начало обработки категорий")
    
    category_characteristics = defaultdict(list)
    category_counts = defaultdict(int)
    
    for index, row in dataframe.iterrows():
        if index % 30000 == 0:
            logger.info(f"Обработано {index:,} строк")
            
        characteristics = extract_characteristics(row['specification'])
        if characteristics:
            category_characteristics[row['id2']].extend(characteristics)
            category_counts[row['id2']] += 1
            
    return category_characteristics, category_counts

def generate_final_ontology(category_characteristics, category_counts):
    """
    Генерирует финальную онтологию с фильтрацией и дедупликацией
    """
    logger.info("Формирование финальной онтологии")
    
    ontology = {}
    for category, characteristics in category_characteristics.items():
        if category_counts[category] < MIN_SUPPORT:
            continue
            
        frequency_counter = Counter(characteristics)
        top_characteristics = [char for char, count in frequency_counter.most_common(60) if count >= 2]
        unique_characteristics = remove_similar_features(top_characteristics)
        
        if len(unique_characteristics) >= 5:
            ontology[category] = unique_characteristics[:TOP_K]
            
    logger.info(f"Сформировано {len(ontology)} категорий в онтологии")
    return ontology

def save_results(ontology, processed_rows_count):
    """
    Сохраняет результаты в JSON файл
    """
    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(exist_ok=True)
    
    result_file = output_path / "28_11_bert12.json"
    
    result_data = {
        "metadata": {
            "source_file": CSV_PATH,
            "processed_rows": processed_rows_count,
            "total_categories": len(ontology),
            "min_support_threshold": MIN_SUPPORT,
            "max_characteristics_per_category": TOP_K
        },
        "categories": dict(sorted(ontology.items()))
    }
    
    with open(result_file, "w", encoding="utf-8") as file:
        json.dump(result_data, file, ensure_ascii=False, indent=2)
        
    logger.info(f"Результаты сохранены в файл: {result_file}")

# ============================= ОСНОВНАЯ ЛОГИКА =============================

def main():
    """
    Основная функция обработки данных и построения онтологии
    """
    try:
        # Загрузка и подготовка данных
        data = load_and_prepare_data()
        
        # Обработка категорий и извлечение характеристик
        characteristics, counts = process_categories(data)
        
        # Генерация финальной онтологии
        final_ontology = generate_final_ontology(characteristics, counts)
        
        # Сохранение результатов
        save_results(final_ontology, len(data))
        
        # Логирование примеров результатов
        logger.info("Примеры обработанных категорий:")
        sample_categories = ["Телевизоры", "Микрофоны музыкальные", "Наушники", "Люверсы для дыроколов", "Кофемашины"]
        for category in sample_categories:
            if category in final_ontology:
                logger.info(f"Категория '{category}': {len(final_ontology[category])} характеристик")
                
    except Exception as e:
        logger.error(f"Критическая ошибка в процессе обработки: {e}")
        raise

if __name__ == "__main__":
    main()