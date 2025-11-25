import requests
import json
import pandas as pd
from typing import Dict, List, Any

class MosZakupkiAPIClient:
    
    def __init__(self, api_key: str):
        self.base_url = "https://api.zakupki.mos.ru/api/v1"
        self.session = requests.Session()
        self.api_key = api_key
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        })

    def try_different_approaches(self):
        """Пробуем разные подходы к API"""
        print("Тестирование различных методов доступа...")
        
        # 1. Пробуем GET вместо POST
        print("\n1. Тестирование GET запросов:")
        endpoints_get = [
            "/references/GetOkpdReference",
            "/references/GetRegionsReference", 
            "/references/GetProductionDirectoryReference"
        ]
        
        for endpoint in endpoints_get:
            url = f"{self.base_url}{endpoint}"
            print(f"GET {endpoint}")
            try:
                response = self.session.get(url, timeout=10)
                print(f"Статус: {response.status_code}")
                if response.status_code == 200:
                    print("Успех!")
                    data = response.json()
                    print(f"Данные: {len(data.get('items', []))} записей")
                    return url, data, 'GET'
            except Exception as e:
                print(f"Ошибка: {e}")

        # 2. Пробуем другие endpoints
        print("\n2. Тестирование других endpoints:")
        other_endpoints = [
            "/queries/GetStatistics",
            "/queries/GetOffers", 
            "/queries/GetTenders"
        ]
        
        for endpoint in other_endpoints:
            url = f"{self.base_url}{endpoint}"
            print(f"POST {endpoint}")
            try:
                response = self.session.post(url, json={"take": 5}, timeout=10)
                print(f"Статус: {response.status_code}")
                if response.status_code == 200:
                    print("Успех!")
                    data = response.json()
                    print(f"Данные: {data.get('count', 0)} записей")
                    return url, data, 'POST'
            except Exception as e:
                print(f"Ошибка: {e}")

        return None, None, None

    def get_public_data(self):
        """Получение публичных данных"""
        print("\nПолучение публичных справочников...")
        
        # Справочники которые могут быть публичными
        references = {
            "OKPD2": "/references/GetOkpdReference",
            "Регионы": "/references/GetRegionsReference",
            "Категории": "/references/GetProductionDirectoryReference"
        }
        
        results = {}
        
        for name, endpoint in references.items():
            url = f"{self.base_url}{endpoint}"
            print(f"Получение {name}...")
            
            try:
                # Пробуем GET
                response = self.session.get(url, timeout=10)
                if response.status_code != 200:
                    # Пробуем POST
                    response = self.session.post(url, json={}, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    results[name] = data
                    print(f"Успешно: {len(data.get('items', []))} записей")
                    
                    # Сохраняем данные
                    filename = f"{name.lower()}_data.json"
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    print(f"Сохранено в {filename}")
                else:
                    print(f"Ошибка: {response.status_code}")
                    
            except Exception as e:
                print(f"Ошибка: {e}")
        
        return results

    def try_simple_queries(self):
        """Простые запросы с минимальными параметрами"""
        print("\nПростые запросы...")
        
        queries = [
            {
                "name": "Статистика",
                "endpoint": "/queries/GetStatistics",
                "params": {}
            },
            {
                "name": "Оферты", 
                "endpoint": "/queries/GetOffers",
                "params": {"take": 10}
            },
            {
                "name": "Закупки",
                "endpoint": "/queries/GetTenders", 
                "params": {"take": 10}
            }
        ]
        
        for query in queries:
            url = f"{self.base_url}{query['endpoint']}"
            print(f"Запрос: {query['name']}")
            
            try:
                response = self.session.post(url, json=query['params'], timeout=10)
                print(f"Статус: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    count = data.get('count', len(data.get('items', [])))
                    print(f"Успешно: {count} записей")
                    
                    # Сохраняем
                    filename = f"{query['name'].lower()}.json"
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    print(f"Сохранено в {filename}")
                    
            except Exception as e:
                print(f"Ошибка: {e}")

    def check_permissions(self):
        """Проверка доступных разрешений"""
        print("\nПроверка разрешений токена...")
        
        # Пробуем разные scope
        test_requests = [
            {"scope": "read", "endpoint": "/queries/GetSkus", "params": {"take": 1}},
            {"scope": "public", "endpoint": "/references/GetOkpdReference", "params": {}},
            {"scope": "basic", "endpoint": "/queries/GetStatistics", "params": {}},
        ]
        
        for test in test_requests:
            url = f"{self.base_url}{test['endpoint']}"
            print(f"Тест scope: {test['scope']}")
            
            try:
                response = self.session.post(url, json=test['params'], timeout=10)
                print(f"Статус: {response.status_code}")
                
                if response.status_code == 200:
                    print("Доступ разрешен")
                elif response.status_code == 403:
                    print("Доступ запрещен - недостаточно прав")
                elif response.status_code == 401:
                    print("Неавторизован")
                    
            except Exception as e:
                print(f"Ошибка: {e}")

def main():
    # Ваш токен
    API_KEY = "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJwbDgxLVYyWUNyQ1V0bmVRTWxxRUNmSVluS1Z3VExnQVIwZXhiTkF1SF9nIn0.eyJleHAiOjIwNzQ4MzM1MTcsImlhdCI6MTc1OTQ3NTIyMCwiYXV0aF90aW1lIjoxNzU5NDczNTE3LCJqdGkiOiIyNThmYTAzZi1jNTk5LTQ5MTUtOWUzYS0yMDdhMmYxOWVmNjYiLCJpc3MiOiJodHRwczovL3pha3Vwa2kubW9zLnJ1L2F1dGgvcmVhbG1zL1BwUmVhbG0iLCJhdWQiOiJJbnRlZ3JhdGlvbkFwcCIsInN1YiI6IjdlMjhiZTU5LWYyNjYtNGNkZi05OWJhLTMzYzJmYTFmZWY4ZSIsInR5cCI6IkJlYXJlciIsImF6cCI6IlBwQXBwIiwic2Vzc2lvbl9zdGF0ZSI6IjNkOTc1N2FhLTNlNjEtNGY5Ni1hNGIzLWE4NjMxNTk3YjVkMiIsInNjb3BlIjoiSW50ZWdyYXRpb25TY29wZSIsInNpZCI6IjNkOTc1N2FhLTNlNjEtNGY5Ni1hNGIzLWE4NjMxNTk3YjVkMiJ9.CREupv9Bav92I17mb62RwVqYIWH2kwaHGL4W9kNDXmvKSvK2jSio1skOGe_UjsmIzTrusEU4h8L9XuPZB-ILBDe3GANNsT4fF5WUWjHWjpeULpSa5Z7SijcPAQ-0S1tX734ysPwfT4N4_bsOzew-h7eMYaxTfH5PvXvI8ht73UCC0m8yKL_pufHt1y7HvjZ6ZpuW4AnyBnQdcmULMS9ufzU6KnH7QkDSiAUF-Xajpe-N2AyWBwdunmMtQ9sSGPPExYVzmqHzKWGdrQuqRmymAyvRfs9Cx12Sf7jpD4-aOwwu7gKfMaE6-2GypETFglGXPr3Y6EEUMpxyTbWljFP-rg"
    
    client = MosZakupkiAPIClient(API_KEY)
    
    print("=" * 60)
    print("Анализ доступов API с предоставленным токеном")
    print("=" * 60)
    
    # Проверяем разрешения
    client.check_permissions()
    
    # Пробуем разные подходы
    url, data, method = client.try_different_approaches()
    
    if data:
        print(f"\nНайден рабочий метод: {method} {url}")
    else:
        print("\nОсновные endpoints недоступны. Пробуем публичные данные...")
        public_data = client.get_public_data()
        
        if public_data:
            print("Успешно получены публичные данные")
        else:
            print("\nПробуем простые запросы...")
            client.try_simple_queries()

if __name__ == "__main__":
    main()