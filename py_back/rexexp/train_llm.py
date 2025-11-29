# train_characteristics_model.py
# Обучает мультилейбл-модель, предсказывающую, какие ключи характеристик
# (Ширина профиля, Диаметр посадочный и т.п.) относятся к товару.
# Использует онтологию universal_characteristics_ontology_v4.json
# и исходный CSV result_itr4.csv.

import json
import math
from pathlib import Path
from typing import List, Dict, Tuple

import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader
from safetensors.torch import save_file
from transformers import AutoTokenizer, AutoModel
import pandas as pd
import chardet
from tqdm import tqdm

# === CONFIG ===

CSV_PATH = "py_back/rexexp/data/result_itr4.csv"
ONTOLOGY_PATH = "result/universal_characteristics_ontology_v4.json"
OUTPUT_DIR = "trained_models"

BASE_MODEL_NAME = "ai-forever/sbert_large_mt_nlu_ru"

BATCH_SIZE = 8
EPOCHS = 3
LR = 2e-5
MAX_LENGTH = 256

device = "cuda" if torch.cuda.is_available() else "cpu"


# === helper для кодировки CSV ===

def detect_encoding(path: str) -> str:
    with open(path, "rb") as f:
        return chardet.detect(f.read(20000)).get("encoding", "utf-8")


# === парсер характеристик (упрощённая версия из v4) ===

NORMALIZATION_MAP = {
    # Общие
    "вид продукции товары": "Вид",
    "вид продукции": "Вид",
    "вид товаров": "Вид",
    "вид": "Вид",

    # Шины
    "вид шин, покрышек и камер резиновых": "Тип шины",
    "вид шин": "Тип шины",
    "вид шин пневматические": "Тип шины",
    "вид запчасти": "Тип запчасти",

    "номинальная ширина профиля": "Ширина профиля",
    "обозначение номинальной ширины профиля": "Ширина профиля",
    "ширина профиля": "Ширина профиля",

    "номинальный посадочный диаметр обода": "Диаметр посадочный",
    "диаметр посадочный": "Диаметр посадочный",
    "посадочный диаметр": "Диаметр посадочный",

    "номинальное отношение высоты профиля": "Отношение профиля",
    "отношение высоты профиля": "Отношение профиля",
    "высота профиля": "Отношение профиля",

    "назначение пневматических шин": "Назначение",
    "категория использования шины": "Категория использования",

    "модель": "Модель",
    "производитель": "Производитель",
    "страна происхождения": "Страна",
    "страна": "Страна",

    "индекс нагрузки": "Индекс нагрузки",
    "индекс категории скорости": "Индекс скорости",
    "индекс скорости": "Индекс скорости",

    "тип конструкции пневматических шин": "Тип конструкции",
    "тип конструкции": "Тип конструкции",
    "тип": "Тип",
}

STOP_WORDS = {"нет", "да", "none", "nan", "null", "undefined", "", "-", "0", "1"}


def preprocess_text(text: str) -> str:
    import re
    text = str(text)
    text = text.replace(";", " ; ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_key_value_pairs(text: str) -> List[Tuple[str, str]]:
    import re
    text = preprocess_text(text)
    pattern = r'([A-Za-zА-Яа-яёЁ0-9 ,\-()"«»]{2,80}?)\s*:\s*([^;,\n]+)'
    matches = re.findall(pattern, text)
    pairs: List[Tuple[str, str]] = []
    for key, value in matches:
        key = key.strip()
        value = value.strip()
        if not key or not value:
            continue
        if key.lower() in STOP_WORDS or value.lower() in STOP_WORDS:
            continue
        if len(value) > 200:
            continue
        pairs.append((key, value))
    return pairs


def normalize_key(key: str) -> str:
    k = key.lower().strip()
    for raw, norm in NORMALIZATION_MAP.items():
        if raw in k:
            return norm
    return key.strip().capitalize()


def normalize_characters(pairs: List[Tuple[str, str]]) -> List[str]:
    normalized: List[str] = []
    for key, value in pairs:
        norm_key = normalize_key(key)
        value = value.strip()
        if not value or value.lower() in STOP_WORDS:
            continue
        normalized.append(f"{norm_key}: {value}")
    return normalized


def build_item_text(row: pd.Series) -> str:
    parts = []
    for col in ["название_сте", "производитель", "страна_происхождения", "название_категории"]:
        if col in row and row[col]:
            val = str(row[col]).strip()
            if val and val not in ("nan", "None"):
                parts.append(val)
    for col in row.index:
        if str(col).startswith("spec"):
            v = str(row[col]).strip()
            if v and v not in ("nan", "None"):
                parts.append(v)
    return " ; ".join(parts)


# === 1. Загружаем онтологию и строим пространство ключей ===

with open(ONTOLOGY_PATH, "r", encoding="utf-8") as f:
    ontology = json.load(f)

cat2chars: Dict[str, List[str]] = {
    cat_id: cat_data.get("characteristics", [])
    for cat_id, cat_data in ontology.get("categories", {}).items()
}

# Множество всех ключей из онтологии
all_keys_set = set()
for chars in cat2chars.values():
    for ch in chars:
        if ":" in ch:
            k, _ = ch.split(":", 1)
            all_keys_set.add(k.strip())

all_keys: List[str] = sorted(all_keys_set)
label2id = {k: i for i, k in enumerate(all_keys)}
id2label = {i: k for k, i in label2id.items()}

print(f"Всего уникальных ключей характеристик: {len(all_keys)}")


# === 2. Загружаем CSV и готовим Dataset ===

enc = detect_encoding(CSV_PATH)
df = pd.read_csv(CSV_PATH, dtype=str, low_memory=False, encoding=enc).fillna("")
df = df[df["id_категории"].notna()]

class CharacteristicsDataset(Dataset):
    def __init__(self, frame: pd.DataFrame):
        self.df = frame.reset_index(drop=True)

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        cat_id = str(row["id_категории"])
        text = build_item_text(row)

        # парсим реальные ключи в этом товаре
        pairs = extract_key_value_pairs(text)
        normalized = normalize_characters(pairs)

        item_keys = set()
        for ch in normalized:
            if ":" not in ch:
                continue
            k, _ = ch.split(":", 1)
            item_keys.add(k.strip())

        # пересечение с ключами категории из онтологии
        y = torch.zeros(len(all_keys), dtype=torch.float32)
        if cat_id in cat2chars:
            cat_keys = set()
            for ch in cat2chars[cat_id]:
                if ":" in ch:
                    k_cat, _ = ch.split(":", 1)
                    cat_keys.add(k_cat.strip())
            final_keys = item_keys.intersection(cat_keys)
        else:
            final_keys = item_keys  # fallback: без онтологии

        for k in final_keys:
            if k in label2id:
                y[label2id[k]] = 1.0

        return {
            "text": text,
            "category_id": cat_id,
            "labels": y,
        }


dataset = CharacteristicsDataset(df)
print(f"Размер датасета: {len(dataset)}")


# === 3. Модель ===

tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_NAME)
encoder = AutoModel.from_pretrained(BASE_MODEL_NAME).to(device)


