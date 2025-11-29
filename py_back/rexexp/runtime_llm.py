# runtime_characteristics_model.py
# Загружает обученную модель из safetensors и по товару + категории
# возвращает список характеристик "Ключ: Значение"

from pathlib import Path
from typing import List, Dict, Tuple

import torch
from torch import nn
from safetensors.torch import load_file
from transformers import AutoTokenizer, AutoModel
import json
import re


# === те же нормализаторы, что и в train ===

NORMALIZATION_MAP = {
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
    "тип": "Тип",
}

STOP_WORDS = {"нет", "да", "none", "nan", "null", "undefined", "", "-", "0", "1"}


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


def normalize_characters(pairs: List[Tuple[str, str]]) -> List[str]:
    normalized: List[str] = []
    for key, value in pairs:
        norm_key = normalize_key(key)
        value = value.strip()
        if not value or value.lower() in STOP_WORDS:
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


# === модель ===

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
    ):
        safetensors_path = Path(safetensors_path)
        label_map_path = Path(label_map_path)

        with open(label_map_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        self.base_model_name: str = meta["base_model_name"]
        self.all_keys: List[str] = meta["all_keys"]
        self.label2id: Dict[str, int] = meta["label2id"]
        self.id2label: Dict[str, str] = {int(i): k for i, k in meta["id2label"].items()}
        self.max_length: int = max_length or meta.get("max_length", 256)
        self.threshold = threshold

        self.tokenizer = AutoTokenizer.from_pretrained(self.base_model_name)
        self.model = CharacteristicsModel(self.base_model_name, num_labels=len(self.all_keys))

        # грузим веса из safetensors
        tensor_dict = load_file(str(safetensors_path))
        encoder_state = {k.replace("encoder.", ""): v for k, v in tensor_dict.items() if k.startswith("encoder.")}
        classifier_state = {k.replace("classifier.", ""): v for k, v in tensor_dict.items() if k.startswith("classifier.")}

        self.model.encoder.load_state_dict(encoder_state)
        self.model.classifier.load_state_dict(classifier_state)
        self.model.eval()
        self.model.to("cuda" if torch.cuda.is_available() else "cpu")
        self.device = next(self.model.parameters()).device

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

        keys = []
        for i, p in enumerate(probs):
            if p >= self.threshold:
                keys.append(self.all_keys[i])

        # fallback: если ничего не превысило порог — взять топ-3
        if not keys:
            top_indices = probs.argsort()[-3:][::-1]
            keys = [self.all_keys[i] for i in top_indices]
        return keys

    def extract_for_item(self, category_id: str, item_fields: Dict[str, str]) -> List[str]:
        """
        Вход:
          - category_id: сейчас напрямую в текст не добавляем,
            но можно сделать: text = f"[cat_{category_id}] " + text
          - item_fields: поля товара (название_сте, страна_происхождения, производитель, spec*)

        Выход:
          - список "Ключ: Значение", собранный по предсказанным ключам
        """
        text = build_item_text(item_fields)

        # 1. предсказываем важные ключи
        predicted_keys = set(self._predict_keys(text))

        # 2. парсим реальные пары key:value в этом товаре
        pairs = extract_key_value_pairs(text)
        normalized = normalize_characters(pairs)

        # 3. собираем значения только для предсказанных ключей
        result: List[str] = []
        for ch in normalized:
            if ":" not in ch:
                continue
            key, value = ch.split(":", 1)
            key = key.strip()
            if key in predicted_keys:
                result.append(f"{key}: {value.strip()}")

        # если ничего не нашли по совпадению — просто отдадим нормализованные
        if not result:
            return normalized[:10]

        # лёгкая дедупликация по ключам
        seen = set()
        final = []
        for ch in result:
            k = ch.split(":", 1)[0].strip()
            if k in seen:
                continue
            seen.add(k)
            final.append(ch)

        return final


if __name__ == "__main__":
    # Пример использования
    extractor = RuntimeCharacteristicsExtractor(
        safetensors_path="trained_models/characteristics_model.safetensors",
        label_map_path="trained_models/label_map.json",
        threshold=0.5,
    )

    example_item = {
        "название_сте": 'ШИНА ЗИМ. "Nokian  NORDMAN 7"  215/55R16 97T XL (шип.)   ТОВАР',
        "страна_происхождения": "РФ / Россия (сборка: ВЫБОРГ?)",
        "производитель": "АО \"Нокиан Тайерс\"   / Nokian Tyres plc",
        "название_категории": "Шины пневматические для легкового автотранспорта (ГОСТ, ТР ТС 018/2011)",

        # Тут каша из нескольких параметров, часть без двоеточий
        "spec1": "Зимняя шина; шипы: есть; тип: бескамерная;  радиальная",
        # Кривой пробел, запятая вместо точки, лишний комментарий
        "spec2": "Номинальное отношение высоты профиля шины к ее ширине: 55,00000 % (серия 55)",
        # Дубликат с другой формулировкой
        "spec3": "Высота профиля: 55 %; индекс нагрузки: 97; индекс категории скорости: T",
        # Размер записан с мусором
        "spec4": "Номинальная ширина профиля: 215.0  мм ; Размерность шины 215/55R16 XL",
        # Посадочный диаметр с лишним текстом
        "spec5": "Посадочный диаметр: R16 (номинальный посадочный диаметр обода: 16.00000 дюйм)",
        # Немного свободного текста без двоеточий — парсер это проигнорирует
        "spec6": "Применение: легковой автомобиль, эксплуатация по снегу и льду, снижение шума",
        # Странный регистр и мусор в названии ключа
        "spec7": "тип КОНСТРУКЦИИ пневматических шин: Радиальная",
        # Булевый параметр спрятан среди других
        "spec8": "ШИПЫ: да; Наличие шипов: присутствует; страна производства тоннелей: Финляндия (?)",
        # Стандарт, который мы хотим игнорить как мусорный ключ/значение
        "spec9": "Соответствие стандартам: ТР ТС 018/2011, ГОСТ EN bla-bla",
        # Вообще странная строка, из которой вытащится только кусок с двоеточием
        "spec10": "!!! Модель: Nordman 7 XL // партия 23-11-2024; склад: Ярославль",
    }

    cat_id = "793286151"  # Шины пневматические для легкового автомобиля

    chars = extractor.extract_for_item(cat_id, example_item)
    print("Характеристики для товара:")
    for c in chars:
        print(" •", c)
