#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_llama_attr_gen.py

Локальный тест генерации "3–5 обязательных характеристик" 
под каждую категорию из CSV:

    CSV_PATH = "py_back/rexexp/data/result_itr4.csv"

Работает с ЛЮБОЙ локальной LLaMA/Mistral/Qwen моделью,
развёрнутой через transformers.

Зависимости:
    pip install transformers accelerate torch pandas

Запуск:
    python test_llama_attr_gen.py
"""

import re
import pandas as pd
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

# ------------------------------
# ПУТЬ К ТВОЕМУ ФАЙЛУ CSV
# ------------------------------
CSV_PATH = "py_back/rexexp/data/result_itr4.csv"

# ------------------------------
# ЛОКАЛЬНАЯ ГЕНЕРАТИВНАЯ МОДЕЛЬ
# ------------------------------
# Примеры:
#   "Qwen/Qwen2.5-7B-Instruct"
#   "meta-llama/Llama-3-8b-instruct"
#   "mistralai/Mistral-7B-Instruct-v0.2"
#
# ВСТАВЬ СВОЮ!
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"


# ------------------------------
# ТЕКСТ-ИНСТРУКЦИЯ (System prompt)
# ------------------------------
SYSTEM_TEXT = (
    "Ты — эксперт по классификации товаров в e-commerce. "
    "Тебе дают название категории на русском языке. "
    "Твоя задача — вернуть 3 ключевые характеристик, "
    "которые по смыслу обязательно должны присутствовать "
    "в описании товара этой категории. "
    "Пиши только названия характеристик, по одному на строку, "
    "без нумерации, без комментариев."
)


def build_prompt(category_name: str) -> str:
    return (
        f"{SYSTEM_TEXT}\n\n"
        f"Категория: {category_name}\n\n"
        f"Характеристики:\n"
    )


def clean_response(text: str) -> list[str]:
    """
    Чистим вывод генеративной модели.
    Оставляем только строки вида «Размер», «Цвет», «Индекс нагрузки» и т.п.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    attrs = []

    for line in lines:
        # убираем "1. ", "- ", "* "
        line = re.sub(r"^[\-\*\d\.\)\s]+", "", line).strip()

        # отсекаем мусор
        if len(line) < 2:
            continue
        if len(line) > 80:
            continue

        attrs.append(line)

    # max 5
    return attrs[:5]


def main():
    print(f"Загружаю модель: {MODEL_NAME} ...")
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
        raise Exception("В CSV нет столбца 'название_категории'")

    categories = df["название_категории"].dropna().unique().tolist()
    print(f"Уникальных категорий: {len(categories)}\n")

    print("Показываю первые 15 категорий:\n")

    for cat in categories[:15]:
        prompt = build_prompt(cat)

        out = pipe(
            prompt,
            do_sample=False,
            temperature=0.0,
            eos_token_id=tokenizer.eos_token_id,
        )[0]["generated_text"]

        attrs = clean_response(out)

        print(f"Категория: {cat}")
        for a in attrs:
            print(f"  - {a}")
        print("-" * 60)


if __name__ == "__main__":
    main()
