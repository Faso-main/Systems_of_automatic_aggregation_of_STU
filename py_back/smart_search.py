import json, re, os
from typing import List, Dict, Optional, Set, Any
from collections import defaultdict
import Levenshtein

def path_making(hashmap: list) -> str:  return os.path.join(*hashmap)

class SmartSearchAI:
    def __init__(self, tree_data: Dict[str, Any]):
        self.tree_data = tree_data
        self.all_categories = self._flatten_categories()
        self._build_enhanced_indices()
         
    def _flatten_categories(self) -> Dict[int, Dict]:
        categories = {}
        
        def process_category(cat, path=None):
            if path is None:
                path = []
                
            current_path = path + [cat["name"]]
            categories[cat["id"]] = {
                "id": cat["id"],
                "name": cat["name"],
                "level": cat["level"],
                "path": current_path,
                "full_path": " → ".join(current_path),
                "search_text": f"{cat['name']} {' '.join(current_path)}".lower()
            }
            
            if "children" in cat:
                for child in cat["children"]:
                    process_category(child, current_path)
        
        for category in self.tree_data["categories"]:
            process_category(category)
            
        return categories
    
    def _build_enhanced_indices(self):
        self.token_index = defaultdict(set)
        self.prefix_index = defaultdict(set)
        self.synonym_groups = self._build_synonym_groups()
        
        for cat_id, cat_info in self.all_categories.items():
            text = cat_info["search_text"]
            
            # Индекс по токенам
            tokens = set(re.findall(r'\w+', text))
            for token in tokens:
                self.token_index[token].add(cat_id)
            
            # Индекс по префиксам (для автодополнения)
            for token in tokens:
                for i in range(2, len(token) + 1):
                    self.prefix_index[token[:i]].add(cat_id)
    
    def _build_synonym_groups(self):
        return {
            "mobile": {"смартфон", "телефон", "мобильный", "мобильник", "андроид", "айфон", "iphone", "смартфоны", "телефоны"},
            "tv": {"телевизор", "тв", "телек", "телевизоры", "smart tv"},
            "laptop": {"ноутбук", "лэптоп", "ноут"},
            "tablet": {"планшет", "таблет", "планшетник", "ipad"},
            "fridge": {"холодильник", "рефрижератор", "холодильники"},
            "washer": {"стиральная", "стиралка", "автомат", "машинка", "стиральные"},
            "watch": {"часы", "часики", "браслет", "смарт-часы"},
            "smart": {"умные", "смарт", "smart", "интеллектуальные"},
            "large": {"большие", "крупные", "большой", "огромные"}
        }
    
    def _get_synonyms(self, word):
        for group in self.synonym_groups.values():
            if word in group:
                return group
        return {word}
    
    def pattern_based_search(self, query: str) -> List[Dict]:
        query_lower = query.lower()
        results = []
        
        # Паттерны для распознавания intent
        patterns = {
            r'.*смартфон.*': ['смартфон', 'телефон', 'мобильный'],
            r'.*телефон.*': ['смартфон', 'телефон'],
            r'.*часики.*': ['часы', 'умные часы'],
            r'.*стиралк.*': ['стиральная', 'стиральные'],
            r'.*холодильник.*': ['холодильник'],
            r'.*больш.*': ['большие', 'крупные']
        }
        
        # Определяем intent по паттернам
        search_tokens = set()
        for pattern, tokens in patterns.items():
            if re.match(pattern, query_lower):
                search_tokens.update(tokens)
        
        # Если не нашли паттерны, используем токены запроса
        if not search_tokens:
            search_tokens = set(re.findall(r'\w+', query_lower))
        
        # Расширяем синонимами
        expanded_tokens = set()
        for token in search_tokens:
            expanded_tokens.update(self._get_synonyms(token))
        
        # Ищем совпадения
        for cat_id, cat_info in self.all_categories.items():
            score = 0.0
            matched_terms = []
            
            for token in expanded_tokens:
                if token in cat_info["search_text"]:
                    score += 1.0
                    matched_terms.append(token)
            
            if score > 0:
                # Бонусы за разные факторы
                if cat_info["level"] == 3:  # Конечные категории
                    score += 0.5
                
                # Бонус за точное совпадение названия
                if any(token in cat_info["name"].lower() for token in expanded_tokens):
                    score += 0.3
                
                results.append({
                    **cat_info,
                    "score": score,
                    "matched_terms": matched_terms,
                    "match_type": "pattern"
                })
        
        return sorted(results, key=lambda x: x["score"], reverse=True)
    
    def phonetic_search(self, query: str) -> List[Dict]:
        query_lower = query.lower()
        results = []
        
        # Русская фонетическая транскрипция
        phonetic_map = {
            'а': 'а', 'б': 'п', 'в': 'ф', 'г': 'к', 'д': 'т',
            'е': 'и', 'ё': 'и', 'ж': 'ш', 'з': 'с', 'и': 'и',
            'й': 'и', 'к': 'к', 'л': 'л', 'м': 'м', 'н': 'н',
            'о': 'а', 'п': 'п', 'р': 'р', 'с': 'с', 'т': 'т',
            'у': 'у', 'ф': 'ф', 'х': 'х', 'ц': 'ц', 'ч': 'ч',
            'ш': 'ш', 'щ': 'щ', 'ъ': '', 'ы': 'и', 'ь': '',
            'э': 'и', 'ю': 'у', 'я': 'а'
        }
        
        def phonetic_transform(text):
            result = []
            for char in text:
                if char in phonetic_map:
                    result.append(phonetic_map[char])
            return ''.join(result)
        
        query_phonetic = phonetic_transform(query_lower)
        
        for cat_id, cat_info in self.all_categories.items():
            name_phonetic = phonetic_transform(cat_info["name"].lower())
            path_phonetic = phonetic_transform(cat_info["search_text"])
            
            # Сравниваем фонетические представления
            name_similarity = Levenshtein.ratio(query_phonetic, name_phonetic)
            path_similarity = Levenshtein.ratio(query_phonetic, path_phonetic)
            
            similarity = max(name_similarity, path_similarity)
            
            if similarity > 0.6:
                results.append({
                    **cat_info,
                    "score": similarity,
                    "match_type": "phonetic"
                })
        
        return sorted(results, key=lambda x: x["score"], reverse=True)
    
    def context_aware_search(self, query: str) -> List[Dict]:
        query_lower = query.lower()
        
        # Семантические кластеры запросов
        semantic_clusters = {
            'electronics': ['смартфон', 'телефон', 'планшет', 'ноутбук', 'телевизор', 'часы'],
            'appliances': ['стиральная', 'холодильник', 'посудомойка', 'плита'],
            'home': ['мебель', 'лампа', 'диван', 'кровать']
        }
        
        # Определяем кластер запроса
        query_cluster = None
        for cluster, keywords in semantic_clusters.items():
            if any(keyword in query_lower for keyword in keywords):
                query_cluster = cluster
                break
        
        # Получаем базовые результаты
        base_results = self.pattern_based_search(query)
        
        if query_cluster:
            # Увеличиваем вес результатов из того же кластера
            for result in base_results:
                result_text = result["search_text"]
                for keyword in semantic_clusters[query_cluster]:
                    if keyword in result_text:
                        result["score"] += 0.5
                        break
        
        return sorted(base_results, key=lambda x: x["score"], reverse=True)
    
    def multi_stage_search(self, query: str) -> List[Dict]:

        # Этап 1: Точный поиск по паттернам
        stage1_results = self.pattern_based_search(query)
        if stage1_results and stage1_results[0]["score"] > 2.0:
            return stage1_results[:10]
        
        # Этап 2: Контекстный поиск
        stage2_results = self.context_aware_search(query)
        if stage2_results and stage2_results[0]["score"] > 1.5:
            return stage2_results[:10]
        
        # Этап 3: Фонетический поиск для опечаток
        stage3_results = self.phonetic_search(query)
        if stage3_results:
            return stage3_results[:10]
        
        # Этап 4: Комбинируем все методы
        all_results = stage1_results + stage2_results + stage3_results
        
        # Объединяем и убираем дубликаты
        seen_ids = set()
        final_results = []
        
        for result in all_results:
            if result["id"] not in seen_ids:
                seen_ids.add(result["id"])
                final_results.append(result)
        
        return sorted(final_results, key=lambda x: x["score"], reverse=True)[:10]
    
    def intelligent_suggestions(self, partial_query: str) -> List[Dict]:
        if len(partial_query.strip()) < 2:
            return []
        
        partial_lower = partial_query.lower()
        suggestions = []
        
        # Ищем в префиксном индексе
        matching_categories = set()
        for prefix, category_ids in self.prefix_index.items():
            if prefix.startswith(partial_lower) or partial_lower.startswith(prefix):
                matching_categories.update(category_ids)
        
        # Создаем предложения
        for cat_id in list(matching_categories)[:20]:
            cat_info = self.all_categories[cat_id]
            
            # Вычисляем релевантность
            relevance = 0.0
            if cat_info["name"].lower().startswith(partial_lower):
                relevance += 1.0
            if any(token.startswith(partial_lower) for token in cat_info["search_text"].split()):
                relevance += 0.5
            
            if relevance > 0:
                suggestions.append({
                    **cat_info,
                    "relevance": relevance
                })
        
        return sorted(suggestions, key=lambda x: x["relevance"], reverse=True)[:6]

