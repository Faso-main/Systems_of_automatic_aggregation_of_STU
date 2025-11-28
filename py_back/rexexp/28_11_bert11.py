# ontology_builder/core.py
import re
import json
from pathlib import Path
from collections import Counter, defaultdict
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer, util
import pandas as pd


class OntologyBuilder:
    def __init__(
        self,
        csv_path: str = "py_back/rexexp/data/split.csv",
        min_support: int = 7,
        top_k: int = 14,
        sim_threshold: float = 0.91,
        output_dir: str = "result"
    ):
        self.csv_path = Path(csv_path)
        self.min_support = min_support
        self.top_k = top_k
        self.sim_threshold = sim_threshold
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        print("Загрузка модели sBERT...")
        self.model = SentenceTransformer("ai-forever/sbert_large_mt_nlu_ru")

        # Умные паттерны: имя → (паттерн, постобработка)
        self.patterns = {
            "Диагональ":          (r'(?:диагональ|экран)[\s:]+([0-9.,]+)\s*["″′′"]', lambda v: f"{v.strip()}\""),
            "Разрешение":         (r'разрешение[\s:]+([0-9x\s]+)',                   lambda v: v.strip().replace(" ", "")),
            "Частота обновления": (r'частота\s+(?:обновления|разв[её]ртки)[\s:]+([0-9]+)\s*гц', lambda v: f"{v.strip()} Гц"),
            "Объём памяти":       (r'(?:объём|память|емкость).*?([0-9]+)\s*(гб|тб)', lambda v: v.strip().upper()),
            "Мощность":           (r'мощность[\s:]+([0-9.,]+)\s*(?:вт|квт)',        lambda v: f"{v.strip()} Вт"),
            "Вес":                (r'(?:вес|масса)[\s:]+([0-9.,]+)\s*(?:кг|г)',      lambda v: v.strip()),
            "Внутренний диаметр": (r'(?:внутр(?:енний|\.)\s*диаметр|вн\.?\s*диам\.?)[\s:]+([0-9.,]+)\s*мм', lambda v: f"{v.strip()} мм"),
            "Внешний диаметр":    (r'(?:внешн(?:ий|\.)\s*диаметр|внешн\.?\s*диам\.?)[\s:]+([0-9.,]+)\s*мм', lambda v: f"{v.strip()} мм"),
            "Материал":           (r'материал[^\n":;]{0,30}[:]\s*([^;\n",}{]{4,50})', lambda v: v.strip().capitalize()),
            "Цвет":               (r'цвет[^\n":;]{0,30}[:]\s*([^;\n",}{]{3,30})',    lambda v: v.strip().capitalize()),
            "Страна":             (r'страна[^\n":;]{0,30}[:]\s*([А-Яа-яЁё]+)',      lambda v: v.strip().capitalize()),
            "Интерфейс":          (r'интерфейс[\s:]+(usb\s*[0-9]\.[0-9x]?)',        lambda v: v.strip().upper()),
            "Тип матрицы":        (r'(?:тип\s+матрицы|матрица)[\s:]+([A-Za-z0-9\+]+)', lambda v: v.strip().upper()),
        }

    def extract_clean(self, text: str) -> List[str]:
        if not text or len(str(text)) < 30:
            return []
        text = " " + str(text).lower() + " "
        feats = []

        for name, (pattern, processor) in self.patterns.items():
            matches = re.findall(pattern, text, flags=re.IGNORECASE)
            for match in matches:
                # Важно: match может быть tuple → берём последний элемент
                if isinstance(match, tuple):
                    value = match[-1]
                else:
                    value = match
                if value and len(str(value)) < 60:
                    processed = processor(str(value))
                    if processed:
                        feats.append(f"{name}: {processed}")
        return feats

    def deduplicate_features(self, features: List[str]) -> List[str]:
        if len(features) <= self.top_k:
            return features
        try:
            embeddings = self.model.encode(features, convert_to_tensor=True)
            keep = []
            used = set()
            for i, feat in enumerate(features):
                if i in used:
                    continue
                keep.append(feat)
                if len(keep) >= self.top_k:
                    break
                for j in range(i + 1, len(features)):
                    if j in used:
                        continue
                    if util.cos_sim(embeddings[i], embeddings[j]) > self.sim_threshold:
                        used.add(j)
            return keep
        except:
            return features[:self.top_k]  # fallback

    def run(self) -> Dict[str, Any]:
        print(f"Чтение {self.csv_path.name}...")
        df = pd.read_csv(self.csv_path, dtype=str, low_memory=False).fillna("")

        if 'id2' not in df.columns or 'specification' not in df.columns:
            raise ValueError("В CSV должны быть колонки: id2, specification")

        df = df[['id2', 'specification']].dropna()
        df['id2'] = df['id2'].astype(str).str.strip()

        # Удаляем мусорные категории
        trash_keywords = {"услуга", "окпд", "фз-", "поставк", "ремонт", "расходн", "канцеляр", "моющ", "дезинф"}
        mask = ~df['id2'].str.contains("|".join(trash_keywords), case=False, na=False)
        df = df[mask]

        print(f"Обрабатываем {len(df):,} строк...")

        cat_features = defaultdict(list)
        cat_count = defaultdict(int)

        for _, row in df.iterrows():
            feats = self.extract_clean(row['specification'])
            if feats:
                cat_features[row['id2']].extend(feats)
                cat_count[row['id2']] += 1

        print(f"Найдено {len(cat_count)} категорий, фильтруем...")

        result = {}
        for cat, feats in cat_features.items():
            if cat_count[cat] < self.min_support:
                continue
            counter = Counter(feats)
            top_feats = [f for f, c in counter.most_common(100) if c >= 2]
            clean_feats = self.deduplicate_features(top_feats)
            if len(clean_feats) >= 5:
                result[cat] = clean_feats

        # Сохраняем
        output_file = self.output_dir / "ONTOLOGY_2025_FINAL.json"
        final_json = {
            "metadata": {
                "source": self.csv_path.name,
                "rows_processed": len(df),
                "categories_found": len(result),
                "status": "ГОТОВО — КРАСИВО И ЧИСТО",
                "version": "2025.1"
            },
            "categories": dict(sorted(result.items()))
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_json, f, ensure_ascii=False, indent=2)

        print(f"ГОТОВО! {len(result)} категорий → {output_file}")
        print("\nПримеры:")
        for cat in list(result.keys())[:8]:
            print(f"\n{cat}")
            for f in result[cat][:7]:
                print(f"  → {f}")

        return final_json