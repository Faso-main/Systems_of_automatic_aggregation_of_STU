# universal_characteristics_extractor.py
import re
import json
import logging
import pandas as pd
import torch
from collections import Counter, defaultdict
from sentence_transformers import SentenceTransformer, util
from pathlib import Path
import chardet
from typing import List, Dict, Any
from tqdm import tqdm


# ============================= КОНФИГУРАЦИЯ =============================
CSV_PATH = "py_back/rexexp/data/result_itr4.csv"
OUTPUT_DIR = "result"
MIN_SUPPORT = 5  # Уменьшил для большего покрытия
TOP_K = 15
SIMILARITY_THRESHOLD = 0.85  # Более гибкая дедупликация
MODEL_NAME = "ai-forever/sbert_large_mt_nlu_ru"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("universal_characteristics.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================= УНИВЕРСАЛЬНЫЕ ПАТТЕРНЫ =============================
UNIVERSAL_PATTERNS = [
    # Размеры и измерения
    r'(размер|диаметр|ширина|высота|глубина|толщина|длина)[\s:]*([0-9.,]+[\\s]*(?:мм|см|м|дюйм|″|"|см³|м²|л|кг|г|мг)?)',
    r'([0-9.,]+\s*(?:мм|см|м|дюйм|″|"|×|x|\*))[\s]*(?:размер|диаметр|ширина|высота)?',
    
    # Вес и объем
    r'(вес|масса|объем|ёмкость)[\s:]*([0-9.,]+\s*(?:кг|г|мг|л|мл|см³|м³))',
    r'([0-9.,]+\s*(?:кг|г|мг|л|мл))[\s]*(?:вес|масса|объем)?',
    
    # Цвета
    r'(цвет|окрас)[\s:]*([а-яё\s-]{3,20})',
    r'\b(черный|белый|красный|синий|зеленый|желтый|оранжевый|фиолетовый|розовый|коричневый|серый|голубой|серебристый|золотой|бежевый)\b',
    
    # Материалы
    r'(материал|изготовлен|сделан)[\s:]*([а-яё\s-]{3,30})',
    r'\b(дерево|металл|сталь|алюминий|пластик|стекло|керамика|текстиль|хлопок|шерсть|кожа|резина|полимер|пвх|силикон)\b',
    
    # Бренды и производители (из названия и стран)
    r'\b([A-Z][a-zA-Z0-9&\.\-]{2,20})\b',  # Заглавные английские слова
    r'(бренд|производитель|марка|brand|maker)[\s:]*([^;\n]{2,30})',
    
    # Технические характеристики
    r'(мощность|напряжение|ток|частота)[\s:]*([0-9.,]+\s*(?:Вт|кВт|В|А|Гц|кГц|МГц))',
    r'([0-9.,]+\s*(?:Вт|кВт|В|А|Гц))[\s]*(?:мощность|напряжение)?',
    
    # Страны и происхождение
    r'\b(россия|китай|германия|сша|япония|корея|франция|италия|испания|турция|индия|тайвань|вьетнам)\b',
    r'(страна|происхождение|made in|страна производства)[\s:]*([^;\n]{3,20})',
    
    # Упаковка и количество
    r'(упаковка|комплект|количество|в комплекте)[\s:]*([0-9]+\s*(?:шт|уп|пак|набор)?)',
    r'([0-9]+\s*(?:шт|уп|пак|набор))[\s]*(?:в комплекте)?',
    
    # Гарантия и сроки
    r'(гарантия|срок службы|срок годности)[\s:]*([0-9]+\s*(?:мес|месяц|год|лет))',
    
    # Общие свойства
    r'(тип|вид|категория|назначение)[\s:]*([^;\n]{3,40})',
    r'(модель|артикул|код)[\s:]*([a-zA-Z0-9\-_]{2,20})',
    
    # Булевы характеристики
    r'\b(да|нет|есть|имеется|наличие|поддержка)\b[\s:]*([^;\n]{2,20})',
    
    # Цифровые значения с единицами измерения
    r'([0-9.,]+\s*(?:°C|°F|об/мин|ккал|кДж|бар|атм|Па|кПа|МПа))',
    
    # Специфичные для электроники
    r'(процессор|память|оперативная память|hdd|ssd|дисплей|экран)[\s:]*([^;\n]{3,30})',
    
    # Для одежды и обуви
    r'(размер)[\s:]*([0-9xl\s\-]+)',
]

# Ключевые слова для фильтрации мусора
STOP_WORDS = {
    'null', 'нет', 'да', 'не указано', 'не указан', 'отсутствует', 
    'пусто', 'empty', 'none', 'nan', 'undefined', '0', '1'
}

# ============================= ИНИЦИАЛИЗАЦИЯ МОДЕЛИ =============================
try:
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = SentenceTransformer(MODEL_NAME, device=device)
    logger.info(f"Модель {MODEL_NAME} загружена на {device}")
except Exception as e:
    logger.error(f"Ошибка модели: {e}")
    model = None

# ============================= УМНЫЙ ПАРСЕР ХАРАКТЕРИСТИК =============================
class UniversalCharacteristicsExtractor:
    def __init__(self):
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in UNIVERSAL_PATTERNS]
    
    def extract_from_text(self, text: str) -> List[str]:
        """Извлекает характеристики из произвольного текста"""
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
                        continue
                else:
                    key, value = "", match.strip()
                
                # Очистка и валидация
                char = self.clean_characteristic(key, value)
                if char and self.is_valid_characteristic(char):
                    characteristics.append(char)
        
        return list(set(characteristics))  # Убираем дубликаты
    
    def preprocess_text(self, text: str) -> str:
        """Предобработка текста для улучшения извлечения"""
        # Заменяем разделители на пробелы
        text = re.sub(r'[;,\|/]', ' ', text)
        # Убираем лишние пробелы
        text = re.sub(r'\s+', ' ', text)
        # Добавляем пробелы вокруг двоеточий для улучшения парсинга
        text = re.sub(r':', ' : ', text)
        return text.lower().strip()
    
    def clean_characteristic(self, key: str, value: str) -> str:
        """Очистка и форматирование характеристики"""
        if not value or len(value) < 2 or len(value) > 50:
            return ""
        
        # Фильтрация стоп-слов
        if any(stop_word in value.lower() for stop_word in STOP_WORDS):
            return ""
        
        # Нормализация ключа
        if not key:
            key = "характеристика"
        else:
            key = key.replace('_', ' ').title()
        
        # Очистка значения
        value = re.sub(r'[^\w\s\d.,°\-/]', '', value)
        value = re.sub(r'\s+', ' ', value).strip()
        
        return f"{key}: {value}" if value else ""
    
    def is_valid_characteristic(self, char: str) -> bool:
        """Проверка валидности характеристики"""
        if len(char) < 5 or len(char) > 100:
            return False
        
        # Проверка на мусорные паттерны
        invalid_patterns = [
            r'^[0-9\s\.\,]+$',  # Только цифры
            r'http',  # URL
            r'@',  # Email
        ]
        
        return not any(re.search(pattern, char, re.IGNORECASE) for pattern in invalid_patterns)

