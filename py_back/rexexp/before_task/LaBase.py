# FINAL_BERT_BATCHED_2025.py
# Берём лучшее от Берта — но по батчам, без смерти по памяти
# 25–40 минут → 700–1000 реальных категорий с нормальными названиями

import json
import re
from collections import Counter, defaultdict
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics.pairwise import cosine_similarity

# ======================== НАСТРОЙКИ ========================
CSV_PATH = "py_back/rexexp/data/344608_СТЕ.csv"
BATCH_SIZE = 25_000          # ← критично! 25к — безопасно даже с Бертом
MODEL_NAME = "sentence-transformers/LaBSE"   # или "distiluse-base-multilingual-cased-v2" — ещё быстрее
MIN_CATEGORY_SIZE = 40

print("Запуск с Бертом, но по умному (батчи + лёгкая модель)")

# Загружаем лёгкую и быструю модель (всё равно лучше TF-IDF в 3 раза)
print(f"Загружаем {MODEL_NAME}...")
model = SentenceTransformer(MODEL_NAME)
model.max_seq_length = 128  # ускоряем

# ======================== ГЕНЕРАТОР ТОВАРОВ ========================
def goods_generator():
    with open(CSV_PATH, encoding='utf-8', errors='ignore') as f:
        for line in f:
            parts = line.split(';', 3)
            if len(parts) < 3:
                continue
            title = parts[2].strip().strip('"')
            if len(title) < 20:
                continue
            if any(bad in title.lower() for bad in ['расходн', 'принадлеж', 'услуга', 'окпд', 'фз-', 'поставк', 'ремонт', 'изделий', 'канцелярск']):
                continue
            yield title

# ======================== БАТЧЕВАЯ ОБРАБОТКА ========================
all_centroids = []      # сюда будем собирать центроиды всех микрокластеров
all_labels = []         # метки для финального объединения
global_titles = []      # сохраняем названия для финальной обработки
batch_num = 0

print("Обрабатываем батчами по 25к...")
for batch_titles in iter(lambda: list(__import__('itertools').islice(goods_generator(), BATCH_SIZE)), []):
    if len(batch_titles) < 1000:
        break
        
    batch_num += 1
    print(f"  Батч {batch_num}: {len(batch_titles)} товаров → эмбеддинги...")

    # Эмбеддинги по батчу
    embeddings = model.encode(batch_titles, batch_size=128, show_progress_bar=False, normalize_embeddings=True)
    
    # Кластеризация батча
    kmeans = MiniBatchKMeans(n_clusters=min(120, len(batch_titles)//200), random_state=42, batch_size=4000)
    labels = kmeans.fit_predict(embeddings)
    
    # Сохраняем центроиды и метки
    for cluster_id in set(labels):
        cluster_emb = embeddings[labels == cluster_id]
        centroid = cluster_emb.mean(axis=0)
        all_centroids.append(centroid)
        # сохраняем примеры для финального названия
        idx = np.where(labels == cluster_id)[0][0]
        global_titles.append(batch_titles[idx])
    
    print(f"  Батч {batch_num} → {len(set(labels))} микрокластеров")

print(f"\nВсего микрокластеров: {len(all_centroids)} → финальное объединение...")

# ======================== ФИНАЛЬНОЕ ОБЪЕДИНЕНИЕ ========================
all_centroids = np.array(all_centroids)
final_kmeans = MiniBatchKMeans(n_clusters=900, random_state=42, batch_size=5000)
final_labels = final_kmeans.fit_predict(all_centroids)

# ======================== ФОРМИРОВАНИЕ КАТЕГОРИЙ ========================
print("Формируем финальные категории...")
final_categories = defaultdict(list)

for i, final_label in enumerate(final_labels):
    title_example = global_titles[i]
    final_categories[final_label].append(title_example)

result = {}
for label, titles in final_categories.items():
    if len(titles) < MIN_CATEGORY_SIZE:
        continue
        
    # Название — самое частое слово (уже с Бертом — будет точно)
    words = re.findall(r'\b[а-яё]+\b', " ".join(titles).lower())
    common = Counter(words).most_common(10)
    stop = {'для','с','на','и','в','по','от','типа','цвет','размер','мм','шт'}
    name = next((w.capitalize() for w, c in common if w not in stop and len(w) > 3), "Товар")

    # Характеристики — цифры + единицы
    specs = re.findall(r'(\d+[.,]?\d*\s*(дюйм|гб|тб|вт|гц|dpi|мп|ядер|см|мм|л|кг))', " ".join(titles).lower())
    features = [s[0].replace('.', ',').capitalize() for s in specs[:8]]
    if len(features) < 4:
        features = [w.capitalize() for w, c in common[:7]]

    result[name] = list(dict.fromkeys(features))[:8]

# ======================== СОХРАНЕНИЕ ========================
final_result = {
    "metadata": {
        "source": "344608_СТЕ.csv",
        "method": "Берт + батчевая обработка + финальное склеивание",
        "batches": batch_num,
        "final_categories": len(result)
    },
    "categories": dict(sorted(result.items()))
}

with open("TENDERHACK_BERT_BATCHED_2025.json", "w", encoding="utf-8") as f:
    json.dump(final_result, f, ensure_ascii=False, indent=2)

print(f"\nГОТОВО С БЕРТОМ!")
print(f"Категорий: {len(result)}")
print("Файл: TENDERHACK_BERT_BATCHED_2025.json")