#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
semantic_attr_selector.py

Инструмент: по названию категории выбирает 3–5 ключевых характеристик
на русском, используя SBERT-модель "ai-forever/sbert_large_mt_nlu_ru".

Ожидается файл result_itr4_test.csv со столбцами:
- "название_категории"
- spec1..spec31 со строками вида "Ключ: Значение"

Запуск:
    python semantic_attr_selector.py

На выходе в консоль: для первых N категорий → топ-5 характеристик.
"""

import re
from typing import List, Tuple

import pandas as pd
import torch
from sentence_transformers import SentenceTransformer


CSV_PATH = "py_back/rexexp/data/result_itr4.csv"
MODEL_NAME = "ai-forever/sbert_large_mt_nlu_ru"


def load_candidates_from_csv(csv_path: str,
                             min_len: int = 3,
                             max_len: int = 60) -> List[str]:
    """
    Собираем возможные названия характеристик из spec*.
    Берём только левую часть до ':', чистим и фильтруем по длине.
    """
    # если нужна кодировка: encoding="utf-8-sig"
    df = pd.read_csv(csv_path)

    spec_cols = [c for c in df.columns if str(c).startswith("spec")]
    if not spec_cols:
        raise RuntimeError("Не найдены колонки spec* в CSV.")

    melted = df.melt(value_vars=spec_cols, value_name="spec").dropna(subset=["spec"])

    # делим "Ключ: Значение"
    parts = melted["spec"].astype(str).str.split(":", 1, expand=True)
    keys = parts[0].astype(str).str.strip()

    # фильтрация по длине и простейшему шуму
    keys = keys[keys.str.len().between(min_len, max_len)]
    # выкидываем чисто числовые/технические
    keys = keys[~keys.str.match(r"^[0-9\-\.\s]+$")]
    # лёгкая чистка
    keys = keys.str.replace(r"\s+", " ", regex=True)
    keys = keys.str.replace(" ", " ", regex=False)  # неразрывные пробелы
    keys = keys.drop_duplicates()

    candidates = keys.tolist()
    return candidates


class SemanticAttrSelector:
    def __init__(self,
                 model_name: str = MODEL_NAME,
                 device: str | None = None):
        """
        model_name: имя SBERT-модели
        device: 'cuda', 'cpu' или None (автоопределение)
        """
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device

        print(f"Загружаю модель {model_name!r} на {device}...")
        self.model = SentenceTransformer(model_name, device=device)

        self.attr_texts: List[str] = []
        self.attr_embs: torch.Tensor | None = None

    def fit_attributes(self, attr_texts: List[str]):
        """
        Передаём список названий характеристик-кандидатов,
        считаем эмбеддинги и храним их.
        """
        self.attr_texts = attr_texts
        print(f"Считаю эмбеддинги для {len(attr_texts)} кандидатов характеристик...")
        embs = self.model.encode(
            attr_texts,
            convert_to_tensor=True,
            normalize_embeddings=True
        )
        self.attr_embs = embs
        print("Готово.")

    def suggest(self, category_name: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Вход: название категории.
        Выход: список (характеристика, score) длиной до top_k.
        """
        if not self.attr_texts or self.attr_embs is None:
            raise RuntimeError("Сначала вызови fit_attributes(...)")

        cat_emb = self.model.encode(
            [category_name],
            convert_to_tensor=True,
            normalize_embeddings=True
        )
        # косинус при нормализованных векторах = скалярное произведение
        scores = torch.matmul(cat_emb, self.attr_embs.T)[0]
        k = min(top_k, len(self.attr_texts))
        topk = torch.topk(scores, k=k)

        result: List[Tuple[str, float]] = []
        for idx, score in zip(topk.indices.tolist(), topk.values.tolist()):
            result.append((self.attr_texts[idx], float(score)))
        return result


def build_selector_from_file(csv_path: str,
                             model_name: str = MODEL_NAME
                             ) -> SemanticAttrSelector:
    """
    1) Собирает кандидатов характеристик из CSV.
    2) Строит по ним эмбеддинги.
    3) Возвращает готовый селектор.
    """
    candidates = load_candidates_from_csv(csv_path)
    print(f"Найдено {len(candidates)} кандидатов характеристик из файла {csv_path}")
    # Можно тут же чуть подрезать список, если хочешь:
    # candidates = [c for c in candidates if not c.lower().startswith("butch")]
    selector = SemanticAttrSelector(model_name=model_name)
    selector.fit_attributes(candidates)
    return selector


def suggest_attrs_for_category(selector: SemanticAttrSelector,
                               category_name: str,
                               top_k: int = 5) -> List[str]:
    """
    Упрощённая обёртка: возвращаем только названия характеристик.
    """
    pairs = selector.suggest(category_name, top_k=top_k)
    return [name for name, score in pairs]


def main():
    # 1. строим селектор по твоему файлу
    selector = build_selector_from_file(CSV_PATH, model_name=MODEL_NAME)

    # 2. читаем категории из файла
    df = pd.read_csv(CSV_PATH)
    if "название_категории" not in df.columns:
        raise RuntimeError("В CSV нет столбца 'название_категории'.")

    categories = df["название_категории"].dropna().unique().tolist()

    print(f"\nВсего уникальных категорий: {len(categories)}")
    print("Покажу первые 15 для примера:\n")

    for cat in categories[:15]:
        attrs = suggest_attrs_for_category(selector, cat, top_k=5)
        print(f"Категория: {cat}")
        for a in attrs:
            print(f"  - {a}")
        print("-" * 60)


if __name__ == "__main__":
    main()
