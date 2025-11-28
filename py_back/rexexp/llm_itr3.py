# universal_characteristics_counter.py
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

try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x: x

# ============================= КОНФИГУРАЦИЯ =============================
CSV_PATH = "py_back/rexexp/data/result_itr4.csv"
OUTPUT_DIR = "result"
MIN_SUPPORT = 3  # Еще меньше для максимального покрытия
TOP_K = 20  # Больше характеристик на категорию
SIMILARITY_THRESHOLD = 0.85
MODEL_NAME = "ai-forever/sbert_large_mt_nlu_ru"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("characteristics_counter.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================= УНИВЕРСАЛЬНЫЕ ПАТТЕРНЫ =============================
UNIVERSAL_PATTERNS = [
    # Размеры и измерения
    r'(размер|диаметр|ширина|высота|глубина|толщина|длина|радиус)[\s:]*([0-9.,]+[\\s]*(?:мм|см|м|дюйм|″|"|см³|м²|л|кг|г|мг)?)',
    r'([0-9.,]+\s*(?:мм|см|м|дюйм|″|"|×|x|\*))[\s]*(?:размер|диаметр|ширина|высота)?',
    
    # Вес и объем
    r'(вес|масса|объем|ёмкость)[\s:]*([0-9.,]+\s*(?:кг|г|мг|л|мл|см³|м³))',
    r'([0-9.,]+\s*(?:кг|г|мг|л|мл))[\s]*(?:вес|масса|объем)?',
    
    # Цвета
    r'(цвет|окрас)[\s:]*([а-яё\s-]{3,20})',
    r'\b(черный|белый|красный|синий|зеленый|желтый|оранжевый|фиолетовый|розовый|коричневый|серый|голубой|серебристый|золотой|бежевый|металлик|прозрачный)\b',
    
    # Материалы
    r'(материал|изготовлен|сделан|состав)[\s:]*([а-яё\s-]{3,30})',
    r'\b(дерево|металл|сталь|алюминий|пластик|стекло|керамика|текстиль|хлопок|шерсть|кожа|резина|полимер|пвх|силикон|нержавеющая сталь|деревянный|металлический|пластиковый|стеклянный)\b',
    
    # Бренды и производители
    r'\b([A-Z][a-zA-Z0-9&\.\-]{2,25})\b',
    r'(бренд|производитель|марка|brand|maker|фирма)[\s:]*([^;\n]{2,30})',
    
    # Технические характеристики
    r'(мощность|напряжение|ток|частота|скорость|обороты)[\s:]*([0-9.,]+\s*(?:Вт|кВт|В|А|Гц|кГц|МГц|об/мин|км/ч))',
    r'([0-9.,]+\s*(?:Вт|кВт|В|А|Гц|об/мин))[\s]*(?:мощность|напряжение)?',
    
    # Страны и происхождение
    r'\b(россия|китай|германия|сша|япония|корея|франция|италия|испания|турция|индия|тайвань|вьетнам|беларусь|украина|польша|чехия)\b',
    r'(страна|происхождение|made in|страна производства)[\s:]*([^;\n]{3,20})',
    
    # Упаковка и количество
    r'(упаковка|комплект|количество|в комплекте|шт|штук)[\s:]*([0-9]+\s*(?:шт|уп|пак|набор|единиц)?)',
    r'([0-9]+\s*(?:шт|уп|пак|набор|единиц))[\s]*(?:в комплекте)?',
    
    # Гарантия и сроки
    r'(гарантия|срок службы|срок годности)[\s:]*([0-9]+\s*(?:мес|месяц|год|лет))',
    
    # Общие свойства
    r'(тип|вид|категория|назначение|применение)[\s:]*([^;\n]{3,50})',
    r'(модель|артикул|код|серия)[\s:]*([a-zA-Z0-9\-_]{2,25})',
    
    # Булевы характеристики
    r'\b(да|нет|есть|имеется|наличие|поддержка|возможно)\b[\s:]*([^;\n]{2,30})',
    
    # Цифровые значения с единицами измерения
    r'([0-9.,]+\s*(?:°C|°F|об/мин|ккал|кДж|бар|атм|Па|кПа|МПа|dB|дБ|люкс|лк))',
    
    # Специфичные для электроники
    r'(процессор|память|оперативная память|hdd|ssd|дисплей|экран|разрешение|ОС|ios|android|windows)[\s:]*([^;\n]{3,40})',
    
    # Для одежды и обуви
    r'(размер)[\s:]*([0-9xl\s\-]+)',
    r'\b(xs|s|m|l|xl|xxl|xxxl)\b',
    
    # Для мебели
    r'(спальня|гостиная|кухня|офис|детская|прихожая)[\s]*(?:мебель|комната)?',
    
    # Общие качественные характеристики
    r'\b(новый|б/у|бу|восстановленный|оригинал|оригинальный|аналог|замена|качественный|премиум|эконом)\b',
]

# Ключевые слова для фильтрации мусора
STOP_WORDS = {
    'null', 'нет', 'да', 'не указано', 'не указан', 'отсутствует', 
    'пусто', 'empty', 'none', 'nan', 'undefined', '0', '1', 'н/д'
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
                char = self.process_match(match)
                if char and self.is_valid_characteristic(char):
                    characteristics.append(char)
        
        return list(set(characteristics))
    
    def process_match(self, match) -> str:
        """Обрабатывает найденное соответствие"""
        if isinstance(match, tuple):
            if len(match) >= 2:
                key, value = match[0].strip(), match[1].strip()
            else:
                return ""
        else:
            key, value = "", match.strip()
        
        return self.clean_characteristic(key, value)
    
    def preprocess_text(self, text: str) -> str:
        """Предобработка текста для улучшения извлечения"""
        text = re.sub(r'[;,\|/]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r':', ' : ', text)
        return text.lower().strip()
    
    def clean_characteristic(self, key: str, value: str) -> str:
        """Очистка и форматирование характеристики"""
        if not value or len(value) < 2 or len(value) > 60:
            return ""
        
        # Фильтрация стоп-слов
        if any(stop_word in value.lower() for stop_word in STOP_WORDS):
            return ""
        
        # Нормализация ключа
        if not key:
            # Автоматическое определение типа по значению
            key = self.detect_key_by_value(value)
        else:
            key = key.replace('_', ' ').title()
        
        # Очистка значения
        value = re.sub(r'[^\w\s\d.,°\-/]', '', value)
        value = re.sub(r'\s+', ' ', value).strip()
        
        return f"{key}: {value}" if value else ""
    
    def detect_key_by_value(self, value: str) -> str:
        """Автоматически определяет тип характеристики по значению"""
        value_lower = value.lower()
        
        if any(unit in value_lower for unit in ['мм', 'см', 'дюйм', '"', '″']):
            return "Размер"
        elif any(unit in value_lower for unit in ['кг', 'г', 'мг']):
            return "Вес"
        elif any(unit in value_lower for unit in ['л', 'мл']):
            return "Объем"
        elif any(unit in value_lower for unit in ['вт', 'квт', 'в', 'а', 'гц']):
            return "Технические параметры"
        elif any(color in value_lower for color in ['черный', 'белый', 'красный', 'синий', 'зеленый']):
            return "Цвет"
        elif any(brand in value_lower for brand in ['samsung', 'lg', 'bosch', 'iphone']):
            return "Бренд"
        else:
            return "Характеристика"
    
    def is_valid_characteristic(self, char: str) -> bool:
        """Проверка валидности характеристики"""
        if len(char) < 5 or len(char) > 100:
            return False
        
        invalid_patterns = [
            r'^[0-9\s\.\,]+$',
            r'http',
            r'@',
        ]
        
        return not any(re.search(pattern, char, re.IGNORECASE) for pattern in invalid_patterns)

# ============================= ЗАГРУЗКА ДАННЫХ =============================
def load_data():
    logger.info("Загрузка данных...")
    
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

# ============================= ОБРАБОТКА КАТЕГОРИЙ (ТОЛЬКО ПОДСЧЕТ) =============================
def extract_characteristics_with_counter(dataframe):
    """Извлекает характеристики и считает частоты без хранения id СТЕ"""
    logger.info("Извлечение характеристик с подсчетом частот...")
    
    extractor = UniversalCharacteristicsExtractor()
    category_characteristics = defaultdict(Counter)  # Counter для каждой категории
    category_names = {}  # Названия категорий
    
    for _, row in tqdm(dataframe.iterrows(), total=len(dataframe)):
        category_id = row['id_категории']
        category_name = row['название_категории']
        text_data = row['all_text_data']
        
        # Сохраняем название категории
        category_names[category_id] = category_name
        
        # Извлекаем характеристики
        chars = extractor.extract_from_text(text_data)
        
        # Считаем частоты
        for char in chars:
            category_characteristics[category_id][char] += 1
    
    return category_characteristics, category_names

# ============================= УМНАЯ ДЕДУПЛИКАЦИЯ =============================
def smart_deduplicate_with_frequency(char_counter: Counter, top_k: int = TOP_K) -> List[Dict]:
    """Умная дедупликация с учетом частот"""
    if len(char_counter) == 0:
        return []
    
    # Берем топовые характеристики по частоте
    common_chars = char_counter.most_common(top_k * 3)
    
    if len(common_chars) <= top_k:
        return [{"characteristic": char, "frequency": freq} for char, freq in common_chars]
    
    if model is None:
        return [{"characteristic": char, "frequency": freq} for char, freq in common_chars[:top_k]]
    
    try:
        # Семантическая дедупликация
        features = [char for char, freq in common_chars]
        embeddings = model.encode(features, convert_to_tensor=True)
        
        kept_indices = []
        kept_chars = []
        
        for i, (char, freq) in enumerate(common_chars):
            if len(kept_indices) >= top_k:
                break
            
            is_similar = False
            for kept_idx in kept_indices:
                similarity = util.cos_sim(embeddings[i], embeddings[kept_idx]).item()
                if similarity > SIMILARITY_THRESHOLD:
                    is_similar = True
                    # Объединяем частоты похожих характеристик
                    kept_chars[kept_indices.index(kept_idx)]["frequency"] += freq
                    break
            
            if not is_similar:
                kept_indices.append(i)
                kept_chars.append({"characteristic": char, "frequency": freq})
        
        # Сортируем по убыванию частоты
        kept_chars.sort(key=lambda x: x["frequency"], reverse=True)
        return kept_chars[:top_k]
    
    except Exception as e:
        logger.warning(f"Ошибка дедупликации: {e}")
        return [{"characteristic": char, "frequency": freq} for char, freq in common_chars[:top_k]]

# ============================= ГЕНЕРАЦИЯ ОНТОЛОГИИ С ЧАСТОТАМИ =============================
def generate_ontology_with_frequencies(category_characteristics, category_names):
    """Генерирует онтологию с частотами характеристик"""
    logger.info("Генерация онтологии с частотами...")
    
    ontology = {}
    category_stats = {}
    
    for category_id, char_counter in tqdm(category_characteristics.items()):
        total_items = sum(char_counter.values())
        
        if total_items < MIN_SUPPORT:
            continue
        
        # Умная дедупликация с частотами
        unique_chars = smart_deduplicate_with_frequency(char_counter)
        
        if len(unique_chars) >= 2:  # Минимум 2 характеристики
            category_stats[category_id] = {
                "category_name": category_names[category_id],
                "total_items": total_items,
                "total_unique_characteristics": len(char_counter),
                "selected_characteristics": len(unique_chars)
            }
            
            ontology[category_id] = unique_chars
    
    logger.info(f"Сгенерировано категорий: {len(ontology)}")
    return ontology, category_stats

# ============================= СОХРАНЕНИЕ РЕЗУЛЬТАТОВ =============================
def save_results_with_frequencies(ontology, category_stats, total_rows):
    """Сохраняет результаты с частотами характеристик"""
    Path(OUTPUT_DIR).mkdir(exist_ok=True)
    
    # Подготовка данных для JSON
    output_data = {
        "metadata": {
            "source_file": CSV_PATH,
            "total_processed_rows": total_rows,
            "categories_with_characteristics": len(ontology),
            "min_support_threshold": MIN_SUPPORT,
            "max_characteristics_per_category": TOP_K,
            "note": "Универсальные характеристики товаров с частотами"
        },
        "categories": {}
    }
    
    for cat_id, characteristics in ontology.items():
        output_data["categories"][cat_id] = {
            "category_name": category_stats[cat_id]["category_name"],
            "total_items": category_stats[cat_id]["total_items"],
            "characteristics": characteristics
        }
    
    # Сохраняем JSON
    json_path = Path(OUTPUT_DIR) / "characteristics_with_frequencies.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Онтология с частотами сохранена: {json_path}")
    
    # Сохраняем плоский CSV для анализа
    csv_data = []
    for cat_id, cat_data in output_data["categories"].items():
        for char_data in cat_data["characteristics"]:
            csv_data.append({
                "category_id": cat_id,
                "category_name": cat_data["category_name"],
                "characteristic": char_data["characteristic"],
                "frequency": char_data["frequency"],
                "total_items_in_category": cat_data["total_items"]
            })
    
    csv_path = Path(OUTPUT_DIR) / "characteristics_frequency_analysis.csv"
    pd.DataFrame(csv_data).to_csv(csv_path, index=False, encoding="utf-8")
    logger.info(f"CSV с частотами сохранен: {csv_path}")
    
    return output_data

# ============================= АНАЛИЗ РЕЗУЛЬТАТОВ =============================
def analyze_frequency_results(ontology):
    """Анализ результатов с частотами"""
    logger.info("Анализ результатов с частотами...")
    
    total_categories = len(ontology)
    total_characteristics = sum(len(chars) for chars in ontology.values())
    
    # Статистика по частотам
    all_frequencies = []
    for cat_id, characteristics in ontology.items():
        for char_data in characteristics:
            all_frequencies.append(char_data["frequency"])
    
    if all_frequencies:
        avg_frequency = sum(all_frequencies) / len(all_frequencies)
        max_frequency = max(all_frequencies)
        min_frequency = min(all_frequencies)
    else:
        avg_frequency = max_frequency = min_frequency = 0
    
    # Анализ типов характеристик
    char_types = Counter()
    for characteristics in ontology.values():
        for char_data in characteristics:
            char = char_data["characteristic"].lower()
            if 'размер' in char:
                char_types['размеры'] += 1
            elif 'цвет' in char:
                char_types['цвета'] += 1
            elif 'материал' in char:
                char_types['материалы'] += 1
            elif any(brand in char for brand in ['бренд', 'производитель']):
                char_types['бренды'] += 1
            elif any(unit in char for unit in ['кг', 'г', 'л', 'мл']):
                char_types['вес_объем'] += 1
            elif any(unit in char for unit in ['мм', 'см', 'дюйм']):
                char_types['размеры'] += 1
            elif any(unit in char for unit in ['вт', 'в', 'а', 'гц']):
                char_types['технические'] += 1
            else:
                char_types['прочие'] += 1
    
    logger.info("=== СТАТИСТИКА ЧАСТОТ ===")
    logger.info(f"Всего категорий: {total_categories}")
    logger.info(f"Всего характеристик: {total_characteristics}")
    logger.info(f"Средняя частота: {avg_frequency:.1f}")
    logger.info(f"Максимальная частота: {max_frequency}")
    logger.info(f"Минимальная частота: {min_frequency}")
    logger.info("Распределение по типам:")
    for char_type, count in char_types.most_common():
        percentage = (count / total_characteristics) * 100 if total_characteristics > 0 else 0
        logger.info(f"  {char_type}: {count} ({percentage:.1f}%)")

# ============================= MAIN =============================
def main():
    try:
        logger.info("🚀 ЗАПУСК ПОДСЧЕТА ХАРАКТЕРИСТИК БЕЗ ID СТЕ")
        
        # Загрузка данных
        data = load_data()
        
        # Извлечение характеристик с подсчетом частот
        category_chars, category_names = extract_characteristics_with_counter(data)
        
        # Генерация онтологии с частотами
        ontology, category_stats = generate_ontology_with_frequencies(category_chars, category_names)
        
        # Сохранение результатов
        save_results_with_frequencies(ontology, category_stats, len(data))
        
        # Анализ результатов
        analyze_frequency_results(ontology)
        
        logger.info("✅ ПОДСЧЕТ ХАРАКТЕРИСТИК УСПЕШНО ЗАВЕРШЕН!")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        raise

if __name__ == "__main__":
    main()