# ============================= ЗАГРУЗКА ДАННЫХ =============================
def load_data():
    logger.info("Загрузка данных...")
    
    # Определение кодировки
    def detect_encoding(file_path):
        with open(file_path, 'rb') as f:
            return chardet.detect(f.read(10000)).get('encoding', 'utf-8')
    
    encoding = detect_encoding(CSV_PATH)
    
    try:
        df = pd.read_csv(CSV_PATH, dtype=str, low_memory=False, encoding=encoding).fillna("")
    except UnicodeDecodeError:
        for enc in ['windows-1251', 'latin-1', 'cp1251']:
            try:
                df = pd.read_csv(CSV_PATH, dtype=str, low_memory=False, encoding=enc).fillna("")
                logger.info(f"Загружено с кодировкой: {enc}")
                break
            except:
                continue
        else:
            df = pd.read_csv(CSV_PATH, dtype=str, low_memory=False, encoding='utf-8', on_bad_lines='skip').fillna("")
    
    # Проверка колонок
    required_cols = ['id_сте', 'id_категории', 'название_категории']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        logger.error(f"Отсутствуют колонки: {missing_cols}")
        raise ValueError(f"Отсутствуют колонки: {missing_cols}")
    
    # Собираем все текстовые данные
    spec_cols = [col for col in df.columns if col.startswith('spec')]
    text_cols = ['название_категории'] + spec_cols
    
    # Добавляем колонки стран если есть
    country_cols = [col for col in df.columns if 'страна' in col.lower()]
    text_cols.extend(country_cols)
    
    logger.info(f"Колонки для анализа: {text_cols}")
    
    # Объединяем все текстовые данные
    df['all_text_data'] = df[text_cols].apply(
        lambda row: ' ; '.join([str(x) for x in row if str(x) not in ['nan', '', 'None']]), 
        axis=1
    )
    
    # Фильтруем пустые
    initial_count = len(df)
    df = df[df['all_text_data'].str.len() > 10]
    
    logger.info(f"Загружено строк: {initial_count:,}")
    logger.info(f"После фильтрации: {len(df):,}")
    logger.info(f"Уникальных категорий: {df['id_категории'].nunique()}")
    
    return df

