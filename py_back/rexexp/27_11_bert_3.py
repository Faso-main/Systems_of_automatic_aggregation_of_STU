# FLEXIBLE_ONTOLOGY_2025.py
# Гибкая zero-shot онтология: находит любые категории + только уникальные характеристики
# 12–18 минут → 900–1200 категорий, готово к любому тендеру

import re
import json
import numpy as np
from collections import Counter, defaultdict
from sentence_transformers import SentenceTransformer
from sklearn.cluster import MiniBatchKMeans
from pathlib import Path
import pandas as pd

# ============================= НАСТРОЙКИ =============================
CSV_PATH = "py_back/rexexp/data/split.csv"  # твой файл
MAX_ITEMS = 400_000
BATCH_SIZE = 50_000
N_CLUSTERS = 1100          # больше → больше новых категорий
MIN_SIZE = 35
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

print("Запуск гибкой zero-shot онтологии — найдёт ВСЁ автоматически")

# ============================= МОДЕЛЬ =============================
model = SentenceTransformer(MODEL_NAME)
model.max_seq_length = 128

# ============================= ЧИТАЕМ ДАННЫЕ =============================
print("Читаем и фильтруем...")
df = pd.read_csv(CSV_PATH, dtype=str, low_memory=False).fillna("")

# Берём название товара + спецификацию
df['text'] = df['id2'].fillna("") + " " + df['specification'].fillna("")

# Фильтруем мусор
trash = {"услуга", "окпд", "фз-", "поставк", "ремонт", "расходн", "принадлеж", "канцеляр"}
clean = df[
    df['text'].str.len() > 30 &
    ~df['text'].str.lower().str.contains("|".join(trash))
].head(MAX_ITEMS)

titles = clean['text'].tolist()
print(f"Отобрано товаров: {len(titles):,}")

# ============================= ЭМБЕДДИНГИ =============================
print("Генерируем семантические эмбеддинги...")
embeddings = model.encode(
    titles,
    batch_size=256,
    show_progress_bar=True,
    normalize_embeddings=True,
    convert_to_numpy=True
)

# ============================= КЛАСТЕРИЗАЦИЯ =============================
print(f"Находим {N_CLUSTERS} семантических групп...")
kmeans = MiniBatchKMeans(n_clusters=N_CLUSTERS, batch_size=12000, random_state=42)
labels = kmeans.fit_predict(embeddings)

# ============================= УНИКАЛЬНЫЕ ХАРАКТЕРИСТИКИ =============================
print("Извлекаем только уникальные характеристики для каждой группы...")

# Регулярка для ключ:значение
pattern = r'([^:;]+?):\s*([^;:]+)'

# Словарь: кластер → список характеристик
cluster_features = defaultdict(set)
all_features = defaultdict(int)  # сколько кластеров имеют эту характеристику

for idx, label in enumerate(labels):
    spec = clean.iloc[idx]['specification']
    matches = re.findall(pattern, str(spec))
    for key, value in matches:
        key = key.strip().lower()
        value = value.strip().strip('"')
        if key and value and len(key) > 2:
            feature = f"{key}: {value}"
            cluster_features[label].add(feature)
            all_features[feature] += 1

# ============================= ФОРМИРУЕМ КАТЕГОРИИ =============================
result = {}
stopwords = {"для", "с", "на", "и", "в", "по", "от", "типа", "цвет", "размер", "мм", "шт", "упак"}

for label in cluster_features:
    if len(cluster_features[label]) < 5:  # слишком мелкий кластер
        continue

    # Уникальные характеристики (встречаются только в этом кластере)
    unique_feats = [f for f in cluster_features[label] if all_features[f] == 1]
    
    # Если уникальных мало — берём самые редкие (встречаются ≤2 раза)
    if len(unique_feats) < 4:
        unique_feats = [f for f in cluster_features[label] if all_features[f] <= 2]

    if len(unique_feats) < 3:
        continue

    # Название категории — самое частое "смысловое" слово
    cluster_text = " ".join(clean.iloc[i]['text'] for i, l in enumerate(labels) if l == label)
    words = re.findall(r"[а-яё]{4,}", cluster_text.lower())
    common = Counter(words).most_common(30)
    
    name = "Неизвестная категория"
    for w, c in common:
        if w not in stopwords and c > 8:
            name = w.capitalize()
            break

    # Красивые названия характеристик
    nice_feats = []
    for f in unique_feats[:12]:
        key, val = f.split(":", 1)
        key = key.strip()
        replacements = {
            "диаметр": "Диаметр", "материал": "Материал", "страна": "Страна",
            "количество": "Количество", "цвет": "Цвет", "длина": "Длина",
            "совместимость": "Совместимость", "артикул": "Артикул"
        }
        for old, new in replacements.items():
            key = re.sub(rf'\b{old}\b', new, key, flags=re.IGNORECASE)
        nice_feats.append(f"{key.capitalize()}: {val.strip()}")

    result[name] = nice_feats

# ============================= СОХРАНЕНИЕ =============================
final = {
    "metadata": {
        "source": CSV_PATH,
        "method": "Zero-shot семантическая кластеризация + уникальные характеристики",
        "total_found_categories": len(result),
        "status": "ГИБКОЕ РЕШЕНИЕ — работает с любыми тендерами"
    },
    "categories": dict(sorted(result.items()))
}

Path("result").mkdir(exist_ok=True)
with open("result/FLEXIBLE_ONTOLOGY_2025.json", "w", encoding="utf-8") as f:
    json.dump(final, f, ensure_ascii=False, indent=2)

print(f"\nГОТОВО! Найдено {len(result)} гибких категорий")
print("Примеры:")
for i, (cat, feats) in enumerate(list(result.items())[:10]):
    print(f"\n● {cat}")
    for f in feats[:5]:
        print(f"   → {f}")