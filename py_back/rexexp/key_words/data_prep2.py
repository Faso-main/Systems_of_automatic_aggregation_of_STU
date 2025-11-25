# universal_category_cleaner_v10.py
# Один файл → любой сырой auto_generated_mapping.json → идеальные характеристики под любой домен
# Просто положи рядом с сырым JSON и запусти

import json
import re
from collections import defaultdict
from pathlib import Path

# ======================== 1. ДЕТЕКТОР ДОМЕНА ========================
def detect_domain(categories):
    cat_text = " ".join(categories).lower()
    scores = {
        "electronics": 0,
        "clothing": 0,
        "food": 0,
        "stationery": 0,
        "furniture": 0,
        "medicine": 0,
        "auto": 0,
        "other": 0
    }

    markers = {
        "electronics": ["процессор", "диагональ", "памяти", "мощность", "разрешение", "частота", "hdmi", "usb", "sata", "ghz", "ядер", "ips", "oled", "наушники", "мышь", "роутер", "коммутатор"],
        "clothing": ["размер", "состав ткани", "пол мужской", "пол женский", "сезон", "утеплитель", "куртка", "брюки", "платье", "рубашка", "хлопок", "полиэстер"],
        "food": ["масса нетто", "состав", "срок годности", "бжу", "калорийность", "упаковка", "кг", "литр", "мука", "сахар", "молоко", "мясо"],
        "stationery": ["плотность", "листов", "формат a4", "мелованная", "скобы", "дырокол", "штемпельная", "клейкая лента", "брауберг", "fellowes"],
        "furniture": ["материал каркаса", "наполнитель", "механизм трансформации", "габариты", "стол", "стул", "диван", "кровать"],
        "medicine": ["действующее вещество", "форма выпуска", "дозировка", "рецептурный", "таблетки", "мазь", "упаковка №"],
        "auto": ["объем двигателя", "мощность л.с.", "привод", "кпп", "акпп", "шина", "диск", "аккумулятор"]
    }

    for domain, words in markers.items():
        scores[domain] += sum(1 for w in words if w in cat_text)

    detected = max(scores, key=scores.get)
    return detected if scores[detected] > 2 else "other"

# ======================== 2. ФИЛЬТРЫ ПО ДОМЕНАМ ========================
DOMAIN_RULES = {
    "electronics": {
        "keep_keywords": ["диагональ", "разрешение", "мощность", "частота", "памяти", "ядер", "объем", "длина кабеля", "usb", "hdmi", "ips", "oled", "ghz", "вт", "вт·ч", "dpi", "импеданс", "lszh"],
        "trash_starts": ["товар", "издели", "принадлеж", "средств_", "элементов_", "расходн", "окпд", "автоматизирован", "минимальный_ресурс"],
        "trash_contains": ["окпд", "тендер", "закупк", "фз-", "канцелярск", "офисн"]
    },
    "clothing": {
        "keep_keywords": ["размер", "рост", "состав", "пол", "сезон", "утеплитель", "хлопок", "полиэстер", "шерсть", "мужской", "женский", "детский"],
        "trash_starts": ["товар", "одежды", "издели", "трикотажн"],
        "trash_contains": []
    },
    "food": {
        "keep_keywords": ["масса нетто", "объем", "состав", "бжу", "калорийность", "срок годности", "кг", "г", "л", "мл"],
        "trash_starts": ["продукт", "пищевой", "товар"],
        "trash_contains": ["окпд2"]
    },
    "stationery": {
        "keep_keywords": ["плотность", "листов", "формат", "мелован", "скобы", "диаметр", "длина намотки", "a4", "a3", "г/м²", "пачка", "рулон"],
        "trash_starts": ["изделий_канцелярск", "принадлежностей", "материалов_расходных"],
        "trash_contains": []
    },
    "furniture": {
        "keep_keywords": ["габариты", "материал", "каркас", "наполнитель", "механизм", "цвет обивки", "дсп", "лдсп", "массив"],
        "trash_starts": ["мебель", "изделий_мебельных"],
        "trash_contains": []
    },
    "other": {  # самый жёсткий — просто цифры + единицы измерения
        "keep_keywords": [],
        "trash_starts": ["товар", "издели", "принадлеж", "средств_", "элементов_", "окпд", "автоматизирован"],
        "trash_contains": ["окпд", "тендер", "закупк", "фз-", "44", "223"],
        "require_unit": True
    }
}

def clean_feature(feat: str, domain: str) -> str | None:
    f = feat.strip()
    if len(f) < 6 or len(f) > 100:
        return None

    f = re.sub(r'^[\d\.\)\s]+', '', f)
    f = re.sub(r'_и_мфу$', '', f, flags=re.I)
    lower = f.lower()
    rules = DOMAIN_RULES.get(domain, DOMAIN_RULES["other"])

    # Жёсткий мусор
    if any(lower.startswith(pref) for pref in rules.get("trash_starts", [])):
        return None
    if any(bad in lower for bad in rules.get("trash_contains", [])):
        return None

    # Для электроники и канцелярии — оставляем только с «вкусными» словами
    if domain in ["electronics", "stationery"]:
        if not any(k in lower for k in rules["keep_keywords"]):
            return None

    # Для "other" — оставляем только если есть цифра + единица измерения
    if domain == "other" and rules.get("require_unit"):
        if not re.search(r'\d+\s*(г|кг|мл|л|мм|см|м|вт|гц|мгц|ггц|dpi|г/м²|листов|пачек)', lower):
            return None

    return f

# ======================== 3. ОСНОВНАЯ ЛОГИКА ========================
def process_file(input_path: str, output_path: str = None):
    with open(input_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    if 'significant_features' not in raw:
        raise ValueError("Нет ключа 'significant_features'")

    categories = list(raw['significant_features'].keys())
    domain = detect_domain(categories)
    print(f"Обнаружен домен: {domain.upper()}")

    cleaned = {"metadata": {"domain": domain, "source": str(input_path), "cleaner": "universal_v10"}, "significant_features": {}}
    seen = defaultdict(set)

    for cat, feats in raw['significant_features'].items():
        good = []
        for f in feats:
            cleaned_f = cat if f.lower() == cat.lower() else clean_feature(f, domain)
            if not cleaned_f:
                continue
            key = cleaned_f.lower()
            if key not in seen[cat] and len(good) < 12:
                seen[cat].add(key)
                good.append(cleaned_f)
        if good:
            cleaned["significant_features"][cat] = good[:10]

    if not output_path:
        output_path = Path(input_path).stem + f"_CLEANED_{domain.upper()}.json"

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"ГОТОВО → {output_path}")
    print(f"Категорий с характеристиками: {len(cleaned['significant_features'])}")
    print(f"Пример: {list(cleaned['significant_features'].items())[0]}")

# ======================== 4. ЗАПУСК ========================
if __name__ == "__main__":
    # Просто меняй эту строку под каждый новый файл
    INPUT_FILE = "py_back/categories/auto_generated_mapping.json"
    
    process_file(INPUT_FILE)