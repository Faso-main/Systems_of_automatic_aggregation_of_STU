# runtime_characteristics_model_v4.py
# Загружает characteristics_model.safetensors и по товару
# возвращает список "Ключ: Значение", учитывая:
#  - расширенное пространство ключей (в т.ч. одежда);
#  - минимум 3 предсказанных ключа (fallback);
#  - мягкий fallback по normalized, если модель дала слишком мало.

from pathlib import Path
from typing import List, Dict, Tuple

import torch
from torch import nn
from safetensors.torch import load_file
from transformers import AutoTokenizer, AutoModel
import json
import re


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

    # одежда / спецодежда
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

    def _predict_keys(self, text: str) -> List[str]:
        encodings = self.tokenizer(
            text,
            padding="max_length",
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        input_ids = encodings["input_ids"].to(self.device)
        attention_mask = encodings["attention_mask"].to(self.device)

        with torch.no_grad():
            logits = self.model(input_ids=input_ids, attention_mask=attention_mask)
            probs = torch.sigmoid(logits)[0].cpu().numpy()

        # базовый отбор по порогу
        selected_indices = [i for i, p in enumerate(probs) if p >= self.threshold]

        # гарантируем минимум self.min_keys ключей
        if len(selected_indices) < self.min_keys:
            top_indices = probs.argsort()[::-1]  # от большего к меньшему
            for idx in top_indices:
                if idx not in selected_indices:
                    selected_indices.append(idx)
                if len(selected_indices) >= self.min_keys:
                    break

        keys = [self.all_keys[i] for i in selected_indices]
        return keys

    def extract_for_item(self, category_id: str, item_fields: Dict[str, str]) -> List[str]:
        base_text = build_item_text(item_fields)
        model_text = f"[CAT_{category_id}] {base_text}"

        predicted_keys = set(self._predict_keys(model_text))

        pairs = extract_key_value_pairs(base_text)
        normalized = normalize_characters(pairs)

        result: List[str] = []
        for ch in normalized:
            if ":" not in ch:
                continue
            key, value = ch.split(":", 1)
            key = key.strip()
            if key in predicted_keys:
                result.append(f"{key}: {value.strip()}")

        # если вообще ничего не прошло через предсказанные ключи — просто вернём сырые нормализованные
        if not result:
            return normalized[:10]

        # если слишком мало (например, <3) — докинем ещё нормализованных
        MIN_FINAL = 3
        if len(result) < MIN_FINAL:
            used_keys = {ch.split(":", 1)[0].strip() for ch in result}
            for ch in normalized:
                if ":" not in ch:
                    continue
                k = ch.split(":", 1)[0].strip()
                if k in used_keys:
                    continue
                result.append(ch)
                used_keys.add(k)
                if len(result) >= MIN_FINAL:
                    break

        # убираем дубль по ключу
        seen = set()
        final = []
        for ch in result:
            if ":" not in ch:
                continue
            k = ch.split(":", 1)[0].strip()
            if k in seen:
                continue
            seen.add(k)
            final.append(ch)

        return final


if __name__ == "__main__":
    extractor = RuntimeCharacteristicsExtractor(
        safetensors_path="trained_models/characteristics_model.safetensors",
        label_map_path="trained_models/label_map.json",
        threshold=0.5,
        min_keys=3,
    )

    # тест на одежду
    example_item = {
        "название_сте": "Куртка зимняя утепленная с капюшоном, т.синий, размер 52-54",
        "страна_происхождения": "Китай",
        "производитель": "ООО ТекстильПром",
        "название_категории": "Одежда специальная защитная",
        "spec1": "Размер: 52-54; рост: 182-188",
        "spec2": "Материал верха: полиэстер 100%; утеплитель: синтепон",
        "spec3": "Цвет: темно-синий; Тип: куртка утепленная",
        "spec4": "ГОСТ: ТР ТС 019/2011; класс защиты: 1",
    }

    cat_id = "999999999"

    chars = extractor.extract_for_item(cat_id, example_item)
    print("Характеристики для товара (одежда):")
    for c in chars:
        print(" •", c)
