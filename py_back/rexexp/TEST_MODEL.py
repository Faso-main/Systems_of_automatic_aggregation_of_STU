#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_llama_attrs.py

1) Читает CSV с товарами:  py_back/rexexp/data/result_itr4.csv
2) Берёт уникальные названия категорий
3) Для каждой категории вызывает локальную LLaMA
4) Полученные 3–5 характеристик сохраняет в:

       py_back/rexexp/data/category_attrs_llama.csv

Зависимости:
    pip install transformers accelerate torch pandas
"""

import re
import pandas as pd
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

# ------------------------------
# Пути
# ------------------------------

CSV_PATH = "py_back/rexexp/data/result_itr4.csv"
OUT_PATH = "py_back/rexexp/data/category_attrs_llama.csv"

# ------------------------------
# Локальная модель
# ------------------------------
# !!! ВСТАВЬ СВОЮ !!!
# Пример:
# MODEL_NAME = "./qwen_local"
# MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"
# MODEL_NAME = "meta-llama/Llama-3-8b-instruct"

MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"


# ------------------------------
# SYSTEM PROMPT
# ------------------------------

SYSTEM_TEXT = (
    "Ты — эксперт по классификации товаров для e-commerce. "
    "Тебе дают название категории. "
    "Верни 3–5 ключевых характеристик, которые обязательно должны быть "
    "у товара в этой категории. "
    "Пиши только названия характеристик, без пояснений, без нумерации, "
    "по одному на строку."
)


def build_prompt(category_name: str) -> str:
    return (
        f"{SYSTEM_TEXT}\n\n"
        f"Категория: {category_name}\n\n"
        f"Характеристики:\n"
    )


def clean_response(text: str) -> list[str]:
    """
    Чистит вывод от мусора: убирает нумерацию, тире, пустые строки.
    возвращает список строк.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    attrs = []

    for line in lines:
        # убираем форматирование типа "1.", "-", "*", "—"
        line = re.sub(r"^[\-\*\d\.\)\s]+", "", line).strip()
        # пропускаем слишком длинный или короткий мусор
        if len(line) < 2 or len(line) > 80:
            continue
        attrs.append(line)

    return attrs[:5]  # максимум 5


def main():
    print(f"Загружаю модель {MODEL_NAME} ...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        device_map="auto",
        torch_dtype="auto",
        trust_remote_code=True,
    )

    pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        device_map="auto",
        max_new_tokens=128,
    )

    print(f"Читаю CSV: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)

    if "название_категории" not in df.columns:
        raise Exception("В CSV нет колонки 'название_категории'")

    categories = sorted(df["название_категории"].dropna().unique().tolist())
    print(f"Найдено категорий: {len(categories)}")

    records = []

    for i, cat in enumerate(categories, start=1):
        print(f"[{i}/{len(categories)}] Обрабатываю: {cat}")

        prompt = build_prompt(cat)

        out = pipe(
            prompt,
            do_sample=False,
            temperature=0.0,
            eos_token_id=tokenizer.eos_token_id,
        )[0]["generated_text"]

        attrs = clean_response(out)

        records.append({
            "category": cat,
            "attributes": "; ".join(attrs)
        })

    # сохраняем результат
    out_df = pd.DataFrame(records)
    out_df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")

    print(f"\nГотово! Сохранено в: {OUT_PATH}")
    print("\nПервые 10 строк результата:\n")
    print(out_df.head(10))


if __name__ == "__main__":
    main()
