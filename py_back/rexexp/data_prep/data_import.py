import pandas as pd
import os

ITEMS_PATH=os.path.join('py_back','rexexp','data','Исходники.xlsx')
RESULT_PATH=os.path.join('py_back','rexexp','data','result_itr1.csv')

# Загружаем данные из Excel и сохраняем в CSV
try:
    df = pd.read_excel(ITEMS_PATH)
    df.to_csv(RESULT_PATH, index=False)
    print("Данные успешно конвертированы из Excel в CSV!")
except FileNotFoundError:
    print("Excel файл не найден")
    # Если файл не найден, создаем пустую структуру для демонстрации
    df = pd.DataFrame()

# Базовый анализ данных
print("=== БАЗОВЫЙ АНАЛИЗ ДАННЫХ ===")
print(f"Размер данных: {df.shape}")
print(f"Колонки: {list(df.columns)}")

print("\nПервые 5 строк:")
print(df.head())

print("\nИнформация о данных:")
print(df.info())

print("\nСтатистика по числовым колонкам:")
print(df.describe())

# Анализ категорий (7-й столбец)
if len(df.columns) >= 7:
    category_col = df.columns[6]
    print(f"\nАнализ категорий ({category_col}):")
    print(f"Уникальные категории: {df[category_col].unique()}")
    print(f"Количество уникальных категорий: {df[category_col].nunique()}")
else:
    print(f"\nВ данных меньше 7 колонок. Доступно: {len(df.columns)}")

print("\nПропущенные значения:")
print(df.isnull().sum())