def demo_ai_search():
    try:
        with open(path_making(['py_back','result_tree_gen.json']), 'r', encoding='utf-8') as f:
            tree_data = json.load(f)
    except FileNotFoundError:
        print("Файл не найден")
        return
    except json.JSONDecodeError:
        print("Ошибка чтения JSON")
        return
    
    ai_search = SmartSearchAI(tree_data)
        
    test_queries = [
        "смартфоны",
        "смартфон", 
        "телефоны",
        "smarthpone",
        "умные часики",
        "стиралка",
        "холодильники большие"
    ]
    
    for query in test_queries:
        print(f"\nЗапрос: '{query}'")
        
        try:
            results = ai_search.multi_stage_search(query)
            
            if results:
                for i, result in enumerate(results[:3], 1):
                    print(f"{i}. {result['name']} (уровень {result['level']})")
                    print(f"   Путь: {result['full_path']}")
                    print(f"   Счет: {result['score']:.3f} [{result['match_type']}]")
                    if 'matched_terms' in result:
                        print(f"   Термины: {', '.join(result['matched_terms'][:3])}")
                    print()
            else:
                print("Нет результатов")
                
        except Exception as e:
            print(f"Ошибка при поиске: {e}")
    
    test_partials = ["смарт", "тел", "стир", "холод"]
    for partial in test_partials:
        print(f"\nПодсказки для '{partial}':")
        suggestions = ai_search.intelligent_suggestions(partial)
        if suggestions:
            for i, suggestion in enumerate(suggestions[:3], 1):
                print(f"   {i}. {suggestion['name']} (релевантность: {suggestion['relevance']:.3f})")
        else:
            print("Нет подсказок")

if __name__ == "__main__":
    demo_ai_search()