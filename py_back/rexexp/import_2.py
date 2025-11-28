import pandas as pd

# Простая конвертация CSV в Excel
df = pd.read_csv('py_back/rexexp/data/result_itr4.csv')
df.to_excel('py_back/rexexp/data/final_for_import.xlsx', index=False)

print("✅ CSV успешно конвертирован в Excel")