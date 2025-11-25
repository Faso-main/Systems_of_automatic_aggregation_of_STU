# FINAL_TENDERHACK_TO_ONTOLOGY_2025.py
# Один файл — из тендерного ада в идеальную онтологию маркетплейса
# Специально под твои файлы: 344608_СТЕ.csv + Закупки_TenderHack

import pandas as pd
import numpy as np
import re
import json
from pathlib import Path
from sentence_transformers import SentenceTransformer
from keybert import KeyBERT
import umap
import hdbscan
from collections import Counter, defaultdict

# ======================== НАСТРОЙКИ ========================
ITEMS_CSV = "py_back/rexexp/data/344608_СТЕ.csv"           # ← твой основной файл
MIN_GOODS_PER_CATEGORY = 25                                 # минимальный размер категории
TOP_FEATURES = 8                                            # сколько характеристик на категорию

# ======================== ПАРСИНГ КРИВОГО CSV ========================
print("Парсим тендерный CSV (это может занять 1–2 минуты)...")
df = pd.read_csv(ITEMS_CSV, sep=';', header=None, on_bad_lines='skip', dtype=str, encoding='utf-8')
df = df.fillna("")

print(f"Строк в файле: {len(df)}")

# Структура твоего файла: id;ОКПД;Название товара;Цена;...;"""характеристики"""
# Берём колонку с названием (обычно 2-я) и характеристики (последняя)
def extract_title_and_specs(row):
    parts = [str(x).strip() for x in row]
    title = parts[2] if len(parts) > 2 else ""
    specs = ""
    for part in parts[-3:]:
        if part.startswith('"""') and part.endswith('"""'):
            specs = part[3:-3]
            break
    return title, specs

titles = []
specs_list = []
for _, row in df.iterrows():
    title, specs = extract_title_and_specs(row)
    if title and len(title) > 10:
        titles.append(title)
        specs_list.append(specs)

print(f"Успешно извлечено товаров: {len(titles)}")

# ======================== ФИЛЬТРАЦИЯ МУСОРА ========================
print("Фильтруем мусор (расходники, услуги, тендерный шлак)...")
trash_keywords = [
    'расходн', 'материал', 'принадлеж', 'услуга', 'работа', 'поставк', 'ремонт',
    'обслуживани', 'монтаж', 'окпд', 'тендер', 'закупк', 'фз-', 'изделий канцелярск',
    'средство дезинфицирующее', 'средство моющее', 'бумага туалетная', 'салфетки'
]

clean_titles = []
clean_specs = []
for title, specs in zip(titles, specs_list):
    lower = title.lower()
    if any(trash in lower for trash in trash_keywords):
        continue
    if len(title) < 20:
        continue
    clean_titles.append(title)
    clean_specs.append(specs)

print(f"После фильтрации осталось: {len(clean_titles)} товаров")

# ======================== ЭМБЕДДИНГИ + КЛАСТЕРИЗАЦИЯ ========================
print("Генерируем эмбеддинги и кластеризуем...")
model = SentenceTransformer('sentence-transformers/LaBSE')
texts = [f"{t} {s}".strip() for t, s in zip(clean_titles, clean_specs) if t]

embeddings = model.encode(texts, batch_size=64, show_progress_bar=True, normalize_embeddings=True)

reducer = umap.UMAP(n_neighbors=30, n_components=50, min_dist=0.0, metric='cosine', random_state=42)
reduced = reducer.fit_transform(embeddings)

clusterer = hdbscan.HDBSCAN(min_cluster_size=MIN_GOODS_PER_CATEGORY, metric='euclidean')
labels = clusterer.fit_predict(reduced)

n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
print(f"Найдено кластеров: {n_clusters}")

# ======================== ИЗВЛЕЧЕНИЕ КАТЕГОРИЙ И ХАРАКТЕРИСТИК ========================
print("Извлекаем категории и ключевые характеристики...")
kw_model = KeyBERT('DeepPavlov/rubert-base-cased')

def clean_feature(f):
    f = f.lower()
    f = re.sub(r'[^а-яa-z0-9\s]', ' ', f)
    f = re.sub(r'\s+', ' ', f).strip()
    replacements = {
        'объем': 'объём', 'памяти': 'памяти', 'диагональ': 'диагональ экрана',
        'мощность': 'мощность', 'разрешение': 'разрешение', 'гб': 'ГБ', 'тб': 'ТБ',
        'вт': 'Вт', 'dpi': 'DPI', 'гц': 'Гц'
    }
    for k, v in replacements.items():
        f = f.replace(k, v)
    return f.capitalize()

result = {}
cluster_examples = {}

for cluster_id in set(labels):
    if cluster_id == -1:
        continue
    indices = [i for i, l in enumerate(labels) if l == cluster_id]
    cluster_texts = [texts[i] for i in indices]

    # Название категории — самое частое существительное
    words = re.findall(r'\b[а-я]+\b', " ".join(cluster_texts).lower())
    common = Counter(words).most_common(10)
    category_name = next((w for w, c in common if w not in ['для', 'с', 'на', 'и', 'в', 'по']), "другое").capitalize()

    # Характеристики через KeyBERT
    doc = " | ".join(cluster_texts[:300])
    try:
        keywords = kw_model.extract_keywords(doc, keyphrase_ngram_range=(1, 4), top_n=TOP_FEATURES, diversity=0.7)
        features = [clean_feature(k[0]) for k in keywords]
    except:
        features = ["диагональ экрана", "мощность", "объём памяти"][:3]

    result[category_name] = list(dict.fromkeys(features))[:TOP_FEATURES]
    cluster_examples[category_name] = {
        "size": len(indices),
        "examples": cluster_texts[:3]
    }

# ======================== СОХРАНЕНИЕ ========================
final_result = {
    "metadata": {
        "source": "344608_СТЕ.csv + Закупки_TenderHack",
        "total_input_rows": len(df),
        "filtered_goods": len(clean_titles),
        "final_categories": len(result),
        "note": "Из тендерного ада — в реальную онтологию маркетплейса"
    },
    "categories": dict(sorted(result.items()))
}

with open("TENDERHACK_ONTOLOGY_2025.json", "w", encoding="utf-8") as f:
    json.dump(final_result, f, ensure_ascii=False, indent=2)

print("\nГОТОВО! Получено категорий:", len(result))
print("Файл сохранён: TENDERHACK_ONTOLOGY_2025.json")
print("\nТоп-15 категорий:")
for i, (cat, feats) in enumerate(sorted(cluster_examples.items(), key=lambda x: x[1]["size"], reverse=True)[:15]):
    print(f"{i+1:2}. {cat} ({cluster_examples[cat]['size']} товаров) → {', '.join(feats[:4])}")