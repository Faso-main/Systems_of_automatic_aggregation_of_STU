import pandas as pd
import os

ITEMS_PATH = os.path.join('py_back','rexexp','data','result_itr1.csv')
OUTPUT_PATH = os.path.join('py_back','rexexp','data','result_itr3.csv')

# Загружаем данные
df = pd.read_csv(ITEMS_PATH)

# Функция для парсинга характеристик
def parse_characteristics(characteristics_str):
    if pd.isna(characteristics_str):
        return {}
    
    characteristics = {}
    try:
        pairs = characteristics_str.split(';')
        for pair in pairs:
            if ':' in pair:
                key, value = pair.split(':', 1)
                characteristics[key.strip()] = value.strip()
    except Exception as e:
        characteristics['_parse_error'] = str(e)
    return characteristics

print("Разбираем характеристики...")

# Найдем максимальное количество характеристик в одной строке
max_specs = 0
for idx, row in df.iterrows():
    characteristics_dict = parse_characteristics(row['характеристики'])
    max_specs = max(max_specs, len(characteristics_dict))

print(f"Максимальное количество характеристик в одном товаре: {max_specs}")

# Создаем список для разобранных данных
exploded_data = []

for idx, row in df.iterrows():
    # Базовые данные из оригинальной строки
    base_data = {
        'id_сте': row['id сте'],
        'название_сте': row['название сте'],
        'ссылка_на_картинку': row['ссылка на картинку сте'],
        'модель': row['модель'],
        'страна_происхождения': row['страна происхождения'],
        'производитель': row['производитель'],
        'id_категории': row['id категории'],
        'название_категории': row['название категории']
    }
    
    # Парсим характеристики
    characteristics_dict = parse_characteristics(row['характеристики'])
    
    # Добавляем характеристики как spec1, spec2, spec3...
    spec_num = 1
    for key, value in characteristics_dict.items():
        base_data[f'spec{spec_num}'] = f"{key}: {value}"
        spec_num += 1
    
    # Заполняем оставшиеся spec колонки пустыми значениями
    while spec_num <= max_specs:
        base_data[f'spec{spec_num}'] = None
        spec_num += 1
    
    exploded_data.append(base_data)

# Создаем DataFrame
exploded_df = pd.DataFrame(exploded_data)

# Сохраняем результат
exploded_df.to_csv(OUTPUT_PATH, index=False, encoding='utf-8')

print(f"Готово! Файл сохранен: {OUTPUT_PATH}")
print(f"Исходное количество строк: {len(df)}")
print(f"Результирующее количество строк: {len(exploded_df)}")
print(f"Количество колонок в результате: {len(exploded_df.columns)}")

# Посмотрим на статистику по spec колонкам
spec_columns = [col for col in exploded_df.columns if col.startswith('spec')]

print(f"\nСоздано spec колонок: {len(spec_columns)}")

# Статистика по заполненности spec колонок
print("\nСтатистика по spec колонкам:")
spec_stats = []
for col in spec_columns:
    non_null_count = exploded_df[col].notna().sum()
    coverage = non_null_count / len(exploded_df)
    spec_stats.append((col, non_null_count, coverage))

# Сортируем по номеру spec
spec_stats.sort(key=lambda x: int(x[0][4:]))

for col, count, coverage in spec_stats:
    print(f"  {col}: {count} записей ({coverage:.1%})")

# Покажем пример результата
print(f"\nПример разбора первых 3 строк:")
for i in range(min(3, len(exploded_df))):
    print(f"\nСтрока {i+1}: {exploded_df.iloc[i]['название_сте']}")
    specs = [exploded_df.iloc[i][col] for col in spec_columns if pd.notna(exploded_df.iloc[i][col])]
    for j, spec in enumerate(specs, 1):
        print(f"  spec{j}: {spec}")

# Базовая информация о данных
print(f"\nОбщая статистика:")
print(f"Всего товаров: {len(exploded_df)}")
print(f"Товаров с характеристиками: {exploded_df[spec_columns[0]].notna().sum()}")
print(f"Товаров без характеристик: {exploded_df[spec_columns[0]].isna().sum()}")