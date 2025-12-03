# preprocess_all_v1.py
# Единый чистый пайплайн:
# 1) Исходники.xlsx -> нормализованный CSV result_itr4.csv
#
# Формат выхода (result_itr4.csv):
#   id_сте
#   название_сте          (нормализованное)
#   ссылка_на_картинку
#   id_категории
#   название_категории
#   страна_происхождения  (норм)
#   производитель         (норм)
#   spec1..specN          (строки "Ключ: Значение", включая "Модель: ...")

import os
from pathlib import Path
from typing import Dict

import pandas as pd
import re

# -------------------------
# НАСТРОЙКИ ПУТЕЙ
# -------------------------

BASE_DATA_DIR = Path("py_back") / "rexexp" / "data"

# Вход: Excel-исходник
ITEMS_XLSX = BASE_DATA_DIR / "Исходники.xlsx"

# Выход: финальный очищенный CSV под все дальнейшие пайплайны
OUTPUT_CSV = BASE_DATA_DIR / "result_itr4_test.csv"


# -------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# -------------------------

def parse_characteristics(characteristics_str: str) -> Dict[str, str]:
    """
    Разбирает строку характеристик вида:
        "Ширина: 215 мм; Высота: 55 %; ..."
    в словарь {ключ: значение}.
    """
    if pd.isna(characteristics_str):
        return {}

    characteristics: Dict[str, str] = {}
    try:
        pairs = str(characteristics_str).split(";")
        for pair in pairs:
            pair = pair.strip()
            if not pair:
                continue
            if ":" in pair:
                key, value = pair.split(":", 1)
                key = key.strip()
                value = value.strip()
                if key:
                    characteristics[key] = value
    except Exception:
        # В спорных случаях просто возвращаем пустой словарь — дальше модель все равно доучим
        return {}

    return characteristics


def normalize_name(name: str) -> str:
    """
    Нормализация названия товара:
    - нижний регистр
    - обрезка лишних пробелов
    """
    if pd.isna(name):
        return ""
    name = str(name).lower().strip()
    name = re.sub(r"\s+", " ", name)
    return name


def normalize_country(country: str) -> str:
    """
    Нормализация стран (РФ/Россия/РФ -> Россия, USA/США -> США и т.д.).
    Логика взята и слегка почищена из preprop_itr4.:contentReference[oaicite:1]{index=1}
    """
    if pd.isna(country):
        return ""

    country = str(country).strip()
    if not country:
        return ""

    low = country.lower()

    # Объединяем Кореи
    if "корея" in low:
        if "север" in low:
            return "КНДР"
        elif "юж" in low:
            return "Республика Корея"
        else:
            return "Корея"

    country_mapping = {
        "россия": "Россия",
        "рф": "Россия",
        "российская федерация": "Россия",

        "сша": "США",
        "соединенные штаты америки": "США",
        "usa": "США",

        "китай": "Китай",
        "china": "Китай",

        "германия": "Германия",
        "germany": "Германия",

        "франция": "Франция",
        "france": "Франция",

        "япония": "Япония",
        "japan": "Япония",
    }

    for key, norm in country_mapping.items():
        if key in low:
            return norm

    return country


def normalize_manufacturer(manufacturer: str) -> str:
    """
    Нормализация названия производителя:
    - приведение ООО / "Общество с ограниченной ответственностью" к одному виду;
    - убираем лишние кавычки и пробелы.
    Логика взята и упрощена из preprop_itr4.:contentReference[oaicite:2]{index=2}
    """
    if pd.isna(manufacturer):
        return ""

    manufacturer = str(manufacturer).strip()
    if not manufacturer:
        return ""

    lower_manuf = manufacturer.lower()

    # Нормализация ООО/ОБЩЕСТВО
    if "общество с ограниченной ответственностью" in lower_manuf:
        manufacturer = re.sub(
            r"(?i)общество с ограниченной ответственностью",
            "ООО",
            manufacturer,
        )
    elif "ооо" in lower_manuf and "общество" not in lower_manuf:
        # Убедимся, что ООО в начале
        if not manufacturer.upper().startswith("ООО"):
            manufacturer = manufacturer.replace("ООО", "")
            manufacturer = manufacturer.strip()
            manufacturer = f"ООО {manufacturer}".strip()

    # Убираем кавычки
    manufacturer = manufacturer.replace('""', '"')
    manufacturer = manufacturer.replace('"', "")

    # Стандартизируем пробелы
    manufacturer = re.sub(r"\s+", " ", manufacturer)

    return manufacturer.strip()


# -------------------------
# ОСНОВНОЙ ПАЙПЛАЙН
# -------------------------

