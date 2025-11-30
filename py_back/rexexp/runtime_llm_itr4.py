# ============================================================
#   RUNTIME LLM ITR3 (BATCH OPTIMIZED)
#   Полностью обновлённая версия с батчевым извлечением
# ============================================================

from pathlib import Path
from typing import List, Dict, Tuple, Any

import torch
from torch import nn
from safetensors.torch import load_file
from transformers import AutoTokenizer, AutoModel
import json
import re

from fastapi import FastAPI
from pydantic import BaseModel


# ======================================================================
# ========================= НОРМАЛИЗАЦИЯ ===============================
# ======================================================================

NORMALIZATION_MAP = {
    "индекс скорости и нагрузки": "Индекс нагрузки/скорости",
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
    "размер": "Размер",
    "рост": "Рост",
    "материал верха": "Материал верха",
    "материал": "Материал",
    "утеплитель": "Утеплитель",
    "цвет": "Цвет",
    "класс защиты": "Класс защиты",
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
    text = str(text)
    text = text.replace(";", " ; ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_key_value_pairs(text: str) -> List[Tuple[str, str]]:
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


def build_item_text(item_fields: Dict[str, str]) -> str:
    parts = []
    for col in ["название_сте", "производитель", "страна_происхождения", "название_категории"]:
        if col in item_fields and item_fields[col]:
            val = str(item_fields[col]).strip()
            if val and val not in ("nan", "None"):
                parts.append(val)
    for key, val in item_fields.items():
        if str(key).startswith("spec") and val:
            v = str(val).strip()
            if v and v not in ("nan", "None"):
                parts.append(v)
    return " ; ".join(parts)


# ======================================================================
# ========================== LLM-МОДЕЛЬ =================================
# ======================================================================

class CharacteristicsModel(nn.Module):
    def __init__(self, base_model_name: str, num_labels: int):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(base_model_name)
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


# ======================================================================
# ========================== БАТЧ-ЭКСТРАКТОР ============================
# ======================================================================

class RuntimeCharacteristicsExtractor:
    def __init__(
        self,
        safetensors_path: str | Path,
        label_map_path: str | Path,
        threshold: float = 0.5,
        max_length: int | None = None,
        min_keys: int = 3,
    ):
        safetensors_path = Path(safetensors_path)
        label_map_path = Path(label_map_path)

        with open(label_map_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        self.base_model_name: str = meta["base_model_name"]
        self.all_keys: List[str] = meta["all_keys"]
        self.label2id: Dict[str, int] = meta["label2id"]
        self.id2label: Dict[int, str] = {int(i): k for i, k in meta["id2label"].items()}
        self.max_length: int = max_length or meta.get("max_length", 256)
        self.threshold = threshold
        self.min_keys = min_keys

        self.tokenizer = AutoTokenizer.from_pretrained(self.base_model_name)
        self.model = CharacteristicsModel(self.base_model_name, num_labels=len(self.all_keys))

        tensor_dict = load_file(str(safetensors_path))
        self.model.load_state_dict(tensor_dict, strict=True)

        self.model.eval()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)

    # ------------------------ БАТЧЕВЫЙ ПРОГОН ------------------------

    def _predict_keys_batch(self, texts: List[str]) -> List[List[str]]:
        if not texts:
            return []

        enc = self.tokenizer(
            texts,
            padding="max_length",
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        input_ids = enc["input_ids"].to(self.device)
        attention_mask = enc["attention_mask"].to(self.device)

        with torch.no_grad():
            logits = self.model(input_ids=input_ids, attention_mask=attention_mask)
            probs = torch.sigmoid(logits).cpu().numpy()

        batch_keys = []

        for row in probs:
            selected = [i for i, p in enumerate(row) if p >= self.threshold]
            if len(selected) < self.min_keys:
                top = row.argsort()[::-1]
                for idx in top:
                    if idx not in selected:
                        selected.append(idx)
                    if len(selected) >= self.min_keys:
                        break

            keys = [self.all_keys[i] for i in selected]
            batch_keys.append(keys)

        return batch_keys

    # старый одиночный метод оставлен ради совместимости
    def _predict_keys(self, text: str) -> List[str]:
        return self._predict_keys_batch([text])[0]

    # -------------------- Батчевый извлекатель -------------------------

    def extract_for_items(self, category_id: str, items: List[Dict[str, Any]]) -> List[List[str]]:
        if not items:
            return []

        base_texts = []
        model_texts = []

        for item in items:
            base = build_item_text(item)
            base_texts.append(base)
            model_texts.append(f"[CAT_{category_id}] {base}")

        # батчевое предсказание ключей
        batch_predicted = self._predict_keys_batch(model_texts)

        results = []
        MIN_FINAL = 3

        for base_text, predicted_keys in zip(base_texts, batch_predicted):

            predicted_set = set(predicted_keys)

            pairs = extract_key_value_pairs(base_text)
            normalized = normalize_characters(pairs)

            selected = []
            for ch in normalized:
                if ":" not in ch:
                    continue
                key, value = ch.split(":", 1)
                key = key.strip()
                if key in predicted_set:
                    selected.append(f"{key}: {value.strip()}")

            # fallback: если ничего не совпало
            if not selected:
                results.append(normalized[:10])
                continue

            # fallback: если < MIN_FINAL
            if len(selected) < MIN_FINAL:
                used_keys = {s.split(":", 1)[0].strip() for s in selected}
                for ch in normalized:
                    if ":" not in ch:
                        continue
                    k = ch.split(":", 1)[0].strip()
                    if k in used_keys:
                        continue
                    selected.append(ch)
                    used_keys.add(k)
                    if len(selected) >= MIN_FINAL:
                        break

            # убираем дубликаты по ключу
            seen = set()
            final = []
            for ch in selected:
                if ":" not in ch:
                    continue
                k = ch.split(":", 1)[0].strip()
                if k in seen:
                    continue
                seen.add(k)
                final.append(ch)

            results.append(final)

        return results


# ======================================================================
# ========================== FASTAPI ===================================
# ======================================================================

app = FastAPI(title="TH3 Runtime LLM ITR3 (BATCH)")

extractor = RuntimeCharacteristicsExtractor(
    safetensors_path="trained_models/characteristics_model.safetensors",
    label_map_path="trained_models/label_map.json",
    threshold=0.5,
    min_keys=3,
)


class RegenerateCategoryRequest(BaseModel):
    category_id: str | int
    category_name: str
    items: list[dict[str, Any]]


class Feature(BaseModel):
    key: str
    values: list[str]


class RegenerateCategoryResponse(BaseModel):
    short_description: str
    features: list[Feature]


@app.get("/health")
def health():
    return {"status": "ok"}


# ------------------ Батчевый aggregate ------------------

def aggregate_features(category_id: str, items: list[dict[str, Any]]) -> tuple[str, list[Feature]]:
    agg: dict[str, set[str]] = {}

    # батчевый вызов
    all_chars = extractor.extract_for_items(str(category_id), items)

    for chars in all_chars:
        for ch in chars:
            if ":" not in ch:
                continue
            key, value = ch.split(":", 1)
            key = key.strip()
            value = value.strip()
            if not key or not value:
                continue
            agg.setdefault(key, set()).add(value)

    # краткое описание
    parts = []
    for key, values in agg.items():
        vals = ", ".join(sorted(values))
        if len(vals) > 150:
            vals = vals[:147] + "..."
        parts.append(f"{key}: {vals}")

    short_description = " | ".join(parts[:15])

    features = [
        Feature(key=k, values=sorted(vs))
        for k, vs in sorted(agg.items(), key=lambda kv: kv[0])
    ]

    return short_description, features


@app.post("/regenerate-category", response_model=RegenerateCategoryResponse)
def regenerate_category(req: RegenerateCategoryRequest):
    if not req.items:
        return RegenerateCategoryResponse(short_description="", features=[])

    short_description, features = aggregate_features(str(req.category_id), req.items)

    return RegenerateCategoryResponse(
        short_description=short_description,
        features=features,
    )


# --------------------- LOCAL RUN ------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "runtime_llm_itr3_batch:app",
        host="127.0.0.1",
        port=8002,
        reload=False,
        workers=1,
    )
