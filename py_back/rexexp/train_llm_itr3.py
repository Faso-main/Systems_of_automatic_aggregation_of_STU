# train_characteristics_model_v4.py
# Обучает мультилейбл-модель для предсказания ключей характеристик.
# Улучшения по сравнению с v3:
#  - пространство ключей all_keys расширяется за счёт всего датасета (data-driven),
#    включая одежду и другие домены;
#  - добавлены форсированные ключи для одежды (Размер, Рост, Цвет, Материал верха, Утеплитель и т.п.);
#  - прежняя логика: фильтрация мусора, pos_weight, [CAT_{id_категории}] в тексте.

import json
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


# ============================= CONFIG =============================

CSV_PATH = "py_back/rexexp/data/result_itr4.csv"
ONTOLOGY_PATH = "result/A__llm_itr6.json"
OUTPUT_DIR = "trained_models"

BASE_MODEL_NAME = "ai-forever/sbert_large_mt_nlu_ru"

BATCH_SIZE = 8
EPOCHS = 3
LR = 2e-5
MAX_LENGTH = 256

# Минимальная поддержка для добавления ключа из данных
KEY_MIN_SUPPORT_GLOBAL = 20

# Форсированные ключи одежды (добавим независимо от частоты)
FORCED_CLOTHES_KEYS = [
    "Размер",
    "Рост",
    "Цвет",
    "Материал верха",
    "Материал",
    "Утеплитель",
    "Класс защиты",
    "Тип",  # тип куртки, тип обуви и т.п.
]

device = "cuda" if torch.cuda.is_available() else "cpu"


# ============================= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============================

def detect_encoding(path: str) -> str:
    with open(path, "rb") as f:
        return chardet.detect(f.read(20000)).get("encoding", "utf-8")


NORMALIZATION_MAP = {
    # более специфичные ключи — раньше
    "индекс скорости и нагрузки": "Индекс нагрузки/скорости",

    # Шины + общие
    "вид продукции товары": "Вид",
    "вид продукции": "Вид",
    "вид товаров": "Вид",
    "вид": "Вид",
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

    # Одежда / спецодежда
    "размер": "Размер",
    "рост": "Рост",
    "материал верха": "Материал верха",
    "материал": "Материал",
    "утеплитель": "Утеплитель",
    "цвет": "Цвет",
    "класс защиты": "Класс защиты",

    # общий "тип" оставляем как Тип
    "тип": "Тип",
}

STOP_WORDS = {"нет", "да", "none", "nan", "null", "undefined", "", "-", "0", "1"}

GENERIC_VID_VALUES = {
    "товары",
    "одежда",
    "одежда для взрослых",
    "транспортные средства",
    "запасные части",
    "спецодежда (специальная экипировка)",
    "головные уборы",
    "одежда специальная",
    "стандартный",
    "стандартный вид",
}

GENERIC_STD_TOKENS = {
    "тр тс",
    "тp тс",
    "gost",
    "гост",
    "en ",
    "iso",
    "стандарты",
    "стандарт",
    "заключение минпромторга",
}


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


def is_generic_pair(norm_key: str, value: str) -> bool:
    vk = norm_key.lower()
    vv = value.lower().strip()

    if norm_key == "Вид" and vv in GENERIC_VID_VALUES:
        return True

    if any(tok in vv for tok in GENERIC_STD_TOKENS) or any(tok in vk for tok in GENERIC_STD_TOKENS):
        return True

    if vv in {"универсальный", "стандартный", "стандартный размер"}:
        return True

    return False


def normalize_characters(pairs: List[Tuple[str, str]]) -> List[str]:
    normalized: List[str] = []
    for key, value in pairs:
        norm_key = normalize_key(key)
        value = value.strip()
        if not value or value.lower() in STOP_WORDS:
            continue
        if is_generic_pair(norm_key, value):
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


# ============================= ОНТОЛОГИЯ + КЛЮЧИ ИЗ ДАННЫХ =============================

with open(ONTOLOGY_PATH, "r", encoding="utf-8") as f:
    ontology = json.load(f)

cat2chars: Dict[str, List[str]] = {
    cat_id: cat_data.get("characteristics", [])
    for cat_id, cat_data in ontology.get("categories", {}).items()
}

all_keys_set = set()
for chars in cat2chars.values():
    for ch in chars:
        if ":" in ch:
            k, _ = ch.split(":", 1)
            all_keys_set.add(k.strip())

print(f"[init] ключей из онтологии: {len(all_keys_set)}")

