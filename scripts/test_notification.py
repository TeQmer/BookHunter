#!/usr/bin/env python3
"""
Скрипт для тестирования Telegram уведомлений о смене токена

Использование:
    python scripts/test_notification.py

Переменные окружения (должны быть в .env):
    TELEGRAM_NOTIFICATION_BOT_TOKEN - токен бота для уведомлений
    TELEGRAM_NOTIFICATION_CHAT_ID - ваш Chat ID
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()


def send_test_notification():
    """Отправляет тестовое уведомление в Telegram"""

    bot_token = os.getenv("TELEGRAM_NOTIFICATION_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_NOTIFICATION_CHAT_ID")

    # Проверяем настройки
    if not bot_token:
        print("❌ ОШИБКА: TELEGRAM_NOTIFICATION_BOT_TOKEN не задан в .env")
        print("   Получите токен бота через @BotFather в Telegram")
        return False

    if not chat_id:
        print("❌ ОШИБКА: TELEGRAM_NOTIFICATION_CHAT_ID не задан в .env")
        print("   Получите ваш Chat ID через @userinfobot в Telegram")
        return False

    # Формируем сообщение
    message = "🧪 <b>Тестовое уведомление</b>\n\n"
    message += "✅ Система уведомлений работает корректно!\n\n"
    message += "Вы будете получать уведомления при:\n"
    message += "• Обновлении токена Читай-города\n"
    message += "• Ошибках при обновлении токена\n"
    message += "• Таймаутах FlareSolverr"

    # Отправляем сообщение
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        print(f"📤 Отправка уведомления в Telegram...")
        print(f"   Bot Token: {bot_token[:20]}...")
        print(f"   Chat ID: {chat_id}")
        print()

        response = requests.post(url, json=data, timeout=10)

        if response.status_code == 200:
            result = response.json()
            print("✅ Успешно! Уведомление отправлено.")
            print(f"   Message ID: {result.get('result', {}).get('message_id')}")
            print()
            print("📱 Проверьте Telegram - вы должны получить тестовое сообщение!")
            return True
        else:
            print(f"❌ ОШИБКА: Telegram API вернул статус {response.status_code}")
            print(f"   Ответ: {response.text}")
            return False

    except requests.Timeout:
        print("❌ ОШИБКА: Таймаут при отправке уведомления")
        return False
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("  ТЕСТИРОВАНИЕ TELEGRAM УВЕДОМЛЕНИЙ")
    print("=" * 60)
    print()

    success = send_test_notification()

    print()
    print("=" * 60)

    if success:
        print("✅ ТЕСТ ПРОЙДЕН УСПЕШНО!")
        print("   Уведомления о смене токена будут работать.")
    else:
        print("❌ ТЕСТ НЕ ПРОЙДЕН")
        print("   Проверьте настройки в .env файле:")
        print("   1. TELEGRAM_NOTIFICATION_BOT_TOKEN")
        print("   2. TELEGRAM_NOTIFICATION_CHAT_ID")

    print("=" * 60)

    sys.exit(0 if success else 1)
