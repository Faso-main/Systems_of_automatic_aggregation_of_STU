import pandas as pd
import os
from collections import Counter

ITEMS_PATH = os.path.join('py_back','rexexp','data','result_itr1.csv')
OUTPUT_PATH = os.path.join('py_back','rexexp','data','detailed_category_analysis.txt')

# Загружаем данные
df = pd.read_csv(ITEMS_PATH)

# Функция для парсинга характеристик (сохраняем все как есть)
def parse_characteristics(characteristics_str):
    if pd.isna(characteristics_str):
        return {}
    
    characteristics = {}
    try:
        # Разделяем по точке с запятой, но сохраняем оригинальные значения
        pairs = characteristics_str.split(';')
        for pair in pairs:
            if ':' in pair:
                key, value = pair.split(':', 1)
                # Сохраняем оригинальные ключи и значения без изменений
                characteristics[key.strip()] = value.strip()
    except Exception as e:
        # Если есть ошибки парсинга, сохраняем оригинальную строку для анализа
        characteristics['_parse_error'] = characteristics_str
    return characteristics

# Применяем парсинг характеристик
df['parsed_characteristics'] = df['характеристики'].apply(parse_characteristics)

# Анализ структуры характеристик
print("=== АНАЛИЗ СТРУКТУРЫ ХАРАКТЕРИСТИК ===")
print(f"Всего записей: {len(df)}")
print(f"Записей с характеристиками: {df['характеристики'].notna().sum()}")
print(f"Записей без характеристик: {df['характеристики'].isna().sum()}")

# Анализ длины характеристик
df['chars_count'] = df['parsed_characteristics'].apply(len)
print(f"\nСтатистика по количеству характеристик на товар:")
print(f"Максимум: {df['chars_count'].max()}")
print(f"Минимум: {df['chars_count'].min()}")
print(f"Среднее: {df['chars_count'].mean():.1f}")
print(f"Медиана: {df['chars_count'].median()}")

# Анализ всех уникальных ключей характеристик
all_keys = []
for chars_dict in df['parsed_characteristics']:
    all_keys.extend(chars_dict.keys())

key_freq = Counter(all_keys)
print(f"\nВсего уникальных ключей характеристик: {len(key_freq)}")
print("Топ-20 самых частых ключей:")
for key, count in key_freq.most_common(20):
    print(f"  - {key}: {count} упоминаний")

# Сохраняем детальный анализ в файл
with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    f.write("=== ДЕТАЛЬНЫЙ АНАЛИЗ ХАРАКТЕРИСТИК ПО КАТЕГОРИЯМ ===\n\n")
    
    # Анализ по категориям
    categories = df['id категории'].unique()
    f.write(f"Всего категорий: {len(categories)}\n\n")
    
    for category_id in categories:
        category_data = df[df['id категории'] == category_id]
        category_name = category_data['название категории'].iloc[0]
        
        f.write(f"Категория: {category_id} - {category_name}\n")
        f.write(f"Количество товаров: {len(category_data)}\n")
        
        # Собираем все характеристики для категории
        category_keys = []
        category_values = {}
        
        for chars_dict in category_data['parsed_characteristics']:
            for key, value in chars_dict.items():
                category_keys.append(key)
                if key not in category_values:
                    category_values[key] = []
                category_values[key].append(value)
        
        # Анализ ключей
        key_counter = Counter(category_keys)
        f.write(f"Уникальных ключей характеристик: {len(key_counter)}\n")
        
        # Топ ключей по частоте
        f.write("Топ-15 ключей по частоте:\n")
        for key, count in key_counter.most_common(15):
            coverage = count / len(category_data)
            unique_vals = len(set(category_values[key]))
            f.write(f"  - {key}: {count} товаров ({coverage:.1%}), {unique_vals} уникальных значений\n")
        
        # Анализ значений для топ-5 ключей
        f.write("\nДетальный анализ топ-5 ключей:\n")
        for key, count in key_counter.most_common(5):
            values = category_values[key]
            value_counter = Counter(values)
            f.write(f"  {key} (всего значений: {len(value_counter)}):\n")
            for val, val_count in value_counter.most_common(5):
                f.write(f"    - '{val}': {val_count} раз\n")
            if len(value_counter) > 5:
                f.write(f"    - ... и еще {len(value_counter) - 5} других значений\n")
        
        f.write("\n" + "="*80 + "\n\n")

print(f"\nДетальный анализ сохранен в: {OUTPUT_PATH}")

# Дополнительный анализ: создаем полную таблицу характеристик
print("Создаем полную таблицу характеристик...")

full_characteristics_data = []

for idx, row in df.iterrows():
    item_id = row['id сте']
    item_name = row['название сте']
    category_id = row['id категории']
    category_name = row['название категории']
    characteristics_dict = row['parsed_characteristics']
    
    for char_key, char_value in characteristics_dict.items():
        full_characteristics_data.append({
            'id_сте': item_id,
            'название_сте': item_name,
            'id_категории': category_id,
            'название_категории': category_name,
            'ключ_характеристики': char_key,
            'значение_характеристики': char_value,
            'оригинальная_строка': row['характеристики']  # Сохраняем оригинал для reference
        })

# Сохраняем полную таблицу
if full_characteristics_data:
    full_chars_df = pd.DataFrame(full_characteristics_data)
    full_chars_path = os.path.join('py_back','rexexp','data','full_characteristics.csv')
    full_chars_df.to_csv(full_chars_path, index=False, encoding='utf-8')
    print(f"Полная таблица характеристик сохранена в: {full_chars_path}")
    print(f"Всего записей характеристик: {len(full_characteristics_data)}")
    
    # Статистика по полной таблице
    print(f"\nСтатистика полной таблицы:")
    print(f"Уникальных ключей: {full_chars_df['ключ_характеристики'].nunique()}")
    print(f"Уникальных значений: {full_chars_df['значение_характеристики'].nunique()}")

# Анализ качества данных
print("\n=== АНАЛИЗ КАЧЕСТВА ДАННЫХ ===")
print("Примеры характеристик для проверки парсинга:")
sample_indices = df[df['chars_count'] > 0].index[:3]
for idx in sample_indices:
    original = df.loc[idx, 'характеристики']
    parsed = df.loc[idx, 'parsed_characteristics']
    print(f"\nОригинал: {original}")
    print(f"Разобрано: {parsed}")
    print(f"Количество характеристик: {len(parsed)}")