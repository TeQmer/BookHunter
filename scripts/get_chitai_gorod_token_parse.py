"""
Скрипт для извлечения токена из JavaScript кода страницы Читай-города

Парсит HTML и ищет токен в JavaScript коде
"""

import re
import requests
from pathlib import Path
from dotenv import load_dotenv, set_key


def extract_token_from_js():
    """
    Извлекает токен из JavaScript кода страницы

    Returns:
        str: Токен авторизации или None
    """
    print("[1/4] Загрузка страницы...")

    url = "https://www.chitai-gorod.ru"

    try:
        # Улучшенные заголовки, имитирующие настоящий браузер
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 YaBrowser/25.12.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
        }

        # Создаем сессию для сохранения cookies
        session = requests.Session()

        response = session.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f"[-] Ошибка загрузки: HTTP {response.status_code}")
            return None

        print("[+] Страница загружена")

        # Ищем токен в JavaScript коде
        print("[2/4] Поиск токена в JavaScript коде...")

        html = response.text

        # Паттерны для поиска токена
        patterns = [
            # Bearer токен в JavaScript
            r'Bearer\s+([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)',
            # access-token в JavaScript объекте
            r'access-token["\s:]+([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)',
            # Токен в строке
            r'["\']Bearer%20([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)["\']',
            # Токен в конфигурации
            r'authorization["\s:]+["\']Bearer%20([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)["\']',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, html)
            for match in matches:
                token = match.group(1)
                if token:
                    print(f"[+] Найден токен: {token[:50]}...")
                    return token

        print("[-] Токен не найден в JavaScript коде")
        return None

    except Exception as e:
        print(f"[-] Ошибка: {e}")
        return None


def test_token(token):
    """
    Проверяет, работает ли токен

    Args:
        token: Токен авторизации

    Returns:
        bool: True если токен работает, False если нет
    """
    print("\n[3/4] Проверка токена...")

    api_url = "https://web-agr.chitai-gorod.ru/web/api/v2/search/product"

    headers = {
        "accept": "*/*",
        "accept-language": "ru,en;q=0.9",
        "authorization": f"Bearer {token}",
        "shop-brand": "chitaiGorod",
        "user-id": "19676135",
    }

    params = {
        "customerCityId": 39,
        "products[page]": 1,
        "products[per-page]": 5,
        "phrase": "тест"
    }

    try:
        response = requests.get(api_url, params=params, headers=headers, timeout=10)

        if response.status_code == 200:
            print("[+] Токен работает!")
            return True
        elif response.status_code == 401:
            print("[-] Токен недействителен (401 Unauthorized)")
            return False
        else:
            print(f"[-] Ошибка проверки: HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"[-] Ошибка при проверке токена: {e}")
        return False


def update_env_token(token):
    """
    Обновляет токен в .env файле

    Args:
        token: Новый токен
    """
    print("[4/4] Обновление .env файла...")

    env_path = Path(__file__).parent.parent / ".env"

    if not env_path.exists():
        print(f"[-] Файл {env_path} не найден")
        return False

    try:
        load_dotenv(env_path)
        set_key(env_path, "CHITAI_GOROD_BEARER_TOKEN", f"Bearer {token}")
        print("[+] Токен обновлен в .env")
        return True

    except Exception as e:
        print(f"[-] Ошибка: {e}")
        return False


def main():
    """Главная функция"""
    print("="*80)
    print("ИЗВЛЕЧЕНИЕ ТОКЕНА ИЗ JAVASCRIPT КОДА")
    print("="*80)
    print()

    token = extract_token_from_js()

    if not token:
        print("\n[-] Не удалось извлечь токен")
        print("\n[!] ПРЕДЛОЖЕНИЕ: Получите токен вручную через браузер:")
        print("   1. Откройте https://www.chitai-gorod.ru/ в браузере")
        print("   2. F12 -> Network -> Фильтр по XHR")
        print("   3. Обновите страницу")
        print("   4. Найдите запрос к API и скопируйте токен из заголовков")
        print("   5. Добавьте в .env: CHITAI_GOROD_BEARER_TOKEN=Bearer_ВАШ_ТОКЕН")
        return

    if test_token(token):
        update_env_token(token)
        print("\n[+] Готово! Перезапустите Docker:")
        print("  docker-compose restart celery_worker")
    else:
        print("\n[-] Токен недействителен")


if __name__ == "__main__":
    main()
