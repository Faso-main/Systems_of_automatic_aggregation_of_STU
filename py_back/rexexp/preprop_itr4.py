import pandas as pd
import re

# Загружаем данные
df = pd.read_csv('py_back/rexexp/data/result_itr3.csv')

print("=== ПЛАН ПРЕДОБРАБОТКИ ДАННЫХ ===")

# 1. id - оставляем как есть
print("1. id_сте: ✓ Уникальные - оставляем как есть")

# 2. названия - нормализуем
print("\n2. названия_сте: Нормализация")
def normalize_name(name):
    if pd.isna(name):
        return ""
    # Приводим к нижнему регистру, убираем лишние пробелы
    name = str(name).lower().strip()
    # Убираем множественные пробелы
    name = re.sub(r'\s+', ' ', name)
    return name

df['название_сте_норм'] = df['название_сте'].apply(normalize_name)

# 3. ссылки - оставляем как есть, но проверяем формат
print("\n3. ссылки_на_картинку: ✓ Оставляем как есть")

# 4. модель - ПЕРЕНОСИМ В ХАРАКТЕРИСТИКИ
print("\n4. модель: ⚠ ПЕРЕНОСИМ В ХАРАКТЕРИСТИКИ")

# Функция для добавления модели в характеристики
def add_model_to_specs(row):
    model = row['модель']
    if pd.notna(model) and str(model).strip() and str(model).strip().lower() not in ['nan', 'none', '']:
        # Находим первую пустую spec колонку
        spec_cols = [col for col in df.columns if col.startswith('spec')]
        for col in spec_cols:
            if pd.isna(row[col]) or str(row[col]).strip() == '':
                return f"Модель: {model}"
    return None

# Добавляем модель как характеристику
df['модель_как_характеристика'] = df.apply(add_model_to_specs, axis=1)

# 5. страна - нормализуем и объединяем Кореи
print("\n5. страна_происхождения: Нормализация стран")

def normalize_country(country):
    if pd.isna(country):
        return ""
    
    country = str(country).strip()
    
    # Объединяем Кореи
    if 'корея' in country.lower():
        if 'север' in country.lower():
            return 'КНДР'
        elif 'юж' in country.lower():
            return 'Республика Корея'
        else:
            return 'Корея'  # если не указано какая
    
    # Нормализация других стран
    country_mapping = {
        'россия': 'Россия',
        'рф': 'Россия',
        'российская федерация': 'Россия',
        'сша': 'США',
        'соединенные штаты америки': 'США',
        'usa': 'США',
        'китай': 'Китай',
        'china': 'Китай',
        'германия': 'Германия',
        'germany': 'Германия',
        'франция': 'Франция',
        'france': 'Франция',
        'япония': 'Япония',
        'japan': 'Япония'
    }
    
    # Если страна в маппинге - возвращаем нормализованное значение
    for key, value in country_mapping.items():
        if key in country.lower():
            return value
    
    return country

df['страна_норм'] = df['страна_происхождения'].apply(normalize_country)

# 6. производитель - нормализуем названия
print("\n6. производитель: Нормализация названий компаний")

def normalize_manufacturer(manufacturer):
    if pd.isna(manufacturer):
        return ""
    
    manufacturer = str(manufacturer).strip()
    
    # Приводим к нижнему регистру для обработки
    lower_manuf = manufacturer.lower()
    
    # Нормализация ООО/ОБЩЕСТВО
    if 'общество с ограниченной ответственностью' in lower_manuf:
        manufacturer = manufacturer.replace('ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ', 'ООО')
    elif 'ооо' in lower_manuf and 'общество' not in lower_manuf:
        # Убедимся что ООО в начале
        if not manufacturer.startswith('ООО'):
            manufacturer = manufacturer.replace('ООО', '').strip()
            manufacturer = f"ООО {manufacturer}"
    
    # Убираем лишние кавычки
    manufacturer = manufacturer.replace('""', '"').replace('"', '')
    
    # Стандартизируем пробелы
    manufacturer = re.sub(r'\s+', ' ', manufacturer)
    
    return manufacturer.strip()

df['производитель_норм'] = df['производитель'].apply(normalize_manufacturer)

