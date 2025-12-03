# runtime_llm_extract_characteristics_itr3.py
# Прогоняет весь result_itr4.csv через RuntimeCharacteristicsExtractor (v4)
# и сохраняет по каждому товару "умные" характеристики:
#   items[item_id] = {
#       id_сте,
#       id_категории,
#       category_name,
#       raw_name,
#       producer,
#       country,
#       characteristics: [ "Ключ: Значение", ... ]
#   }

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

import chardet
import pandas as pd
from tqdm import tqdm

# Импорт твоей модели рантайма
from runtime_llm_itr3 import RuntimeCharacteristicsExtractor


# ============================= КОНФИГ =============================

CSV_PATH = "py_back/rexexp/data/result_itr4.csv"

MODEL_PATH = "trained_models/characteristics_model.safetensors"
LABEL_MAP_PATH = "trained_models/label_map.json"

OUTPUT_DIR = "result"
OUTPUT_JSON = "runtime_item_characteristics_itr3.json"


# ============================= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============================

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

    # можно чуть подчистить совсем пустые товары
    if "название_сте" in df.columns:
        df = df[df["название_сте"].astype(str).str.strip() != ""]

    df = df.reset_index(drop=True)
    return df


def build_item_fields(row: pd.Series) -> Dict[str, Any]:
    """
    Собираем dict полей, который отдаём в RuntimeCharacteristicsExtractor.extract_for_item.

    Включаем:
      - название_сте
      - страна_происхождения
      - производитель
      - название_категории
      - все spec*
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

    print("Загружаем CSV...")
    df = load_items(CSV_PATH)
    print(f"Строк в датасете: {len(df):,}")

    print("🧠 Инициализируем RuntimeCharacteristicsExtractor (v4)...")
    extractor = RuntimeCharacteristicsExtractor(
        safetensors_path=MODEL_PATH,
        label_map_path=LABEL_MAP_PATH,
        threshold=0.5,   # как и раньше, можно потом подкрутить
        min_keys=3,      # минимум ключей на товар
    )

    items_payload: Dict[str, Dict[str, Any]] = {}

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
            characteristics = []
            print(f"[WARN] Ошибка при обработке id_сте={item_id}: {e}")

        items_payload[item_id] = {
            "id_сте": item_id,
            "id_категории": cat_id,
            "category_name": category_name,
            "raw_name": raw_name,
            "producer": producer,
            "country": country,
            "characteristics": characteristics,
        }

    generated_at = datetime.now().isoformat(timespec="seconds")

    output = {
        "meta": {
            "source_csv": CSV_PATH,
            "model_safetensors": MODEL_PATH,
            "label_map": LABEL_MAP_PATH,
            "generated_at": generated_at,
            "items_count": len(items_payload),
        },
        "items": items_payload,
    }

    out_path = Path(OUTPUT_DIR) / OUTPUT_JSON
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("✅ runtime_llm_extract_characteristics_itr3 закончил работу.")
    print(f"Файл сохранён: {out_path}")


if __name__ == "__main__":
    main()