# ============================= ОБРАБОТКА КАТЕГОРИЙ =============================
def process_categories_with_universal_extractor(dataframe):
    logger.info("Универсальное извлечение характеристик...")
    
    extractor = UniversalCharacteristicsExtractor()
    category_chars = defaultdict(list)
    category_item_ids = defaultdict(list)
    category_counts = defaultdict(int)
    
    for _, row in tqdm(dataframe.iterrows(), total=len(dataframe)):
        category_id = row['id_категории']
        item_id = row['id_сте']
        text_data = row['all_text_data']
        
        # Извлекаем характеристики из всего текста
        chars = extractor.extract_from_text(text_data)
        
        if chars:
            category_chars[category_id].extend(chars)
            category_item_ids[category_id].append(item_id)
            category_counts[category_id] += 1
    
    return category_chars, category_item_ids, category_counts

# ============================= УМНАЯ ДЕДУПЛИКАЦИЯ =============================
def smart_deduplicate_features(features: List[str], top_k: int = TOP_K) -> List[str]:
    """Умная дедупликация с использованием эмбеддингов"""
    if len(features) <= top_k:
        return features
    
    if model is None or len(features) == 0:
        return features[:top_k]
    
    try:
        # Простая частотная фильтрация сначала
        counter = Counter(features)
        common_features = [feat for feat, count in counter.most_common(top_k * 2)]
        
        if len(common_features) <= top_k:
            return common_features
        
        # Семантическая дедупликация для топовых характеристик
        embeddings = model.encode(common_features, convert_to_tensor=True)
        kept_indices = []
        
        for i in range(len(common_features)):
            if len(kept_indices) >= top_k:
                break
            
            is_similar = False
            for kept_idx in kept_indices:
                similarity = util.cos_sim(embeddings[i], embeddings[kept_idx]).item()
                if similarity > SIMILARITY_THRESHOLD:
                    is_similar = True
                    break
            
            if not is_similar:
                kept_indices.append(i)
        
        return [common_features[i] for i in kept_indices[:top_k]]
    
    except Exception as e:
        logger.warning(f"Ошибка дедупликации: {e}")
        return [feat for feat, _ in Counter(features).most_common(top_k)]

# ============================= ГЕНЕРАЦИЯ УНИВЕРСАЛЬНОЙ ОНТОЛОГИИ =============================
def generate_universal_ontology(category_chars, category_item_ids, category_counts):
    logger.info("Генерация универсальной онтологии...")
    
    ontology = {}
    category_metadata = {}
    
    for category, chars in tqdm(category_chars.items()):
        if category_counts[category] < MIN_SUPPORT:
            continue
        
        # Умная дедупликация характеристик
        unique_chars = smart_deduplicate_features(chars)
        
        if len(unique_chars) >= 3:  # Минимум 3 характеристики
            category_metadata[category] = {
                "total_items": category_counts[category],
                "item_ids": list(set(category_item_ids[category])),
                "characteristics_count": len(unique_chars),
                "sample_characteristics": unique_chars[:5]  # Примеры для отладки
            }
            
            ontology[category] = unique_chars
    
    logger.info(f"Сгенерировано категорий: {len(ontology)}")
    return ontology, category_metadata

