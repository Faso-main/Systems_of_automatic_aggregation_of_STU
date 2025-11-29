#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
qwen25_category_attrs.py

Мозг: Qwen2.5-7B-Instruct (локально через transformers).

Логика:
1) Берём категории из py_back/rexexp/data/result_itr4.csv (колонка "название_категории").
2) Для каждой категории определяем домен (tyres, clothes, shoes, gloves, etc.).
3) Для домена есть список атрибутов-кандидатов.
4) Qwen2.5 получает:
   - system-инструкцию,
   - домен,
   - категорию,
   - список атрибутов
   и должен вернуть РОВНО 3 в формате JSON-массива строк.
5) Результат пишем в py_back/rexexp/data/category_attrs_qwen25.csv.

Зависимости:
    pip install transformers accelerate torch pandas
"""

import re
import json
from typing import List, Dict

import pandas as pd
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM


# ----------- Пути -----------

CSV_PATH = "py_back/rexexp/data/result_itr4.csv"
OUT_PATH = "py_back/rexexp/data/category_attrs_qwen25.csv"

# Модель Qwen 2.5 (можешь подставить локальный путь)
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"


# ----------- Домены и атрибуты-кандидаты -----------

DOMAIN_ATTRS: Dict[str, List[str]] = {
    "clothes": [
        "Размер",
        "Пол",
        "Цвет",
        "Сезон",
        "Состав ткани",
        "Тип изделия",
    ],
    "underwear": [
        "Размер",
        "Пол",
        "Состав ткани",
        "Назначение",
        "Сезон",
    ],
    "shoes": [
        "Размер обуви",
        "Пол",
        "Сезонность обуви",
        "Материал верха",
        "Материал подошвы",
        "Назначение обуви",
    ],
    "gloves": [
        "Размер",
        "Материал",
        "Тип защиты",
        "Назначение",
        "Класс защиты",
    ],
    "headwear": [
        "Размер",
        "Пол",
        "Сезон",
        "Материал",
        "Цвет",
    ],
    "tyres": [
        "Размерность шины",
        "Ширина профиля",
        "Высота профиля",
        "Диаметр посадочный",
        "Индекс нагрузки",
        "Индекс скорости",
        "Сезонность шины",
        "Камерность",
    ],
    "respirators": [
        "Тип фильтра",
        "Степень фильтрации",
        "Класс защиты",
        "Срок службы",
        "Совместимость со средствами защиты",
    ],
    "eye_face_ppe": [
        "Тип защиты",
        "Материал",
        "Наличие покрытия от запотевания",
        "Наличие УФ-защиты",
        "Размер / регулировка",
    ],
    "hearing_ppe": [
        "Уровень шумоподавления",
        "Тип средства защиты",
        "Регулировка",
        "Совместимость с другим СИЗ",
        "Материал амбушюр/вкладышей",
    ],
    "fall_ppe": [
        "Тип системы (привязь/строп/карабины)",
        "Длина стропа",
        "Максимальная нагрузка",
        "Соответствие стандартам",
        "Материал лент/строп",
    ],
    "spec_clothes": [
        "Назначение",
        "Класс защиты",
        "Температурный диапазон",
        "Стойкость к химическим воздействиям",
        "Материал верха",
    ],
    "cosmetics": [
        "Тип средства",
        "Назначение",
        "Объем",
        "Тип кожи / область применения",
        "Активные компоненты",
    ],
    "lighting": [
        "Тип источника света",
        "Мощность",
        "Световой поток",
        "Тип питания (батарея/сеть)",
        "Степень защиты IP",
    ],
    "textile": [
        "Размер",
        "Материал",
        "Плотность ткани",
        "Цвет",
        "Назначение",
    ],
    "bags": [
        "Назначение",
        "Объем",
        "Материал",
        "Размер",
        "Тип застежки",
    ],
    "med_sets": [
        "Состав набора",
        "Область применения",
        "Стерильность",
        "Срок годности",
        "Материал изделий",
    ],
    "generic": [
        "Назначение",
        "Материал",
        "Размер",
        "Цвет",
        "Масса/объем",
    ],
}


def detect_domain(cat: str) -> str:
    s = cat.lower()

    if any(w in s for w in ["шины", "шина", "покрыш", "камера"]):
        return "tyres"

    if any(w in s for w in ["обувь", "ботинк", "туфл", "сапог", "галош", "кроссовк"]):
        return "shoes"

    if any(w in s for w in ["перчатк", "рукавиц"]):
        return "gloves"

    if any(w in s for w in ["шапк", "шапочк", "уборы головные", "подшлемник"]):
        return "headwear"

    if any(w in s for w in [
        "одежда", "брюки", "юбк", "пальто", "куртк", "ветровк",
        "джемпер", "свитер", "жилет", "сорочки", "пиджак", "пижам",
        "плащ", "футболки", "блузк", "халат"
    ]):
        return "clothes"

    if any(w in s for w in ["белье", "бельевые изделия", "носки", "подследники", "колготк", "легинс"]):
        return "underwear"

    if "специальная" in s or "элементы специальной одежды" in s or "боевая одежда пожарного" in s:
        return "spec_clothes"
    if "защиты от" in s or "защита от" in s:
        return "spec_clothes"

    if any(w in s for w in ["респиратор", "противогаз"]):
        return "respirators"
    if any(w in s for w in ["фильтры для", "патроны и фильтры", "фильтры сменные"]):
        return "respirators"

    if any(w in s for w in ["очки защитные", "щитки лицевые", "щиток лицевой"]):
        return "eye_face_ppe"

    if "противошумн" in s:
        return "hearing_ppe"

    if "падения с высоты" in s or "страховочная привязь" in s or "стропы" in s:
        return "fall_ppe"

    if any(w in s for w in ["кремы для рук", "гели для ухода", "мыло туалетное", "защиты кожи"]):
        return "cosmetics"

    if "осветительные" in s or "приборы осветительные" in s:
        return "lighting"

    if any(w in s for w in ["полотенца", "текстиль общего назначения", "салфетки"]):
        return "textile"

    if "сумки" in s:
        return "bags"

    if any(w in s for w in ["медицинские наборы", "общебольничного оборудования", "хирургического оборудования"]):
        return "med_sets"

    return "generic"


SYSTEM_PROMPT = (
    "Ты — эксперт по характеристикам товаров в e-commerce. "
    "Тебе дают название категории и домен. "
    "Также дан список возможных характеристик для этого домена. "
    "Нужно выбрать РОВНО ТРИ наиболее важных характеристики для этой категории.\n\n"
    "Правила:\n"
    "- выбирай ТОЛЬКО из предложенного списка;\n"
    "- не придумывай новых характеристик;\n"
    "- ответ верни строго в виде JSON-массива строк, без комментариев. Пример:\n"
    '  [\"Размер\", \"Цвет\", \"Состав ткани\"]'
)


def build_user_prompt(category: str, domain: str, attrs: List[str]) -> str:
    attrs_list = "\n".join(f"- {a}" for a in attrs)
    return (
        f"Домен: {domain}\n"
        f"Категория: {category}\n\n"
        f"Доступные характеристики:\n"
        f"{attrs_list}\n\n"
        f"Верни JSON-массив из ровно трёх выбранных характеристик."
    )


def extract_json_array(text: str) -> List[str]:
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    chunk = text[start:end+1]
    try:
        data = json.loads(chunk)
        if isinstance(data, list):
            return [str(x) for x in data]
    except json.JSONDecodeError:
        return []
    return []


def main():
    print(f"Загружаю Qwen 2.5 модель: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        device_map="auto",
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else "auto",
        trust_remote_code=True,
    )

    print(f"Читаю CSV: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)

    if "название_категории" not in df.columns:
        raise RuntimeError("В CSV нет столбца 'название_категории'")

    categories = sorted(df["название_категории"].dropna().unique().tolist())
    print(f"Найдено категорий: {len(categories)}")

    records = []

    for i, cat in enumerate(categories, start=1):
        domain = detect_domain(cat)
        candidates = DOMAIN_ATTRS.get(domain, DOMAIN_ATTRS["generic"])

        print(f"[{i}/{len(categories)}] {cat}  --> домен={domain}")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(cat, domain, candidates)},
        ]

        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        inputs = tokenizer(
            prompt,
            return_tensors="pt"
        ).to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=128,
                do_sample=False,
                temperature=0.0,
                eos_token_id=tokenizer.eos_token_id,
            )

        gen_text = tokenizer.decode(outputs[0], skip_special_tokens=True)

        attrs = extract_json_array(gen_text)
        if len(attrs) != 3:
            # если Qwen накосячил — fallback на первые 3 кандидата
            attrs = candidates[:3]

        records.append({
            "category": cat,
            "domain": domain,
            "attributes": "; ".join(attrs),
        })

    out_df = pd.DataFrame(records)
    out_df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")

    print(f"\nГотово. Результат сохранён в: {OUT_PATH}")
    print("\nПервые 20 строк:")
    print(out_df.head(20))


if __name__ == "__main__":
    main()
