from data import key_api

def check_token_validity(token: str):
    import jwt
    from datetime import datetime
    
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        
        print("Информация о токене:")
        print(f"Выдан: {datetime.fromtimestamp(decoded.get('auth_time', 0))}")
        print(f"Создан: {datetime.fromtimestamp(decoded.get('iat', 0))}")
        print(f"Истекает: {datetime.fromtimestamp(decoded.get('exp', 0))}")
        print(f"Субъект: {decoded.get('sub')}")
        print(f"Область действия: {decoded.get('scope')}")
        
        exp_time = datetime.fromtimestamp(decoded.get('exp', 0))
        current_time = datetime.now()
        
        if exp_time > current_time:
            print("Токен действителен")
            return True
        else:
            print("Токен просрочен")
            return False
            
    except Exception as e:
        print(f"Ошибка проверки токена: {e}")
        return False

check_token_validity(key_api)