# ============================= СОХРАНЕНИЕ РЕЗУЛЬТАТОВ =============================
def save_universal_results(ontology, metadata, total_rows):
    Path(OUTPUT_DIR).mkdir(exist_ok=True)
    
    # Сохраняем полную онтологию
    output_data = {
        "metadata": {
            "source_file": CSV_PATH,
            "processed_rows": total_rows,
            "total_categories": len(ontology),
            "min_support_threshold": MIN_SUPPORT,
            "max_characteristics_per_category": TOP_K,
            "model": MODEL_NAME,
            "note": "Универсальная онтология характеристик для всех категорий товаров"
        },
        "categories": {}
    }
    
    for cat_id, chars in ontology.items():
        output_data["categories"][cat_id] = {
            "characteristics": chars,
            "metadata": metadata[cat_id]
        }
    
    # Сохраняем JSON
    json_path = Path(OUTPUT_DIR) / "universal_characteristics_ontology.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Универсальная онтология сохранена: {json_path}")
    
    # Сохраняем CSV для анализа
    csv_data = []
    for cat_id, cat_data in output_data["categories"].items():
        for char in cat_data["characteristics"]:
            csv_data.append({
                "category_id": cat_id,
                "characteristic": char,
                "total_items": cat_data["metadata"]["total_items"],
                "sample_item_ids": ", ".join(cat_data["metadata"]["item_ids"][:3])
            })
    
    csv_path = Path(OUTPUT_DIR) / "universal_characteristics_for_analysis.csv"
    pd.DataFrame(csv_data).to_csv(csv_path, index=False, encoding="utf-8")
    logger.info(f"CSV для анализа сохранен: {csv_path}")
    
    return output_data

# ============================= АНАЛИЗ РЕЗУЛЬТАТОВ =============================
def analyze_results(ontology):
    """Анализ качества извлеченных характеристик"""
    logger.info("Анализ результатов...")
    
    total_chars = sum(len(chars) for chars in ontology.values())
    avg_chars_per_cat = total_chars / len(ontology) if ontology else 0
    
    # Собираем статистику по типам характеристик
    char_types = Counter()
    for chars in ontology.values():
        for char in chars:
            if 'размер' in char.lower():
                char_types['размеры'] += 1
            elif 'цвет' in char.lower():
                char_types['цвета'] += 1
            elif 'материал' in char.lower():
                char_types['материалы'] += 1
            elif any(brand in char.lower() for brand in ['бренд', 'производитель']):
                char_types['бренды'] += 1
            elif any(unit in char for unit in ['кг', 'г', 'л', 'мл']):
                char_types['вес_объем'] += 1
            elif any(unit in char for unit in ['мм', 'см', 'дюйм']):
                char_types['размеры'] += 1
            else:
                char_types['прочие'] += 1
    
    logger.info("=== СТАТИСТИКА ИЗВЛЕЧЕНИЯ ===")
    logger.info(f"Всего категорий: {len(ontology)}")
    logger.info(f"Всего характеристик: {total_chars}")
    logger.info(f"Среднее характеристик на категорию: {avg_chars_per_cat:.1f}")
    logger.info("Распределение по типам:")
    for char_type, count in char_types.most_common():
        logger.info(f"  {char_type}: {count}")

# ============================= MAIN =============================
def main():
    try:
        logger.info("🚀 ЗАПУСК УНИВЕРСАЛЬНОГО ИЗВЛЕЧЕНИЯ ХАРАКТЕРИСТИК")
        
        # Загрузка данных
        data = load_data()
        
        # Извлечение характеристик
        chars, item_ids, counts = process_categories_with_universal_extractor(data)
        
        # Генерация онтологии
        ontology, metadata = generate_universal_ontology(chars, item_ids, counts)
        
        # Сохранение результатов
        save_universal_results(ontology, metadata, len(data))
        
        # Анализ результатов
        analyze_results(ontology)
        
        logger.info("✅ УНИВЕРСАЛЬНАЯ ОНТОЛОГИЯ ХАРАКТЕРИСТИК ГОТОВА!")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        raise

if __name__ == "__main__":
    main()