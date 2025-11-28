# smart_characteristics_extractor.py
import re
import json
import logging
import pandas as pd
import torch
from collections import Counter, defaultdict
from transformers import AutoTokenizer, AutoModel
from pathlib import Path
import chardet
from typing import List, Dict, Any
import numpy as np

try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x: x

# ============================= КОНФИГУРАЦИЯ =============================
CSV_PATH = "py_back/rexexp/data/result_itr4.csv"
OUTPUT_DIR = "result"
MIN_SUPPORT = 2
TOP_K = 15

# Используем русскоязычную модель для лучшего понимания контекста
MODEL_NAME = "cointegrated/rubert-tiny2"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("smart_extractor.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================= ИНИЦИАЛИЗАЦИЯ МОДЕЛИ =============================
try:
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME).to(device)
    logger.info(f"Модель {MODEL_NAME} загружена на {device}")
except Exception as e:
    logger.error(f"Ошибка загрузки модели: {e}")
    model = None
    tokenizer = None

# ============================= УМНЫЙ КЛАССИФИКАТОР ХАРАКТЕРИСТИК =============================
class SmartCharacteristicsClassifier:
    def __init__(self):
        self.key_phrases = {
            'размер': ['размер', 'диаметр', 'ширина', 'высота', 'толщина', 'длина', 'радиус'],
            'вес': ['вес', 'масса', 'кг', 'г', 'мг'],
            'объем': ['объем', 'емкость', 'л', 'мл', 'см3'],
            'цвет': ['цвет', 'окрас', 'оттенок'],
            'материал': ['материал', 'состав', 'изготовлен', 'сделан'],
            'бренд': ['бренд', 'марка', 'производитель', 'фирма'],
            'страна': ['страна', 'происхождение', 'made in'],
            'мощность': ['мощность', 'ватт', 'вт', 'квт'],
            'напряжение': ['напряжение', 'вольт', 'в'],
            'скорость': ['скорость', 'обороты', 'об/мин'],
            'гарантия': ['гарантия', 'срок службы', 'срок годности'],
            'тип': ['тип', 'вид', 'категория', 'назначение'],
            'модель': ['модель', 'артикул', 'код'],
            'количество': ['количество', 'шт', 'штук', 'комплект']
        }
        
    def classify_characteristic(self, text: str) -> str:
        """Классифицирует характеристику по типу"""
        text_lower = text.lower()
        
        for category, phrases in self.key_phrases.items():
            if any(phrase in text_lower for phrase in phrases):
                return category
        
        return "другое"

