# ontology_builder_robust.py
# 100% надёжный, даже на битых CSV

import re
import json
from pathlib import Path
from collections import Counter, defaultdict
from sentence_transformers import SentenceTransformer, util
import pandas as pd

# ==================== КОНФИГ ====================
CSV_PATH = "py_back/rexexp/data/split.csv"
MIN_SUPPORT = 7
TOP_K = 14
SIM_THRESHOLD = 0.91
OUTPUT_DIR = "result"

# ==================== МОДЕЛЬ ====================
print("Загрузка sBERT...")
model = SentenceTransformer("ai-forever/sbert_large_mt_nlu_ru")

# ==================== ПАТТЕРНЫ ====================
PATTERNS = {
    "Диагональ":          (r'(?:диагональ|экран)[\s:]+([0-9.,]+)\s*["″′′"]',       lambda v: f"{v}\""),
    "Разрешение":         (r'разрешение[\s:]+([0-9x\s]+)',                        lambda v: v.replace(" ", "")),
    "Частота обновления": (r'частота\s+(?:обновления|разв[её]ртки)[\s:]+([0-9]+)', lambda v: f"{v} Гц"),
    "Объём памяти":       (r'(?:память|объём|емкость).*?([0-9]+)\s*(гб|тб)',      lambda v: v.upper()),
    "Мощность":           (r'мощность[\s:]+([0-9.,]+)\s*(?:вт|квт)',             lambda v: f"{v} Вт"),
    "Вес":                (r'(?:вес|масса)[\s:]+([0-9.,]+)\s*(?:кг|г)',           lambda v: v),
    "Внутренний диаметр": (r'внутр(?:енний|\.)\s*диаметр.*?([0-9.,]+)\s*мм',      lambda v: f"{v} мм"),
    "Внешний диаметр":    (r'внешн(?:ий|\.)\s*диаметр.*?([0-9.,]+)\s*мм',         lambda v: f"{v} мм"),
    "Материал":           (r'материал[^:\n";]{0,30}[:]\s*([^;\n",}{]{4,60})',     lambda v: v.strip().capitalize()),
    "Цвет":               (r'цвет[^:\n";]{0,30}[:]\s*([^;\n",}{]{3,40})',        lambda v: v.strip().capitalize()),
    "Страна":             (r'страна[^:\n";]{0,30}[:]\s*([А-Яа-яЁё]+)',           lambda v: v.capitalize()),
    "Интерфейс":          (r'интерфейс[\s:]+(usb\s*[0-9]\.[0-9x]?)',             lambda v: v.upper()),
}

def safe_extract(text):
    if not text or len(str(text)) < 30:
        return []
    text = " " + str(text).lower() + " "
    feats = []
    for name, (pat, proc) in PATTERNS.items():
        for match in re.findall(pat, text, flags=re.IGNORECASE):
            value = match[-1] if isinstance(match, tuple) else match  # ← вот фикс!
            value = str(value).strip()
            if value and len(value) < 70:
                feats.append(f"{name}: {proc(value)}")
    return feats

def dedup(features):
    if len(features) <= TOP_K:
        return features
    try:
        emb = model.encode(features, convert_to_tensor=True)
        keep, used = [], set()
        for i, f in enumerate(features):
            if i in used: continue
            keep.append(f)
            if len(keep) >= TOP_K: break
            for j in range(i+1, len(features)):
                if util.cos_sim(emb[i], emb[j]) > SIM_THRESHOLD:
                    used.add(j)
        return keep
    except:
        return features[:TOP_K]

# ==================== ЧТЕНИЕ CSV (надёжно!) ====================
print(f"Читаем битый CSV: {CSV_PATH}")
try:
    df = pd.read_csv(CSV_PATH, dtype=str, low_memory=False, engine="c").fillna("")
except:
    print("C-движок упал → переключаемся на python-движок...")
    df = pd.read_csv(CSV_PATH, dtype=str, low_memory=False, engine="python", on_bad_lines="skip").fillna("")

if 'id2' not in df.columns or 'specification' not in df.columns:
    raise ValueError("Нужны колонки: id2, specification")

df = df[['id2', 'specification']].dropna(subset=['id2'])
df['id2'] = df['id2'].astype(str).str.strip()

# Фильтр мусора
trash = {"услуга", "окпд", "фз-", "поставк", "ремонт", "расходн", "канцеляр", "моющ", "дезинф"}
df = df[~df['id2'].str.contains("|".join(trash), case=False, na=False)]

print(f"Обрабатываем {len(df):,} строк...")

# ==================== ОСНОВНОЙ ЦИКЛ ====================
cat_feats = defaultdict(list)
cat_cnt = defaultdict(int)

for idx, row in df.iterrows():
    if idx % 25000 == 0:
        print(f"   обработано {idx:,} строк...")
    feats = safe_extract(row['specification'])
    if feats:
        cat_feats[row['id2']].extend(feats)
        cat_cnt[row['id2']] += 1

# ==================== ФИНАЛ ====================
result = {}
for cat, feats in cat_feats.items():
    if cat_cnt[cat] < MIN_SUPPORT:
        continue
    top = [f for f, c in Counter(feats).most_common(100) if c >= 2]
    clean = dedup(top)
    if len(clean) >= 5:
        result[cat] = clean

print(f"\nГОТОВО! {len(result)} чистых категорий")

Path(OUTPUT_DIR).mkdir(exist_ok=True)
with open(f"{OUTPUT_DIR}/ONTOLOGY_2025_ROBUST.json", "w", encoding="utf-8") as f:
    json.dump({
        "metadata": {"categories": len(result), "rows_processed": len(df)},
        "categories": dict(sorted(result.items()))
    }, f, ensure_ascii=False, indent=2)

# Примеры
print("\nПримеры лучших категорий:")
for cat in list(result)[:10]:
    print(f"\n{cat}")
    for f in result[cat][:8]:
        print(f"  → {f}")

print("\nФайл сохранён!")