class CharacteristicsModel(nn.Module):
    def __init__(self, encoder: AutoModel, num_labels: int):
        super().__init__()
        self.encoder = encoder
        hidden_size = encoder.config.hidden_size
        self.classifier = nn.Linear(hidden_size, num_labels)

    def forward(self, input_ids, attention_mask):
        outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        # mean pooling по токенам
        last_hidden = outputs.last_hidden_state  # (batch, seq, hidden)
        mask = attention_mask.unsqueeze(-1)      # (batch, seq, 1)
        masked = last_hidden * mask
        summed = masked.sum(dim=1)               # (batch, hidden)
        counts = mask.sum(dim=1).clamp(min=1e-9)
        pooled = summed / counts                 # (batch, hidden)
        logits = self.classifier(pooled)         # (batch, num_labels)
        return logits


model = CharacteristicsModel(encoder, num_labels=len(all_keys)).to(device)
criterion = nn.BCEWithLogitsLoss()
optimizer = torch.optim.AdamW(model.parameters(), lr=LR)


def collate_fn(batch):
    texts = [item["text"] for item in batch]
    labels = torch.stack([item["labels"] for item in batch], dim=0)

    encodings = tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=MAX_LENGTH,
        return_tensors="pt",
    )
    input_ids = encodings["input_ids"]
    attention_mask = encodings["attention_mask"]

    return {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "labels": labels,
    }


loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True, collate_fn=collate_fn)


# === 4. Обучение ===

for epoch in range(EPOCHS):
    model.train()
    total_loss = 0.0
    for batch in tqdm(loader, desc=f"Epoch {epoch+1}/{EPOCHS}"):
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["labels"].to(device)

        logits = model(input_ids=input_ids, attention_mask=attention_mask)
        loss = criterion(logits, labels)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        total_loss += loss.item()

    avg_loss = total_loss / len(loader)
    print(f"[Epoch {epoch+1}] loss = {avg_loss:.4f}")


# === 5. Сохранение в safetensors + label_map ===

Path(OUTPUT_DIR).mkdir(exist_ok=True)

state = {}
for k, v in model.encoder.state_dict().items():
    state[f"encoder.{k}"] = v.cpu()
for k, v in model.classifier.state_dict().items():
    state[f"classifier.{k}"] = v.cpu()

safetensors_path = Path(OUTPUT_DIR) / "characteristics_model.safetensors"
save_file(state, str(safetensors_path))
print(f"Модель сохранена в {safetensors_path}")

label_map_path = Path(OUTPUT_DIR) / "label_map.json"
with open(label_map_path, "w", encoding="utf-8") as f:
    json.dump(
        {
            "base_model_name": BASE_MODEL_NAME,
            "all_keys": all_keys,
            "label2id": label2id,
            "id2label": id2label,
            "max_length": MAX_LENGTH,
        },
        f,
        ensure_ascii=False,
        indent=2,
    )
print(f"label_map сохранён в {label_map_path}")