def main():
    print("=== ЕДИНЫЙ ПРЕДОБРАБАТЫВАЮЩИЙ ПАЙПЛАЙН ===")
    print(f"Читаем Excel: {ITEMS_XLSX}")

    if not ITEMS_XLSX.exists():
        raise FileNotFoundError(f"Не найден исходный Excel: {ITEMS_XLSX}")

    # Ожидаем структуру, как была в result_itr1.csv:
    df_raw = pd.read_excel(ITEMS_XLSX)

    required_cols = [
        "id сте",
        "название сте",
        "ссылка на картинку сте",
        "модель",
        "страна происхождения",
        "производитель",
        "id категории",
        "название категории",
        "характеристики",
    ]
    missing = [c for c in required_cols if c not in df_raw.columns]
    if missing:
        raise ValueError(f"В Excel отсутствуют обязательные колонки: {missing}")

    print(f"Всего строк в исходниках: {len(df_raw)}")

    # -------------------------
    # 1. Посчитать максимум характеристик (specN)
    # -------------------------
    print("Считаем максимальное количество характеристик на товар...")

    max_specs = 0
    for val in df_raw["характеристики"]:
        chars = parse_characteristics(val)
        max_specs = max(max_specs, len(chars))

    print(f"Максимальное количество характеристик: {max_specs}")

    # -------------------------
    # 2. Собрать exploded DataFrame с колонками spec1..specN
    # -------------------------
    print("Формируем таблицу со spec1..specN...")

    exploded_rows = []

    for _, row in df_raw.iterrows():
        base = {
            "id_сте": row["id сте"],
            "название_сте": row["название сте"],
            "ссылка_на_картинку": row["ссылка на картинку сте"],
            "модель": row.get("модель", ""),
            "страна_происхождения": row.get("страна происхождения", ""),
            "производитель": row.get("производитель", ""),
            "id_категории": row["id категории"],
            "название_категории": row["название категории"],
        }

        chars_dict = parse_characteristics(row.get("характеристики", ""))

        spec_num = 1
        for key, value in chars_dict.items():
            base[f"spec{spec_num}"] = f"{key}: {value}"
            spec_num += 1

        while spec_num <= max_specs:
            base[f"spec{spec_num}"] = None
            spec_num += 1

        exploded_rows.append(base)

    exploded_df = pd.DataFrame(exploded_rows)

    print(f"После разбиения: {len(exploded_df)} строк, {len(exploded_df.columns)} колонок")

    # -------------------------
    # 3. Нормализация основных полей
    # -------------------------
    print("Нормализуем названия, страны, производителей...")

    exploded_df["название_сте_норм"] = exploded_df["название_сте"].apply(normalize_name)
    exploded_df["страна_норм"] = exploded_df["страна_происхождения"].apply(normalize_country)
    exploded_df["производитель_норм"] = exploded_df["производитель"].apply(normalize_manufacturer)

    # -------------------------
    # 4. Перенос "модель" в первую свободную spec*
    # -------------------------
    print('Переносим "модель" в первую свободную spec* (Модель: ...)')

    spec_cols = [c for c in exploded_df.columns if c.startswith("spec")]
    spec_cols.sort(key=lambda x: int(x[4:]))  # spec1, spec2, ...

    for idx, row in exploded_df.iterrows():
        model_val = str(row.get("модель", "")).strip()
        if not model_val or model_val.lower() in {"nan", "none"}:
            continue

        # проверяем, нет ли уже где-то "Модель:" в spec'ах
        already_has_model = False
        for col in spec_cols:
            val = row.get(col, None)
            if pd.isna(val) or not val:
                continue
            if str(val).lower().startswith("модель:"):
                already_has_model = True
                break

        if already_has_model:
            continue

        # ищем первую пустую spec*
        for col in spec_cols:
            val = row.get(col, None)
            if pd.isna(val) or not str(val).strip():
                exploded_df.at[idx, col] = f"Модель: {model_val}"
                break

    # -------------------------
    # 5. Формируем финальный DataFrame, совместимый с текущим пайплайном
    # -------------------------
    print("Собираем финальный датасет result_itr4.csv...")

    final_df = pd.DataFrame()
    final_df["id_сте"] = exploded_df["id_сте"]
    final_df["название_сте"] = exploded_df["название_сте_норм"]
    final_df["ссылка_на_картинку"] = exploded_df["ссылка_на_картинку"]
    final_df["id_категории"] = exploded_df["id_категории"]
    final_df["название_категории"] = exploded_df["название_категории"]
    final_df["страна_происхождения"] = exploded_df["страна_норм"]
    final_df["производитель"] = exploded_df["производитель_норм"]

    for col in spec_cols:
        final_df[col] = exploded_df[col]

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")

    print("\n=== ГОТОВО ===")
    print(f"Финальный файл сохранён: {OUTPUT_CSV}")
    print(f"Строк: {len(final_df)}, колонок: {len(final_df.columns)}")
    print(f"Уникальных категорий: {final_df['id_категории'].nunique()}")
    print(f"Уникальных стран: {final_df['страна_происхождения'].nunique()}")
    print(f"Уникальных производителей: {final_df['производитель'].nunique()}")


if __name__ == "__main__":
    main()
