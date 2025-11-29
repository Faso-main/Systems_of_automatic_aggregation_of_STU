#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_llama_attrs_v2.py

Версия 2:
Модель не придумывает характеристики с нуля,
а выбирает 3–5 штук из КАНОНИЧЕСКОГО СПИСКА атрибутов.

Вход:
    CSV_PATH = "py_back/rexexp/data/result_itr4.csv"

Выход:
    py_back/rexexp/data/category_attrs_llama_v2.csv

Формат:
    category, attributes  (атрибуты через "; ")

Зависимости:
    pip install transformers accelerate torch pandas
"""

import re
from typing import List, Dict

import pandas as pd
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline


# ------------------------------
# Пути
# ------------------------------

CSV_PATH = "py_back/rexexp/data/result_itr4.csv"
OUT_PATH = "py_back/rexexp/data/category_attrs_llama_v2.csv"

# ------------------------------
# Локальная модель
# ------------------------------
# ВСТАВЬ СВОЮ / ЛОКАЛЬНЫЙ ПУТЬ
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"
# MODEL_NAME = "./local_llama_model_dir"


# ------------------------------
# Канонический список атрибутов
# ------------------------------

CANONICAL_ATTRS: List[str] = [
    # Общие (одежда/обувь/СИЗ)
    "Размер",
    "Размерный ряд",
    "Пол",
    "Возраст",
    "Цвет",
    "Сезон",
    "Состав ткани",
    "Материал",
    "Тип ткани",
    "Тип изделия",
    "Длина изделия",
    "Тип застежки",
    "Наличие подкладки",

    # Обувь
    "Размер обуви",
    "Материал верха",
    "Материал подкладки",
    "Материал подошвы",
    "Тип подошвы",
    "Сезонность обуви",
    "Назначение обуви",
    "Наличие защитного подноска",

    # СИЗ / спецодежда
    "Класс защиты",
    "Тип защиты",
    "Назначение",
    "Температурный диапазон",
    "Стойкость к химическим воздействиям",
    "Стойкость к влаге",

    # Респираторы / противогазы / фильтры
    "Тип фильтра",
    "Степень фильтрации",
    "Срок службы",
    "Совместимость со средствами защиты",

    # Шины
    "Размерность шины",
    "Ширина профиля",
    "Высота профиля",
    "Диаметр посадочный",
    "Индекс нагрузки",
    "Индекс скорости",
    "Сезонность шины",
    "Тип протектора",
    "Наличие шипов",
    "Камерность",

    # Прочее
    "Объем",
    "Масса",
    "Материал корпуса",
]

# Для удобного нормализованного сопоставления
def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


CANONICAL_MAP: Dict[str, str] = {norm(a): a for a in CANONICAL_ATTRS}


# ------------------------------
# SYSTEM PROMPT
# ------------------------------

SYSTEM_TEXT = (
    "Ты — эксперт по характеристикам товаров в e-commerce. "
    "Тебе дают название категории на русском. "
    "Есть список возможных характеристик (ниже). "
    "Нужно выбрать из этого списка 3–5 наиболее важных характеристик "
    "для заданной категории.\n\n"
    "Важно:\n"
    "- выбирай ТОЛЬКО из списка ниже;\n"
    "- не придумывай новых характеристик;\n"
    "- пиши только выбранные названия, по одному на строку;\n"
    "- без нумерации, без комментариев."
)


def build_prompt(category_name: str) -> str:
    attrs_list = "\n".join(f"- {a}" for a in CANONICAL_ATTRS)
    return (
        f"{SYSTEM_TEXT}\n\n"
        f"Список возможных характеристик:\n"
        f"{attrs_list}\n\n"
        f"Категория: {category_name}\n\n"
        f"Выбранные характеристики:\n"
    )


def clean_and_filter_response(text: str) -> List[str]:
    """
    1) Разбиваем ответ на строки.
    2) Чистим от '1.', '-', '•' и т.п.
    3) Оставляем только строки, которые совпадают с каноническим списком.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out: List[str] = []

    for line in lines:
        # убираем нумерацию/маркеры
        line = re.sub(r"^[\-\*\d\.\)\s]+", "", line).strip()
        if not line:
            continue

        key = norm(line)
        if key in CANONICAL_MAP:
            out.append(CANONICAL_MAP[key])

    # максимум 5
    # + уберем дубликаты, сохранив порядок
    seen = set()
    final = []
    for a in out:
        if a not in seen:
            seen.add(a)
            final.append(a)
        if len(final) >= 5:
            break

    return final


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
        print(f"[{i}/{len(categories)}] Категория: {cat}")
        prompt = build_prompt(cat)

        gen = pipe(
            prompt,
            do_sample=False,
            temperature=0.0,
            eos_token_id=tokenizer.eos_token_id,
        )[0]["generated_text"]

        attrs = clean_and_filter_response(gen)

        records.append({
            "category": cat,
            "attributes": "; ".join(attrs),
        })

    out_df = pd.DataFrame(records)
    out_df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")

    print(f"\nГотово! Результат сохранен в: {OUT_PATH}")
    print("\nПервые 10 строк:")
    print(out_df.head(10))


if __name__ == "__main__":
    main()