# 7. категории - оставляем как есть
print("\n7. категории: ✓ ID и названия в порядке")

# 8. характеристики - анализируем и нормализуем
print("\n8. характеристики: Анализ и нормализация")

def analyze_specs(row):
    """Анализирует характеристики и возвращает нормализованный словарь"""
    spec_cols = [col for col in df.columns if col.startswith('spec')]
    specs = {}
    
    for col in spec_cols:
        if pd.notna(row[col]) and str(row[col]).strip():
            spec_str = str(row[col]).strip()
            if ':' in spec_str:
                key, value = spec_str.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                # Нормализация ключей
                key_normalized = normalize_spec_key(key)
                specs[key_normalized] = value
    
    return specs

def normalize_spec_key(key):
    """Нормализует ключи характеристик"""
    key = key.lower().strip()
    
    # Маппинг синонимов
    key_mapping = {
        'ширина профиля': 'ширина',
        'номинальная ширина профиля': 'ширина', 
        'высота профиля': 'высота',
        'посадочный диаметр': 'диаметр',
        'номинальный посадочный диаметр обода': 'диаметр',
        'индекс скорости': 'индекс_скорости',
        'индекс нагрузки': 'индекс_нагрузки',
        'категория использования шины': 'сезонность',
        'назначение пневматических шин': 'назначение',
        'тип конструкции пневматических шин': 'конструкция'
    }
    
    return key_mapping.get(key, key)

# Применяем нормализацию
spec_cols = [col for col in df.columns if col.startswith('spec')]
print(f"Всего колонок с характеристиками: {len(spec_cols)}")

# Создаем финальный DataFrame для экспорта
print("\n=== СОЗДАНИЕ ФИНАЛЬНОГО ДАТАСЕТА ===")

# Создаем новый DataFrame с обработанными данными
final_df = pd.DataFrame()

# Копируем основные колонки
final_df['id_сте'] = df['id_сте']
final_df['название_сте'] = df['название_сте_норм']
final_df['ссылка_на_картинку'] = df['ссылка_на_картинку']
final_df['id_категории'] = df['id_категории']
final_df['название_категории'] = df['название_категории']
final_df['страна_происхождения'] = df['страна_норм']
final_df['производитель'] = df['производитель_норм']

# Копируем оригинальные характеристики
for col in spec_cols:
    final_df[col] = df[col]

# Добавляем модель как характеристику если есть
for idx, row in df.iterrows():
    if pd.notna(row['модель_как_характеристика']):
        # Находим первую пустую spec колонку
        for col in spec_cols:
            if pd.isna(final_df.loc[idx, col]) or str(final_df.loc[idx, col]).strip() == '':
                final_df.loc[idx, col] = row['модель_как_характеристика']
                break

# Сохраняем результат
FINAL_PATH = 'py_back/rexexp/data/final_preprocessed.csv'
final_df.to_csv(FINAL_PATH, index=False, encoding='utf-8')

print(f"Финальный датасет сохранен: {FINAL_PATH}")

# Статистика по обработке
print("\n=== СТАТИСТИКА ОБРАБОТКИ ===")
print(f"Обработано записей: {len(final_df)}")
print(f"Уникальных стран: {final_df['страна_происхождения'].nunique()}")
print(f"Уникальных производителей: {final_df['производитель'].nunique()}")
print(f"Записей с нормализованными названиями: {final_df['название_сте'].notna().sum()}")

# Покажем примеры до и после
print("\n=== ПРИМЕРЫ ОБРАБОТКИ ===")
sample_idx = 0
print(f"ДО обработки:")
print(f"  Название: {df.iloc[sample_idx]['название_сте']}")
print(f"  Страна: {df.iloc[sample_idx]['страна_происхождения']}")
print(f"  Производитель: {df.iloc[sample_idx]['производитель']}")
print(f"  Модель: {df.iloc[sample_idx]['модель']}")

print(f"ПОСЛЕ обработки:")
print(f"  Название: {final_df.iloc[sample_idx]['название_сте']}")
print(f"  Страна: {final_df.iloc[sample_idx]['страна_происхождения']}")
print(f"  Производитель: {final_df.iloc[sample_idx]['производитель']}")