import json
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
from typing import Dict, List

RUNTIME_ITEMS_PATH = "result/PROD_runtime_V2_READY.json"
RUNTIME_CATEGORIES_PATH = "result/runtime_llm_items_itr3.json"
OUTPUT_DIR = "result"
OUTPUT_JSON = "universal_characteristics_ontology_v4.json"

TOP_K = 15  # максимум характеристик на категорию


def load_runtime_items() -> dict:
    with open(RUNTIME_ITEMS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_runtime_categories() -> dict:
    with open(RUNTIME_CATEGORIES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_short_description(chars: List[str]) -> str:
    """
    Краткое описание: берём до 5 уникальных ключей из "Ключ: Значение".
    Например: "Вид · Ширина профиля · Индекс нагрузки".
    """
    keys: List[str] = []
    for ch in chars:
        if not isinstance(ch, str):
            continue
        if ":" not in ch:
            continue
        key = ch.split(":", 1)[0].strip()
        if key and key not in keys:
            keys.append(key)

    keys = keys[:5]
    return " · ".join(keys)


def build_ontology(
    runtime_items: dict,
    runtime_categories: dict,
) -> dict:
    items_meta = runtime_items.get("meta", {})
    items_data = runtime_items.get("items", {})

    cats_meta = runtime_categories.get("meta", {})
    cats_data = runtime_categories.get("categories", {})

    # cat_id -> Counter(characteristic)
    cat_char_counters: Dict[str, Counter] = defaultdict(Counter)
    # cat_id -> set(item_ids)
    cat_items: Dict[str, set] = defaultdict(set)
    # cat_id -> name
    cat_names: Dict[str, str] = {}

    # 1) Проходим по runtime_llm_items_itr3.json (категории → item_ids)
    for cat_id, cat_info in cats_data.items():
        cat_id_str = str(cat_id)
        cat_name = cat_info.get("category_name") or cat_info.get("name") or ""
        item_ids = cat_info.get("item_ids", [])

        if cat_name:
            cat_names[cat_id_str] = cat_name

        for item_id in item_ids:
            item_id_str = str(item_id)
            cat_items[cat_id_str].add(item_id_str)

            # подтягиваем характеристики из PROD_runtime_V2_READY.json
            item_obj = items_data.get(item_id_str)
            if not item_obj:
                continue

            # на всякий случай проверяем согласованность id_категории
            item_cat_id = str(item_obj.get("id_категории", "")).strip()
            if item_cat_id and item_cat_id != cat_id_str:
                # если вдруг не совпало — всё равно используем по runtime_categories
                pass

            chars = item_obj.get("characteristics", [])
            for ch in chars:
                if isinstance(ch, str) and ch.strip():
                    cat_char_counters[cat_id_str][ch.strip()] += 1

    # 2) Строим итоговые категории
    categories_out: Dict[str, dict] = {}

    for cat_id, counter in cat_char_counters.items():
        # Сортировка по частоте, берём топ-K
        most_common_chars = [ch for ch, _ in counter.most_common(TOP_K)]

        # Название категории
        cat_name = cat_names.get(cat_id)
        # Если вдруг нет имени в runtime_llm_items_itr3 — можно попробовать достать из items
        if not cat_name:
            # пробегаем первые несколько товаров категории
            for item_id in list(cat_items.get(cat_id, []))[:10]:
                item_obj = items_data.get(item_id)
                if not item_obj:
                    continue
                name = item_obj.get("category_name")
                if name:
                    cat_name = name
                    break

        # Краткое описание
        short_desc = generate_short_description(most_common_chars)

        sample_products = sorted(cat_items.get(cat_id, []), key=lambda x: int(x))

        categories_out[cat_id] = {
            "category_id": int(cat_id) if cat_id.isdigit() else cat_id,
            "category_name": cat_name or "",
            "short_description": short_desc,
            "characteristics": most_common_chars,
            "sample_products": sample_products,
            "total_items": len(sample_products),
        }

    ontology = {
        "meta": {
            "version": "4_from_runtime_v2",
            "generated_at": datetime.utcnow().isoformat(),
            "source_runtime_items": RUNTIME_ITEMS_PATH,
            "source_runtime_categories": RUNTIME_CATEGORIES_PATH,
            "items_meta": items_meta,
            "categories_meta": cats_meta,
            "categories_count": len(categories_out),
        },
        "categories": categories_out,
    }

    return ontology


def main():
    print("Загружаем runtime items…")
    runtime_items = load_runtime_items()

    print("Загружаем runtime categories…")
    runtime_categories = load_runtime_categories()

    print("Строим онтологию категорий…")
    ontology = build_ontology(runtime_items, runtime_categories)

    Path(OUTPUT_DIR).mkdir(exist_ok=True)
    out_path = Path(OUTPUT_DIR) / OUTPUT_JSON
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(ontology, f, ensure_ascii=False, indent=2)

    print(f"Онтология сохранена в {out_path}")
    print(f"Категорий: {len(ontology['categories'])}")


if __name__ == "__main__":
    main()