# Загружаем данные для data-driven ключей
enc = detect_encoding(CSV_PATH)
df = pd.read_csv(CSV_PATH, dtype=str, low_memory=False, encoding=enc).fillna("")
df = df[df["id_категории"].notna()]

# Собираем статистику по ключам из всего датасета
key_counts = {}
print("Сканируем датасет для выявления дополнительных ключей...")
for _, row in tqdm(df.iterrows(), total=len(df)):
    text = build_item_text(row)
    pairs = extract_key_value_pairs(text)
    normalized = normalize_characters(pairs)
    for ch in normalized:
        if ":" not in ch:
            continue
        k, _ = ch.split(":", 1)
        k = k.strip()
        key_counts[k] = key_counts.get(k, 0) + 1

# Добавляем data-driven ключи с достаточной частотой
for k, cnt in key_counts.items():
    if cnt >= KEY_MIN_SUPPORT_GLOBAL:
        all_keys_set.add(k)

# Добавляем форсированные ключи одежды
for k in FORCED_CLOTHES_KEYS:
    all_keys_set.add(k)

all_keys: List[str] = sorted(all_keys_set)
label2id = {k: i for i, k in enumerate(all_keys)}
id2label = {i: k for k, i in label2id.items()}

print(f"[final] всего уникальных ключей (с данными + одежда): {len(all_keys)}")


# ============================= DATASET =============================

class CharacteristicsDataset(Dataset):
    def __init__(self, frame: pd.DataFrame):
        self.df = frame.reset_index(drop=True)

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        cat_id = str(row["id_категории"])
        base_text = build_item_text(row)

        pairs = extract_key_value_pairs(base_text)
        normalized = normalize_characters(pairs)

        item_keys = set()
        for ch in normalized:
            if ":" not in ch:
                continue
            k, _ = ch.split(":", 1)
            item_keys.add(k.strip())

        y = torch.zeros(len(all_keys), dtype=torch.float32)
        for k in item_keys:
            if k in label2id:
                y[label2id[k]] = 1.0

        return {
            "category_id": cat_id,
            "text": base_text,
            "labels": y,
        }


dataset = CharacteristicsDataset(df)
print(f"Размер датасета: {len(dataset)}")


# ============================= МОДЕЛЬ =============================

tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_NAME)
encoder = AutoModel.from_pretrained(BASE_MODEL_NAME).to(device)


class CharacteristicsModel(nn.Module):
    def __init__(self, encoder: AutoModel, num_labels: int):
        super().__init__()
        self.encoder = encoder
        hidden_size = self.encoder.config.hidden_size
        self.classifier = nn.Linear(hidden_size, num_labels)

    def forward(self, input_ids, attention_mask):
        outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        last_hidden = outputs.last_hidden_state
        mask = attention_mask.unsqueeze(-1)
        masked = last_hidden * mask
        summed = masked.sum(dim=1)
        counts = mask.sum(dim=1).clamp(min=1e-9)
        pooled = summed / counts
        logits = self.classifier(pooled)
        return logits


model = CharacteristicsModel(encoder, num_labels=len(all_keys)).to(device)


# ============================= ВЕСА КЛАССОВ =============================

print("Вычисляем pos_weight по частотам меток...")
num_labels = len(all_keys)
pos_counts = torch.zeros(num_labels)

for i in tqdm(range(len(dataset)), desc="Скан датасета под pos_weight"):
    y = dataset[i]["labels"]
    pos_counts += y

N = len(dataset)
neg_counts = N - pos_counts
pos_weight = neg_counts / torch.clamp(pos_counts, min=1.0)
pos_weight[pos_counts == 0] = 1.0

criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight.to(device))
optimizer = torch.optim.AdamW(model.parameters(), lr=LR)


# ============================= COLLATE =============================

def collate_fn(batch):
    texts = [f"[CAT_{b['category_id']}] {b['text']}" for b in batch]
    labels = torch.stack([b["labels"] for b in batch], dim=0)

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


# ============================= TRAIN =============================

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


# ============================= SAVE =============================

Path(OUTPUT_DIR).mkdir(exist_ok=True)

state_dict = {k: v.cpu() for k, v in model.state_dict().items()}
safetensors_path = Path(OUTPUT_DIR) / "characteristics_model.safetensors"
save_file(state_dict, str(safetensors_path))
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
            "key_min_support_global": KEY_MIN_SUPPORT_GLOBAL,
            "forced_clothes_keys": FORCED_CLOTHES_KEYS,
        },
        f,
        ensure_ascii=False,
        indent=2,
    )
print(f"label_map сохранён в {label_map_path}")
