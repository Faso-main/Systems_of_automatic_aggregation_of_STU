import requests
import json

class IntegrationScopeTester:
    
    def __init__(self, api_key: str):
        self.base_url = "https://api.zakupki.mos.ru/api/v1"
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })
    
    def test_integration_endpoints(self):
        """Тестируем endpoints доступные для IntegrationScope"""
        print("Тестирование endpoints для IntegrationScope...")
        
        # Endpoints которые могут быть доступны для интеграции
        integration_endpoints = [
            # Команды для интеграции
            ("/commands/SyncWithEis", "Синхронизация с ЕИС"),
            ("/commands/ProcessIntegrationQueue", "Очередь интеграции"),
            ("/externalCommands/ReceiveNotification", "Получение уведомлений"),
            
            # Запросы статистики
            ("/queries/GetStatistics", "Статистика"),
            ("/queries/GetContractStats", "Статистика контрактов"),
            
            # Справочники
            ("/references/GetOkpdReference", "Справочник ОКПД2"),
            ("/references/GetRegionsReference", "Справочник регионов"),
            
            # Внешние запросы
            ("/externalQueries/GetExternalSkus", "Внешние СТЕ"),
            ("/externalQueries/GetExternalSkuChangeRequests", "Заявки на СТЕ"),
        ]
        
        available_endpoints = []
        
        for endpoint, description in integration_endpoints:
            url = f"{self.base_url}{endpoint}"
            print(f"Тест: {description}")
            
            try:
                # Пробуем POST с пустыми параметрами
                response = self.session.post(url, json={}, timeout=10)
                print(f"  Статус: {response.status_code}")
                
                if response.status_code == 200:
                    print(f"  ✅ ДОСТУПЕН")
                    available_endpoints.append((endpoint, description))
                    
                    # Сохраняем пример ответа
                    data = response.json()
                    with open(f"integration_{endpoint.split('/')[-1]}.json", "w") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                        
                elif response.status_code in [400, 422]:
                    print(f"  ⚠️  Требуются параметры")
                    available_endpoints.append((endpoint, description))
                    
            except Exception as e:
                print(f"  ❌ Ошибка: {e}")
        
        return available_endpoints
    
    def try_integration_commands(self):
        """Пробуем команды интеграции"""
        print("\nТестирование команд интеграции...")
        
        integration_commands = [
            {
                "name": "Синхронизация с ЕИС",
                "endpoint": "/commands/SyncWithEis", 
                "params": {"contractId": 123}  # Тестовый ID
            },
            {
                "name": "Очередь интеграции",
                "endpoint": "/commands/ProcessIntegrationQueue",
                "params": {}
            }
        ]
        
        for cmd in integration_commands:
            url = f"{self.base_url}{cmd['endpoint']}"
            print(f"Команда: {cmd['name']}")
            
            try:
                response = self.session.post(url, json=cmd['params'], timeout=10)
                print(f"  Статус: {response.status_code}")
                
                if response.status_code == 200:
                    print("  ✅ Команда выполнена")
                elif response.status_code == 400:
                    print("  ⚠️  Неверные параметры")
                elif response.status_code == 404:
                    print("  ❌ Ресурс не найден")
                    
            except Exception as e:
                print(f"  ❌ Ошибка: {e}")

def main():
    API_KEY = "your-token-here"
    
    tester = IntegrationScopeTester(API_KEY)
    
    print("=" * 60)
    print("АНАЛИЗ ДОСТУПА IntegrationScope")
    print("=" * 60)
    
    # Тестируем доступные endpoints
    available = tester.test_integration_endpoints()
    
    print(f"\nДоступные endpoints: {len(available)}")
    for endpoint, description in available:
        print(f"  ✅ {description}: {endpoint}")
    
    # Тестируем команды
    tester.try_integration_commands()
    
    if not available:
        print("\n❌ Нет доступных endpoints с текущим токеном")
        print("\nРЕКОМЕНДАЦИИ:")
        print("1. Обратитесь к администратору портала")
        print("2. Запросите токен с правами на чтение данных")
        print("3. Используйте веб-интерфейс для просмотра данных")
        print("4. Рассмотрите альтернативные источники данных")

if __name__ == "__main__":
    main()