# v_FINAL_HUMAN_READABLE.py
# Один запуск → идеально чистый, красивый, человекочитаемый JSON
# Никаких доменов, никаких сложностей — только золото

import json
import re
from pathlib import Path

def humanize_feature(text: str) -> str:
    # Приводим "объем_памяти_гб" → "объём памяти"
    text = text.strip().lower()
    # Убираем технические хвосты
    text = re.sub(r'_+.*$', '', text)
    text = re.sub(r'\s+_$', '', text)
    
    # Заменяем подчёркивания на пробелы
    text = text.replace('_', ' ')
    
    # Исправляем частые слова
    replacements = {
        'объем': 'объём',
        'памяти': 'памяти',
        'ядер': 'ядер',
        'процессор': 'процессор',
        'диагональ': 'диагональ экрана',
        'разрешение': 'разрешение экрана',
        'мощность': 'мощность',
        'частота': 'частота',
        'видеопамяти': 'видеопамяти',
        'импеданс': 'импеданс',
        'мл': 'мл',
        'гб': 'ГБ',
        'тб': 'ТБ',
        'вт': 'Вт',
        'dpi': 'DPI',
        'гц': 'Гц',
        'кг': 'кг',
        'см': 'см',
        'мм': 'мм',
        'листов': 'листов',
        'пачка': 'листов в пачке',
        'a4': 'A4',
        'usb': 'USB',
        'hdmi': 'HDMI',
        'ips': 'IPS',
        'oled': 'OLED',
        'smart tv': 'Smart TV',
        '4k': '4K',
        'full hd': 'Full HD'
    }
    
    for bad, good in replacements.items():
        text = re.sub(rf'\b{bad}\b', good, text)
    
    # Делаем первую букву заглавной
    text = text.strip()
    if text:
        text = text[0].upper() + text[1:]
    
    return text

def clean_category_name(name: str) -> str:
    # "Телевизор Asano Samsung Черный 55 дюймов" → "Телевизор"
    # "Ноутбук Intel Core i7 Черный" → "Ноутбук"
    common_words = [
        'черный', 'белый', 'синий', 'красный',
        'asano', 'samsung', 'lg', 'sony', 'philips',
        'intel', 'amd', 'core', 'i3', 'i5', 'i7', 'i9',
        'geforce', 'radeon', 'rtx', 'gtx',
        'apple', 'ipad', 'iphone', 'macbook',
        'lenovo', 'asus', 'acer', 'hp', 'dell',
        r'\d+[""′″]?\s*(дюйм|дюйма|дюймов)?',
        r'\d+гб|\d+gb',
        r'\d+тб|\d+tb',
    ]
    cleaned = name
    for word in common_words:
        cleaned = re.sub(rf'\s+{word}', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = cleaned.split()[0] if cleaned else name  # берём первое слово
    return cleaned.capitalize()

def main():
    input_file = "py_back/categories/auto_generated_mapping.json"
    output_file = "CATEGORIES_FINAL_BEAUTIFUL_2025.json"
    
    with open(input_file, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    
    if 'significant_features' not in raw:
        print("Нет significant_features!")
        return
    
    result = {}
    trash_indicators = [
        'вид', 'тип', 'товар', 'издели', 'принадлеж', 'окпд', 'автоматизирован',
        'фз-', 'тендер', 'закупк', 'поставк', 'канцелярск', 'офисн', 'расходн'
    ]
    
    for raw_cat, features in raw['significant_features'].items():
        clean_features = []
        seen = set()
        
        for feat in features:
            f = feat.strip()
            if not f or len(f) < 6:
                continue
            if any(trash in f.lower() for trash in trash_indicators):
                continue
            if f.lower().count('_') > 8:  # слишком длинные тендерные фразы
                continue
                
            nice_feat = humanize_feature(f)
            key = nice_feat.lower()
            if key not in seen and len(clean_features) < 10:
                seen.add(key)
                clean_features.append(nice_feat)
        
        if clean_features:
            nice_cat = clean_category_name(raw_cat)
            # Избегаем дублей категорий
            if nice_cat not in result or len(clean_features) > len(result[nice_cat]):
                result[nice_cat] = clean_features
    
    # Сортируем по алфавиту
    result = dict(sorted(result.items()))
    
    final = {
        "metadata": {
            "name": "Чистая онтология товаров (1M+ позиций)",
            "version": "FINAL_BEAUTIFUL_2025",
            "total_categories": len(result),
            "generated_by": "Grok + human supervision",
            "note": "Готово к использованию в RAG, классификаторах, промптах"
        },
        "categories": result
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    
    print(f"ГОТОВО! Создано {len(result)} чистых категорий")
    print(f"Файл: {output_file}")
    print("\nПримеры:")
    for cat, feats in list(result.items())[:10]:
        print(f"  • {cat}: {', '.join(feats[:3])}{'...' if len(feats)>3 else ''}")

if __name__ == "__main__":
    main()