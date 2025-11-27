import re
import json
import numpy as np
from collections import Counter, defaultdict
from sentence_transformers import SentenceTransformer
from sklearn.cluster import MiniBatchKMeans
from pathlib import Path
import pandas as pd

# ============================= КРИТИЧНО ВАЖНЫЕ НАСТРОЙКИ =============================
CSV_PATH = "py_back/rexexp/data/split.csv"
CSV_PATH = "py_back/rexexp/data/split.csv"
MAX_ITEMS = 350_000
N_CLUSTERS = 1050
MIN_SIZE = 38

MODEL_NAME = "DeepPavlov/rubert-base-cased-conversational"  # или вот эта ↓ если есть GPU
# MODEL_NAME = "ai-forever/sbert_large_mt_nlu_ru"  # если хочешь максимум качества

print("Запуск самого умного решения 2025 года...")

model = SentenceTransformer(MODEL_NAME)
model.max_seq_length = 256

print("Интеллектуальная фильтрация...")
df = pd.read_csv(CSV_PATH, dtype=str, low_memory=False).fillna("")

df['full_text'] = (
    df['id2'].fillna("") + " " +
    df['specification'].fillna("") + " " +
    df.iloc[:, 3:10].fillna("").apply(" ".join, axis=1)  # любые описания
)

trash_patterns = r"услуг|окпд|фз-|поставк|ремонт|расходн|принадлеж|канцеляр|моющ|дезинф"
good = df[
    df['full_text'].str.len() > 35 &
    ~df['full_text'].str.lower().str.contains(trash_patterns)
].head(MAX_ITEMS)

texts = good['full_text'].tolist()
print(f"Отобрано интеллектуальных строк: {len(texts):,}")

print("Генерируем глубокие семантические эмбеддинги...")
embeddings = model.encode(
    texts,
    batch_size=128,
    show_progress_bar=True,
    normalize_embeddings=True,
    convert_to_numpy=True
)

print("Адаптивная кластеризация...")
kmeans = MiniBatchKMeans(n_clusters=N_CLUSTERS, batch_size=15000, random_state=42)
labels = kmeans.fit_predict(embeddings)

print("Масочное извлечение характеристик...")

# маски
PATTERNS = [
    r'([дД]иаметр.*?):?\s*([0-9.,\s]+ ?[мк]?м)',
    r'([дД]лина.*?):?\s*([0-9.,\s]+ ?[мк]?м)',
    r'([мМ]ощность.*?):?\s*([0-9.,]+ ?[вВ]т)',
    r'([оО]бъем.*?):?\s*([0-9.,]+ ?[лЛ])',
    r'([пП]амять.*?):?\s*([0-9]+ ?[гГ][бБ])',
    r'([дД]иагональ.*?):?\s*([0-9.,]+ ?["″]?)',
    r'([рР]азрешение.*?):?\s*([0-9x]+)',
    r'([мМ]атериал.*?):?\s*([^\n,;]{3,30})',
    r'([сС]трана.*?):?\s*([А-Яа-я]{4,})',
    r'([цЦ]вет.*?):?\s*([^\n,;]{3,20})',
    r'([кК]оличество.*?):?\s*([0-9]+ ?шт)',
    r'([вВ]ес.*?):?\s*([0-9.,]+ ?[кгг])',
]

def extract_features(text):
    features = []
    for pattern in PATTERNS:
        matches = re.findall(pattern, text)
        for match in matches:
            key = match[0].strip().lower()
            val = match[1].strip()
            # Нормализация
            key = key.replace("диаметр внешний", "внешний диаметр").replace("внутренний диаметр", "внутренний диаметр")
            features.append(f"{key}: {val}")
    return features

result = {}
all_features_global = defaultdict(int)

cluster_features = defaultdict(list)
for idx, label in enumerate(labels):
    feats = extract_features(texts[idx])
    cluster_features[label].extend(feats)
    for f in feats:
        all_features_global[f] += 1

for label in cluster_features:
    feats = cluster_features[label]
    if len(feats) < 8: continue
    
    unique = [f for f in feats if all_features_global[f] <= 2]
    if len(unique) < 3:
        unique = Counter(feats).most_common(10)
        unique = [f[0] for f in unique]
    
    cluster_text = " ".join(texts[i] for i, l in enumerate(labels) if l == label)
    words = re.findall(r"[а-яё]{4,}", cluster_text.lower())
    common = Counter(words).most_common(40)
    
    name = "Неизвестная категория"
    blacklist = {"для","типа","цвет","размер","мм","шт","упак","комплект","набор","товар"}
    for w, c in common:
        if w not in blacklist and c > 10:
            name = w.capitalize()
            break
    
    nice = []
    for f in unique[:12]:
        if ":" in f:
            k, v = f.split(":", 1)
            k = k.replace("диаметр", "Диаметр").replace("длина", "Длина").replace("мощность", "Мощность")
            nice.append(f"{k.strip().capitalize()}: {v.strip()}")
        else:
            nice.append(f.capitalize())
    
    if len(nice) >= 3:
        result[name] = nice

final = {
    "metadata": {
        "source": CSV_PATH,
        "model": MODEL_NAME,
        "method": "LLM-guided + масочное извлечение + адаптивная кластеризация",
        "total_categories": len(result),
        "status": "МАКСИМАЛЬНАЯ ИНТЕЛЛЕКТУАЛЬНОСТЬ — 2025"
    },
    "categories": dict(sorted(result.items()))
}

Path("result").mkdir(exist_ok=True)
with open("result/SMART_ONTOLOGY_2025.json", "w", encoding="utf-8") as f:
    json.dump(final, f, ensure_ascii=False, indent=2)

print(f"Result: {len(result)}")
top = sorted(result.items(), key=lambda x: len(x[1]), reverse=True)[:15]
for i, (cat, feats) in enumerate(top, 1):
    print(f"{i:2}. {cat:<20} → {', '.join(feats[:4])}")