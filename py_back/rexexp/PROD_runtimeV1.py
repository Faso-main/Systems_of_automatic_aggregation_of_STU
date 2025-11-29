# runtime_llm_itr3.py
# Прогоняет весь result_itr4.csv через RuntimeCharacteristicsExtractor
# и сохраняет:
#  - items:  id_сте -> {id_сте, id_категории, category_name, raw_name, producer, country, characteristics}
#  - categories: id_категории -> {id_категории, category_name, item_ids}
#
# Это заготовка под последующую агрегацию / работу фронта.

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

import chardet
import pandas as pd
from tqdm import tqdm

# ВАЖНО: импортируй тот runtime, который у тебя реально лежит и работает:
# из моей последней версии это runtime_characteristics_model_v4,
# но если у тебя пока v2 / v3 — просто поправь импорт.
from runtime_llm_itr3 import RuntimeCharacteristicsExtractor


# ============================= КОНФИГ =============================

CSV_PATH = "py_back/rexexp/data/result_itr4.csv"

MODEL_PATH = "trained_models/characteristics_model.safetensors"
LABEL_MAP_PATH = "trained_models/label_map.json"

OUTPUT_DIR = "result"
OUTPUT_JSON = "runtime_llm_items_itr3.json"


# ============================= СЛУЖЕБНЫЕ =============================

def detect_encoding(path: str) -> str:
    with open(path, "rb") as f:
        return chardet.detect(f.read(20000)).get("encoding", "utf-8")


def load_items(csv_path: str) -> pd.DataFrame:
    enc = detect_encoding(csv_path)
    df = pd.read_csv(csv_path, dtype=str, low_memory=False, encoding=enc).fillna("")

    required = ["id_сте", "id_категории"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"В CSV не хватает колонок: {missing}")

    # Можно отфильтровать явно пустые строки по названию
    if "название_сте" in df.columns:
        df = df[df["название_сте"].astype(str).str.strip() != ""]

    df = df.reset_index(drop=True)
    return df


def build_item_fields(row: pd.Series) -> Dict[str, Any]:
    """
    Собираем dict, который отдаём в RuntimeCharacteristicsExtractor.extract_for_item.
    В нём должны быть:
      - название_сте
      - страна_происхождения
      - производитель
      - название_категории
      - все spec*
    Остальное extractor проигнорирует.
    """
    fields: Dict[str, Any] = {}

    for col in ["название_сте", "страна_происхождения", "производитель", "название_категории"]:
        if col in row:
            fields[col] = row[col]

    for col in row.index:
        if str(col).startswith("spec"):
            fields[col] = row[col]

    return fields


# ============================= MAIN =============================

def main():
    Path(OUTPUT_DIR).mkdir(exist_ok=True)

    print("🔧 Загружаем CSV...")
    df = load_items(CSV_PATH)
    print(f"Строк в датасете: {len(df):,}")

    print("🧠 Инициализируем RuntimeCharacteristicsExtractor...")
    extractor = RuntimeCharacteristicsExtractor(
        safetensors_path=MODEL_PATH,
        label_map_path=LABEL_MAP_PATH,
        threshold=0.5,      # можно потом подкрутить
        # min_keys можно тоже прокинуть, если есть в конструкторе v4
    )

    items_payload: Dict[str, Dict[str, Any]] = {}
    categories_payload: Dict[str, Dict[str, Any]] = {}

    for _, row in tqdm(df.iterrows(), total=len(df), desc="Обработка товаров"):
        item_id = str(row["id_сте"])
        cat_id = str(row["id_категории"])

        category_name = ""
        if "название_категории" in row:
            category_name = str(row["название_категории"]).strip()

        raw_name = str(row.get("название_сте", "")).strip()
        producer = str(row.get("производитель", "")).strip()
        country = str(row.get("страна_происхождения", "")).strip()

        item_fields = build_item_fields(row)

        try:
            characteristics = extractor.extract_for_item(cat_id, item_fields)
        except Exception as e:
            # чтобы не падать из-за одного бага в данных
            characteristics = []
            print(f"[WARN] Ошибка при обработке id_сте={item_id}: {e}")

        # сохраняем инфу по товару
        items_payload[item_id] = {
            "id_сте": item_id,
            "id_категории": cat_id,
            "category_name": category_name,
            "raw_name": raw_name,
            "producer": producer,
            "country": country,
            "characteristics": characteristics,
        }

        # обновляем агрегат по категории
        if cat_id not in categories_payload:
            categories_payload[cat_id] = {
                "id_категории": cat_id,
                "category_name": category_name,
                "item_ids": [],
            }
        categories_payload[cat_id]["item_ids"].append(item_id)

    generated_at = datetime.now().isoformat(timespec="seconds")

    output = {
        "meta": {
            "source_csv": CSV_PATH,
            "model_safetensors": MODEL_PATH,
            "label_map": LABEL_MAP_PATH,
            "generated_at": generated_at,
            "items_count": len(items_payload),
            "categories_count": len(categories_payload),
        },
        "categories": categories_payload,
        "items": items_payload,
    }

    out_path = Path(OUTPUT_DIR) / OUTPUT_JSON
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("✅ runtime_llm_itr3 закончил работу.")
    print(f"Файл сохранён: {out_path}")


if __name__ == "__main__":
    main()
