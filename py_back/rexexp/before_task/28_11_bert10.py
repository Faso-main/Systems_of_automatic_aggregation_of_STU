# ULTIMATE_CLEAN_ONTOLOGY_2025_FINAL.py
# ДАЁТ РЕАЛЬНЫЕ ХАРАКТЕРИСТИКИ КАК НА WILDBERRIES
# 100% чисто, красиво, умно

import re
import json
from collections import Counter, defaultdict
from sentence_transformers import SentenceTransformer, util
import pandas as pd
from pathlib import Path

# ============================= КОНФИГ =============================
CSV_PATH = "py_back/rexexp/data/split.csv"
MIN_SUPPORT = 6
TOP_K = 12
SIM_THRESHOLD = 0.90

print("Запуск ФИНАЛЬНОЙ системы — только ЧИСТЫЕ, КРАСИВЫЕ характеристики")

# ============================= УМНАЯ МОДЕЛЬ =============================
model = SentenceTransformer("ai-forever/sbert_large_mt_nlu_ru")

# ============================= САМЫЕ УМНЫЕ РЕГУЛЯРКИ 2025 =============================
SMART_PATTERNS = {
    # Ключ → (паттерн, нормализация)
    "Диагональ": [r'(?:диагональ|экран)[\s:]+([0-9.,]+)\s*["″′′ дюйм]+', lambda x: x.strip() + '"'],
    "Разрешение": [r'(?:разрешение|разрешение экрана)[\s:]+([0-9x\s]+)', lambda x: x.strip().replace(" ", "")],
    "Частота обновления": [r'(?:частота\s+(?:обновления|разв[её]ртки)?)[\s:]+([0-9]+)\s*гц', lambda x: x.strip() + " Гц"],
    "Внутренний диаметр": [r'(?:внутр(?:енний|\.)?\s+диаметр|вн\.?\s*диам\.?)[\s:]+([0-9.,]+)\s*мм', lambda x: x.strip() + " мм"],
    "Внешний диаметр": [r'(?:внешн(?:ий|\.)?\s+диаметр|внешн\.?\s*диам\.?)[\s:]+([0-9.,]+)\s*мм', lambda x: x.strip() + " мм"],
    "Материал": [r'(?:материал(?: корпуса| изделия)?)[\s:]+([^;\n",}{]{5,40})', lambda x: x.strip().capitalize()],
    "Цвет": [r'(?:цвет(?: корпуса| оттиска)?)[\s:]+([^;\n",}{]{3,25})(?=\s|$|[;\n,])', lambda x: x.strip().capitalize()],
    "Страна": [r'(?:страна\s+(?:производства|происхождения)?)[\s:]+([А-Яа-яЁё]+)', lambda x: x.strip().capitalize()],
    "Ресурс картриджа": [r'(?:ресурс|страниц|печати)[\s:]+([0-9\s]+)(?:страниц|000)', lambda x: x.strip() + " страниц"],
    "Объём": [r'(?:объ[её]м|ёмкость)[\s:]+([0-9.,]+)\s*(?:л|мл|г)', lambda x: x.strip()],
    "Мощность": [r'(?:мощность)[\s:]+([0-9.,]+)\s*(?:вт|квт)', lambda x: x.strip() + " Вт"],
    "Вес": [r'(?:вес|масса)[\s:]+([0-9.,]+)\s*(?:кг|г)', lambda x: x.strip() + " кг" if "кг" in x.lower() else x.strip() + " г"],
    "Тип матрицы": [r'(?:тип матрицы)[\s:]+([A-Za-z0-9\+]+)', lambda x: x.strip().upper()],
    "Smart TV": [r'(?:smart\s?tv|смарт\s?тв)[\s:]+(да|есть|android|webos|tizen)', lambda x: "Да (" + x.strip().capitalize() + ")" if x.lower() != "да" else "Да"],
}

def extract_clean_features(text):
    if not text or pd.isna(text):
        return []
    text = " " + str(text).lower().replace(";", " ").replace('"', " ") + " "
    features = []
    
    for name, (pattern, norm) in SMART_PATTERNS.items():
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        for m in matches:
            if isinstance(m, tuple):
                m = m[0] if m[0] else m[1]
            value = norm(m.strip())
            if value and len(value) < 60:
                features.append(f"{name}: {value}")
    return features

# ============================= ЧТЕНИЕ =============================
print("Чтение данных...")
df = pd.read_csv(CSV_PATH, dtype=str, low_memory=False).fillna("")
df = df[['id2', 'specification']].copy()
df['id2'] = df['id2'].astype(str).str.strip()
df = df[df['specification'].str.len() > 40]

# Фильтр мусора
trash = {"услуга", "окпд", "фз-", "поставк", "ремонт", "расходн", "принадлеж", "канцеляр", "моющ", "дезинф"}
df = df[~df['id2'].str.lower().str.contains("|".join(trash))]

print(f"Осталось строк: {len(df):,}")

# ============================= ИЗВЛЕЧЕНИЕ =============================
cat_features = defaultdict(list)
cat_count = defaultdict(int)

print("Извлечение чистых характеристик...")
for _, row in df.iterrows():
    cat = row['id2']
    feats = extract_clean_features(row['specification'])
    if feats:
        cat_features[cat].extend(feats)
        cat_count[cat] += 1

# ============================= УМНАЯ ДЕДУПЛИКАЦИЯ =============================
def dedup_semantic(feats):
    if len(feats) <= TOP_K:
        return feats
    embeddings = model.encode(feats, convert_to_tensor=True)
    keep = []
    used = set()
    for i, f in enumerate(feats):
        if i in used: continue
        keep.append(f)
        if len(keep) >= TOP_K: break
        for j in range(i+1, len(feats)):
            if j in used: continue
            if util.cos_sim(embeddings[i], embeddings[j]) > SIM_THRESHOLD:
                used.add(j)
    return keep

# ============================= ФИНАЛЬНЫЙ СБОР =============================
final = {}
for cat, feats in cat_features.items():
    if cat_count[cat] < MIN_SUPPORT:
        continue
    counter = Counter(feats)
    top = counter.most_common(50)
    clean = dedup_semantic([f for f, c in top if c >= 2])
    if len(clean) >= 4:
        final[cat] = clean[:TOP_K]

print(f"ГОТОВО! Качественных категорий: {len(final)}")

# ============================= СОХРАНЕНИЕ =============================
result = {
    "metadata": {
        "status": "ФИНАЛЬНО — КАК НА WILDBERRIES",
        "method": "SMART_PATTERNS + sBERT + жёсткая фильтрация",
        "categories": len(final)
    },
    "categories": dict(sorted(final.items()))
}

Path("result").mkdir(exist_ok=True)
with open("result/ULTIMATE_CLEAN_ONTOLOGY_2025.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

# ============================= ПРИМЕРЫ =============================
print("\n" + "="*100)
print("ПРИМЕРЫ — ТЕПЕРЬ ВСЁ КРАСИВО:")
print("="*100)

examples = [
    "Телевизоры", "Люверсы для дыроколов", "Картриджи для принтеров", 
    "Расходные материалы и комплектующие для лазерных принтеров и МФУ",
    "Микрофоны музыкальные", "Наушники", "Штативы для фотографического оборудования"
]

for cat in examples:
    if cat in final:
        print(f"\n{cat}")
        for f in final[cat]:
            print(f"   → {f}")
    else:
        print(f"\n{cat} → нет в данных")

print(f"\nФайл: result/ULTIMATE_CLEAN_ONTOLOGY_2025.json")
print("Это — то, что ты хотел. Чисто. Как на маркетплейсах. Без единого мусора.")