# ============================= СЕМАНТИЧЕСКИЙ АНАЛИЗАТОР =============================
class SemanticAnalyzer:
    def __init__(self):
        self.classifier = SmartCharacteristicsClassifier()
    
    def get_embeddings(self, texts: List[str]) -> np.ndarray:
        """Получает эмбеддинги для текстов"""
        if model is None or tokenizer is None:
            return np.random.randn(len(texts), 128)
        
        try:
            inputs = tokenizer(texts, padding=True, truncation=True, max_length=128, return_tensors="pt")
            inputs = {k: v.to(device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = model(**inputs)
            
            # Используем эмбеддинги [CLS] токена
            embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()
            return embeddings
            
        except Exception as e:
            logger.warning(f"Ошибка получения эмбеддингов: {e}")
            return np.random.randn(len(texts), 128)
    
    def semantic_similarity(self, text1: str, text2: str) -> float:
        """Вычисляет семантическую схожесть двух текстов"""
        embeddings = self.get_embeddings([text1, text2])
        similarity = np.dot(embeddings[0], embeddings[1]) / (
            np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
        )
        return float(similarity)

# ============================= УМНЫЙ ЭКСТРАКТОР ХАРАКТЕРИСТИК =============================
class IntelligentCharacteristicsExtractor:
    def __init__(self):
        self.semantic_analyzer = SemanticAnalyzer()
        self.compiled_patterns = self._build_smart_patterns()
    
    def _build_smart_patterns(self) -> List[re.Pattern]:
        """Строит умные паттерны для извлечения характеристик"""
        patterns = [
            # Размеры с единицами измерения
            r'(\d+[.,]?\d*\s*(?:мм|см|м|дюйм|″|"|×|x|\*))',
            # Вес и объем
            r'(\d+[.,]?\d*\s*(?:кг|г|мг|л|мл))',
            # Технические параметры
            r'(\d+[.,]?\d*\s*(?:Вт|кВт|В|А|Гц|об/мин|км/ч))',
            # Температура и давление
            r'(\d+[.,]?\d*\s*(?:°C|°F|бар|атм|кПа))',
            # Цвета
            r'\b(черный|белый|красный|синий|зеленый|желтый|оранжевый|фиолетовый|розовый|коричневый|серый)\b',
            # Бренды (слова с заглавной буквы)
            r'\b([A-ZА-Я][a-zа-яA-ZА-Я0-9&\.\-]{1,20})\b',
            # Страны
            r'\b(Россия|Китай|Германия|США|Япония|Корея|Франция|Италия|Испания|Турция|Индия)\b',
        ]
        return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    
    def extract_smart_characteristics(self, text: str) -> List[Dict]:
        """Умное извлечение характеристик с семантическим анализом"""
        if not text or len(str(text)) < 10:
            return []
        
        text = self._clean_text(text)
        characteristics = []
        
        # Извлекаем кандидаты с помощью паттернов
        candidates = self._extract_candidates(text)
        
        # Обрабатываем каждого кандидата
        for candidate in candidates:
            if self._is_valid_characteristic(candidate):
                category = self.semantic_analyzer.classifier.classify_characteristic(candidate)
                characteristics.append({
                    "text": candidate,
                    "category": category,
                    "confidence": self._calculate_confidence(candidate, category)
                })
        
        # Сортируем по уверенности
        characteristics.sort(key=lambda x: x["confidence"], reverse=True)
        return characteristics[:TOP_K]
    
    def _clean_text(self, text: str) -> str:
        """Очистка текста"""
        # Убираем мусор
        text = re.sub(r'[^\w\s\d.,°\-/×x*"″]', ' ', str(text))
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _extract_candidates(self, text: str) -> List[str]:
        """Извлекает кандидатов в характеристики"""
        candidates = set()
        
        # Используем паттерны
        for pattern in self.compiled_patterns:
            matches = pattern.findall(text)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                candidate = str(match).strip()
                if len(candidate) >= 2 and len(candidate) <= 50:
                    candidates.add(candidate)
        
        # Дополнительно ищем ключевые фразы
        key_phrases = self._extract_key_phrases(text)
        candidates.update(key_phrases)
        
        return list(candidates)
    
    def _extract_key_phrases(self, text: str) -> List[str]:
        """Извлекает ключевые фразы с помощью эвристик"""
        phrases = []
        words = text.split()
        
        # Ищем паттерны типа "ключ: значение"
        key_value_patterns = [
            r'(\w+)\s*[:=]\s*([^,;]{3,30})',
            r'(\w+)\s+([^,;]{3,30})'
        ]
        
        for pattern in key_value_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for key, value in matches:
                if (len(key) > 2 and len(value) > 2 and 
                    key.lower() not in ['и', 'в', 'на', 'с', 'по']):
                    phrases.append(f"{key}: {value}")
        
        return phrases
    
    def _is_valid_characteristic(self, candidate: str) -> bool:
        """Проверяет валидность характеристики"""
        if len(candidate) < 3 or len(candidate) > 60:
            return False
        
        # Фильтруем мусор
        stop_patterns = [
            r'^[0-9\s.,]+$',  # Только цифры
            r'http',          # URL
            r'@',             # Email
            r'null', 'undefined', 'nan'  # Технические значения
        ]
        
        if any(re.search(pattern, candidate, re.IGNORECASE) for pattern in stop_patterns):
            return False
        
        return True
    
    def _calculate_confidence(self, characteristic: str, category: str) -> float:
        """Вычисляет уверенность в характеристике"""
        confidence = 0.5  # Базовая уверенность
        
        # Повышаем уверенность для характеристик с единицами измерения
        if re.search(r'\d+[.,]?\d*\s*(?:мм|см|кг|г|л|мл|Вт|В|А|Гц)', characteristic):
            confidence += 0.3
        
        # Повышаем для известных категорий
        if category != "другое":
            confidence += 0.2
        
        # Понижаем для слишком коротких характеристик
        if len(characteristic) < 5:
            confidence -= 0.2
        
        return min(1.0, max(0.1, confidence))

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

# ============================= ОБРАБОТКА КАТЕГОРИЙ =============================
def process_categories_intelligently(dataframe):
    """Умная обработка категорий с семантическим анализом"""
    logger.info("Умное извлечение характеристик...")
    
    extractor = IntelligentCharacteristicsExtractor()
    category_characteristics = defaultdict(list)
    category_names = {}
    
    for _, row in tqdm(dataframe.iterrows(), total=len(dataframe)):
        category_id = row['id_категории']
        category_name = row['название_категории']
        text_data = row['all_text_data']
        
        category_names[category_id] = category_name
        
        # Извлекаем умные характеристики
        characteristics = extractor.extract_smart_characteristics(text_data)
        
        if characteristics:
            category_characteristics[category_id].extend(characteristics)
    
    return category_characteristics, category_names

# ============================= СЕМАНТИЧЕСКАЯ ДЕДУПЛИКАЦИЯ =============================
def semantic_deduplication(characteristics_list: List[Dict]) -> List[Dict]:
    """Семантическая дедупликация характеристик"""
    if len(characteristics_list) <= 1:
        return characteristics_list
    
    analyzer = SemanticAnalyzer()
    unique_chars = []
    
    for char in characteristics_list:
        is_duplicate = False
        
        for unique_char in unique_chars:
            similarity = analyzer.semantic_similarity(char["text"], unique_char["text"])
            
            if similarity > 0.8:  # Порог схожести
                is_duplicate = True
                # Объединяем уверенность
                unique_char["confidence"] = max(unique_char["confidence"], char["confidence"])
                break
        
        if not is_duplicate:
            unique_chars.append(char)
    
    return unique_chars

# ============================= ГЕНЕРАЦИЯ УМНОЙ ОНТОЛОГИИ =============================
def generate_intelligent_ontology(category_characteristics, category_names):
    """Генерация умной онтологии"""
    logger.info("Генерация умной онтологии...")
    
    ontology = {}
    category_stats = {}
    
    for category_id, chars_list in tqdm(category_characteristics.items()):
        if len(chars_list) < MIN_SUPPORT:
            continue
        
        # Семантическая дедупликация
        unique_chars = semantic_deduplication(chars_list)
        
        # Сортируем по уверенности и берем топ
        unique_chars.sort(key=lambda x: x["confidence"], reverse=True)
        top_chars = unique_chars[:TOP_K]
        
        if len(top_chars) >= 2:
            category_stats[category_id] = {
                "category_name": category_names[category_id],
                "total_characteristics": len(chars_list),
                "selected_characteristics": len(top_chars)
            }
            
            # Сохраняем только тексты характеристик (без метаданных)
            ontology[category_id] = [char["text"] for char in top_chars]
    
    logger.info(f"Сгенерировано категорий: {len(ontology)}")
    return ontology, category_stats

# ============================= СОХРАНЕНИЕ РЕЗУЛЬТАТОВ =============================
def save_intelligent_results(ontology, category_stats, total_rows):
    """Сохранение результатов умного извлечения"""
    Path(OUTPUT_DIR).mkdir(exist_ok=True)
    
    # ЧИСТАЯ онтология без лишних данных
    output_data = {
        "metadata": {
            "total_processed_rows": total_rows,
            "categories_with_characteristics": len(ontology),
            "model_used": MODEL_NAME,
            "note": "Умная онтология характеристик с семантическим анализом"
        },
        "categories": {}
    }
    
    for cat_id, characteristics in ontology.items():
        output_data["categories"][cat_id] = {
            "category_name": category_stats[cat_id]["category_name"],
            "characteristics": characteristics
        }
    
    # Сохраняем JSON
    json_path = Path(OUTPUT_DIR) / "smart_characteristics_ontology.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Умная онтология сохранена: {json_path}")
    
    # Сохраняем CSV для анализа
    csv_data = []
    for cat_id, cat_data in output_data["categories"].items():
        for char in cat_data["characteristics"]:
            csv_data.append({
                "category_id": cat_id,
                "category_name": cat_data["category_name"],
                "characteristic": char
            })
    
    csv_path = Path(OUTPUT_DIR) / "smart_characteristics_analysis.csv"
    pd.DataFrame(csv_data).to_csv(csv_path, index=False, encoding="utf-8")
    logger.info(f"CSV для анализа сохранен: {csv_path}")
    
    return output_data

# ============================= АНАЛИЗ КАЧЕСТВА =============================
def analyze_quality(ontology):
    """Анализ качества извлеченных характеристик"""
    logger.info("Анализ качества характеристик...")
    
    total_chars = sum(len(chars) for chars in ontology.values())
    categories_with_good_chars = 0
    
    # Анализируем качество по категориям
    for cat_id, characteristics in ontology.items():
        good_chars = 0
        for char in characteristics:
            # Хорошая характеристика содержит конкретные данные
            if (re.search(r'\d', char) or  # содержит цифры
                any(keyword in char.lower() for keyword in ['цвет', 'материал', 'бренд', 'размер']) or
                len(char.split()) >= 2):  # состоит из нескольких слов
                good_chars += 1
        
        if good_chars >= len(characteristics) * 0.6:  # 60% хороших характеристик
            categories_with_good_chars += 1
    
    logger.info("=== КАЧЕСТВО ИЗВЛЕЧЕНИЯ ===")
    logger.info(f"Всего категорий: {len(ontology)}")
    logger.info(f"Категории с хорошими характеристиками: {categories_with_good_chars}")
    logger.info(f"Общее количество характеристик: {total_chars}")
    
    # Показываем примеры хороших характеристик
    good_examples = []
    for chars in list(ontology.values())[:3]:  # Первые 3 категории
        for char in chars[:2]:  # По 2 примера
            if re.search(r'\d', char) or ':' in char:
                good_examples.append(char)
    
    if good_examples:
        logger.info("Примеры хороших характеристик:")
        for example in good_examples[:5]:
            logger.info(f"  - {example}")

# ============================= MAIN =============================
def main():
    try:
        logger.info("🚀 ЗАПУСК УМНОГО ИЗВЛЕЧЕНИЯ ХАРАКТЕРИСТИК")
        
        # Загрузка данных
        data = load_data()
        
        # Умное извлечение характеристик
        category_chars, category_names = process_categories_intelligently(data)
        
        # Генерация онтологии
        ontology, category_stats = generate_intelligent_ontology(category_chars, category_names)
        
        # Сохранение результатов
        save_intelligent_results(ontology, category_stats, len(data))
        
        # Анализ качества
        analyze_quality(ontology)
        
        logger.info("✅ УМНАЯ ОНТОЛОГИЯ ХАРАКТЕРИСТИК ГОТОВА!")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        raise

if __name__ == "__main__":
    main()