import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
import numpy as np
import os

ITEMS_PATH=os.path.join('py_back','rexexp','data','344608_СТЕ.csv')


# Твой CSV
df = pd.read_csv(ITEMS_PATH, sep=';', header=None)
titles = df[2].dropna().str.strip().tolist()  # колонка 2 — названия

# Лёгкая модель
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
embeddings = model.encode(titles[:100000], batch_size=64)  # 100k за 2 минуты

# Кластеризация
kmeans = KMeans(n_clusters=500, random_state=42)
clusters = kmeans.fit_predict(embeddings)

# Результаты
df_clusters = pd.DataFrame({'title': titles[:100000], 'cluster': clusters})
print(df_clusters.groupby('cluster').size().sort_values(ascending=False))