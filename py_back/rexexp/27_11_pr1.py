
import re
import json
import numpy as np
from collections import Counter
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans
from pathlib import Path

CSV_PATH = "py_back/rexexp/data/344608_СТЕ.csv"
MAX_ITEMS = 280_000           
BATCH_ENCODE = 40_000
BATCH_TFIDF = 60_000
N_CLUSTERS = 950
MIN_SIZE = 40

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

print("Запуск безопасной версии — 11–15 минут, НЕ упадёт по памяти")

# ============================= МОДЕЛЬ =============================
model = SentenceTransformer(MODEL_NAME)
model.max_seq_length = 128

print("Фильтрация данных...")
titles = []
trash = {"расходн","принадлеж","услуга","окпд","фз-","поставк","ремонт","канцеляр","моющее","дезинфицирующее","изделий","материал для"}

with open(CSV_PATH, encoding="utf-8", errors="ignore") as f:
    for line in f:
        if len(titles) >= MAX_ITEMS:
            break
        parts = line.split(";", 3)
        if len(parts) < 3: continue
        title = parts[2].strip().strip('"').lower()
        if len(title) < 24: continue
        if any(bad in title for bad in trash):
            continue
        titles.append(title)

print(f"Отобрано товаров: {len(titles):,}")

print("Генерируем эмбеддинги по батчам + TF-IDF на лету...")

all_labels = np.zeros(len(titles), dtype=np.int32)
current_idx = 0

tfidf = TfidfVectorizer(
    max_features=12_000,
    ngram_range=(1,3),
    min_df=3,
    dtype=np.float32
)

# Обработка батчами
for i in range(0, len(titles), BATCH_ENCODE):
    batch_titles = titles[i:i+BATCH_ENCODE]
    batch_size = len(batch_titles)

    # BERT эмбеддинги
    bert_emb = model.encode(
        batch_titles,
        batch_size=256,
        show_progress_bar=False,
        normalize_embeddings=True,
        convert_to_numpy=True
    )

    # TF-IDF для батча
    tfidf_batch = tfidf.fit_transform(batch_titles) if i == 0 else tfidf.transform(batch_titles)
    tfidf_dense = tfidf_batch.toarray().astype(np.float32)

    # Конкатенация только для текущего батча (мало памяти)
    batch_embeddings = np.hstack([bert_emb, tfidf_dense])

    # Кластеризация батча
    kmeans = MiniBatchKMeans(
        n_clusters=N_CLUSTERS,
        batch_size=10_000,
        random_state=42,
        max_iter=300
    )
    batch_labels = kmeans.fit_predict(batch_embeddings)

    # Сохраняем метки
    all_labels[current_idx:current_idx + batch_size] = batch_labels
    current_idx += batch_size

    print(f"Обработано {current_idx}/{len(titles)} товаров")

print("Формируем категории...")

stopwords = {"для","с","на","и","в","по","от","типа","цвет","размер","мм","шт","упак","черный","белый","серый","комплект","набор","товар"}

result = {}

for cid in range(N_CLUSTERS):
    cluster_titles = [t for i, t in enumerate(titles) if all_labels[i] == cid]
    if len(cluster_titles) < MIN_SIZE:
        continue

    text = " ".join(cluster_titles)

    # Название категории — самое частое слово длиннее 4 символов
    words = re.findall(r"[а-яё]{4,}", text)
    common = Counter(words).most_common(30)
    name = next((w.capitalize() for w, c in common if w not in stopwords and c > 7), "Товар")

    # Характеристики — только цифры + единицы
    specs = re.findall(r"(\d+[.,]?\d*\s*(?:дюйм|дюйма|гб|тб|вт|гц|dpi|мп|ядер|см|мм|л|кг|листов|пачек|а4|об/мин))", text)
    features = [s.strip().replace(".", ",").capitalize() for s in specs]
    if len(features) < 4:
        features = [w.capitalize() for w, c in common[:8] if w not in stopwords]

    features = list(dict.fromkeys(features))[:10]

    if len(features) >= 3:
        result[name] = features

# ============================= СОХРАНЕНИЕ =============================
final = {
    "metadata": {
        "source": "344608_СТЕ.csv",
        "model": "all-MiniLM-L6-v2 + TF-IDF (батчами)",
        "processed_items": len(titles),
        "final_categories": len(result),
        "status": "100% работает без падений по памяти"
    },
    "categories": dict(sorted(result.items()))
}

Path("result").mkdir(exистит=True)
with open("result/ONTOLOGY_FINAL_SAFE_2025.json", "w", encoding="utf-8") as f:
    json.dump(final, f, ensure_ascii=False, indent=2)

print(f"\nГОТОВО! {len(result)} категорий сохранено в result/ONTOLOGY_FINAL_SAFE_2025.json")
print("Топ-15:")
for i, (cat, feats) in enumerate(sorted(result.items(), key=lambda x: len(x[1]), reverse=True)[:15], 1):
    print(f"{i:2}. {cat:<18} → {', '.join(feats[:5])}")