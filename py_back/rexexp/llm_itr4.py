# smart_characteristics_extractor_fixed.py
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
from sklearn.metrics.pairwise import cosine_similarity

try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x: x

# ============================= КОНФИГУРАЦИЯ =============================
CSV_PATH = "py_back/rexexp/data/result_itr4.csv"
OUTPUT_DIR = "result"
MIN_SUPPORT = 2
TOP_K = 15
BATCH_SIZE = 32  # Пакетная обработка для ускорения

MODEL_NAME = "cointegrated/rubert-tiny2"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("smart_extractor_fixed.log", encoding='utf-8'),
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

# ============================= УМНЫЙ ЭКСТРАКТОР ХАРАКТЕРИСТИК =============================
class IntelligentCharacteristicsExtractor:
    def __init__(self):
        self.compiled_patterns = self._build_smart_patterns()
    
    def _build_smart_patterns(self) -> List[re.Pattern]:
        """Улучшенные паттерны для извлечения характеристик"""
        patterns = [
            # Ключ-значение с разделителями
            r'(\b(?:размер|диаметр|ширина|высота|толщина|длина|радиус|вес|масса|объем|емкость|цвет|материал|бренд|производитель|марка|страна|мощность|напряжение|скорость|гарантия|тип|вид|категория|назначение|модель|артикул|код|количество|сезонность|индекс)\b)\s*[:=]\s*([^;,\n]{3,50})',
            
            # Размеры с единицами измерения
            r'(\d+[.,]?\d*\s*(?:мм|см|м|дюйм|″|")(?:\s*[x×]\s*\d+[.,]?\d*\s*(?:мм|см|м|дюйм|″|"))*)',
            
            # Вес и объем
            r'(\d+[.,]?\d*\s*(?:кг|г|мг|л|мл|см³|м³))',
            
            # Технические параметры
            r'(\d+[.,]?\d*\s*(?:Вт|кВт|В|А|Гц|Гб|Мб|кбайт|об/мин|км/ч))',
            
            # Цвета
            r'\b(цвет|окрас)\s+(черный|белый|красный|синий|зеленый|желтый|оранжевый|фиолетовый|розовый|коричневый|серый|голубой|бежевый|серебристый|золотой)\b',
            
            # Бренды (улучшенные)
            r'\b((?:[A-ZА-Я][a-zа-я]+)(?:\s+[A-ZА-Я][a-zа-я]+)*)\b(?=\s*(?:бренд|производитель|марка))',
            
            # Страны
            r'\b(Россия|Китай|Германия|США|Япония|Корея|Франция|Италия|Испания|Турция|Индия|Беларусь|Украина)\b',
            
            # Типоразмеры (для шин, электроники и т.д.)
            r'(\d+[.,]?\d*\s*[x×/]\s*\d+[.,]?\d*(?:\s*[x×/]\s*\d+[.,]?\d*)*)',
        ]
        return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    
    def extract_smart_characteristics(self, text: str) -> List[str]:
        """Умное извлечение характеристик"""
        if not text or len(str(text)) < 10:
            return []
        
        text = self._clean_text(text)
        characteristics = set()
        
        # Извлекаем характеристики с помощью паттернов
        for pattern in self.compiled_patterns:
            matches = pattern.findall(text)
            for match in matches:
                if isinstance(match, tuple):
                    if len(match) >= 2:
                        key, value = match[0].strip(), match[1].strip()
                        char = f"{key}: {value}"
                    else:
                        continue
                else:
                    char = str(match).strip()
                
                if self._is_valid_characteristic(char):
                    characteristics.add(char)
        
        # Дополнительно извлекаем ключевые фразы
        key_phrases = self._extract_key_value_pairs(text)
        characteristics.update(key_phrases)
        
        return sorted(list(characteristics))[:TOP_K]
    
    def _clean_text(self, text: str) -> str:
        """Очистка текста"""
        text = re.sub(r'[;,\|/]', ' ', str(text))
        text = re.sub(r'\s+', ' ', text)
        # Добавляем пробелы вокруг разделителей для улучшения парсинга
        text = re.sub(r'([:=])(\S)', r'\1 \2', text)
        text = re.sub(r'(\S)([:=])', r'\1 \2', text)
        return text.strip()
    
    def _extract_key_value_pairs(self, text: str) -> List[str]:
        """Извлекает пары ключ-значение из текста"""
        pairs = []
        
        # Ищем конструкции типа "Ключ: значение" или "Ключ значение"
        patterns = [
            r'(\b[а-яa-z]+\b)\s*[:=]\s*([^;,\n]{3,40})',
            r'(\b[а-яa-z]+\b)\s+([^;,\n]{3,40})(?=\s|$|;)'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                key, value = match.group(1), match.group(2)
                if (self._is_valid_key(key) and self._is_valid_value(value)):
                    pairs.append(f"{key}: {value}")
        
        return pairs
    
    def _is_valid_key(self, key: str) -> bool:
        """Проверяет валидность ключа"""
        key = key.lower()
        stop_keys = {'и', 'в', 'на', 'с', 'по', 'для', 'из', 'от', 'до', 'не'}
        return (len(key) > 2 and 
                key not in stop_keys and
                not key.isdigit())
    
    def _is_valid_value(self, value: str) -> bool:
        """Проверяет валидность значения"""
        value = value.strip()
        stop_values = {'null', 'nan', 'нет', 'не указано', 'пусто'}
        return (len(value) >= 2 and 
                len(value) <= 50 and
                value.lower() not in stop_values and
                not re.match(r'^\d+$', value))  # Не только цифры
    
    def _is_valid_characteristic(self, char: str) -> bool:
        """Проверяет валидность характеристики"""
        if len(char) < 5 or len(char) > 80:
            return False
        
        stop_patterns = [
            r'^[0-9\s.,]+$',
            r'http',
            r'@',
            r'null', 'undefined', 'nan'
        ]
        
        return not any(re.search(pattern, char, re.IGNORECASE) for pattern in stop_patterns)

# ============================= ОПТИМИЗИРОВАННЫЙ СЕМАНТИЧЕСКИЙ АНАЛИЗАТОР =============================
class FastSemanticAnalyzer:
    def __init__(self):
        self.embedding_cache = {}
    
    def get_batch_embeddings(self, texts: List[str]) -> np.ndarray:
        """Пакетное получение эмбеддингов для ускорения"""
        if model is None or tokenizer is None:
            return np.random.randn(len(texts), 128)
        
        try:
            # Обрабатываем батчами
            all_embeddings = []
            for i in range(0, len(texts), BATCH_SIZE):
                batch_texts = texts[i:i + BATCH_SIZE]
                
                inputs = tokenizer(batch_texts, padding=True, truncation=True, 
                                 max_length=128, return_tensors="pt")
                inputs = {k: v.to(device) for k, v in inputs.items()}
                
                with torch.no_grad():
                    outputs = model(**inputs)
                
                batch_embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()
                all_embeddings.append(batch_embeddings)
            
            return np.vstack(all_embeddings)
            
        except Exception as e:
            logger.warning(f"Ошибка получения эмбеддингов: {e}")
            return np.random.randn(len(texts), 128)
    
    def fast_deduplicate(self, characteristics: List[str], similarity_threshold: float = 0.85) -> List[str]:
        """Быстрая дедупликация с использованием эмбеддингов"""
        if len(characteristics) <= 1:
            return characteristics
        
        try:
            # Получаем эмбеддинги для всех характеристик
            embeddings = self.get_batch_embeddings(characteristics)
            
            # Вычисляем попарные сходства
            similarity_matrix = cosine_similarity(embeddings)
            
            # Дедупликация
            unique_indices = []
            for i in range(len(characteristics)):
                is_duplicate = False
                for j in unique_indices:
                    if similarity_matrix[i, j] > similarity_threshold:
                        is_duplicate = True
                        break
                if not is_duplicate:
                    unique_indices.append(i)
            
            return [characteristics[i] for i in unique_indices]
        
        except Exception as e:
            logger.warning(f"Ошибка дедупликации: {e}")
            # Возвращаем уникальные по тексту
            return list(set(characteristics))

# ============================= ЗАГРУЗКА ДАННЫХ (без изменений) =============================
def load_data():
    # ... тот же код что и раньше ...
    pass

# ============================= ОБРАБОТКА КАТЕГОРИЙ (ОПТИМИЗИРОВАННАЯ) =============================
def process_categories_fast(dataframe):
    """Быстрая обработка категорий"""
    logger.info("Быстрое извлечение характеристик...")
    
    extractor = IntelligentCharacteristicsExtractor()
    semantic_analyzer = FastSemanticAnalyzer()
    
    category_characteristics = defaultdict(list)
    category_names = {}
    
    for _, row in tqdm(dataframe.iterrows(), total=len(dataframe)):
        category_id = row['id_категории']
        category_name = row['название_категории']
        text_data = row['all_text_data']
        
        category_names[category_id] = category_name
        
        # Извлекаем характеристики
        characteristics = extractor.extract_smart_characteristics(text_data)
        
        if characteristics:
            category_characteristics[category_id].extend(characteristics)
    
    return category_characteristics, category_names

# ============================= ГЕНЕРАЦИЯ ОНТОЛОГИИ (ОПТИМИЗИРОВАННАЯ) =============================
def generate_fast_ontology(category_characteristics, category_names):
    """Быстрая генерация онтологии"""
    logger.info("Быстрая генерация онтологии...")
    
    semantic_analyzer = FastSemanticAnalyzer()
    ontology = {}
    category_stats = {}
    
    for category_id, chars_list in tqdm(category_characteristics.items()):
        if len(chars_list) < MIN_SUPPORT:
            continue
        
        # Быстрая дедупликация
        unique_chars = semantic_analyzer.fast_deduplicate(chars_list)
        
        # Берем топ-K
        top_chars = unique_chars[:TOP_K]
        
        if len(top_chars) >= 2:
            category_stats[category_id] = {
                "category_name": category_names[category_id],
                "total_characteristics": len(chars_list),
                "selected_characteristics": len(top_chars)
            }
            
            ontology[category_id] = top_chars
    
    logger.info(f"Сгенерировано категорий: {len(ontology)}")
    return ontology, category_stats

# ============================= СОХРАНЕНИЕ РЕЗУЛЬТАТОВ (без изменений) =============================
def save_intelligent_results(ontology, category_stats, total_rows):
    # ... тот же код что и раньше ...
    pass

# ============================= MAIN =============================
def main():
    try:
        logger.info("🚀 ЗАПУСК ОПТИМИЗИРОВАННОГО ИЗВЛЕЧЕНИЯ ХАРАКТЕРИСТИК")
        
        # Загрузка данных
        data = load_data()
        
        # Быстрое извлечение характеристик
        category_chars, category_names = process_categories_fast(data)
        
        # Генерация онтологии
        ontology, category_stats = generate_fast_ontology(category_chars, category_names)
        
        # Сохранение результатов
        save_intelligent_results(ontology, category_stats, len(data))
        
        logger.info("✅ ОПТИМИЗИРОВАННАЯ ОНТОЛОГИЯ ХАРАКТЕРИСТИК ГОТОВА!")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        raise

if __name__ == "__main__":
    main()