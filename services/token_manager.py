"""
Менеджер токенов для авторизации в API магазинов

Обеспечивает:
- Получение токена из Redis
- Обновление токена при истечении
- Проверку валидности токена
- Триггер Celery задач для обновления
- Отправка уведомлений в Telegram
"""

import os
import re
import logging
import requests
from typing import Optional, Dict
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class TokenManager:
    """Менеджер токенов с хранением в Redis"""

    def __init__(self, redis_url: str = None, redis_password: str = None):
        """
        Инициализация менеджера токенов

        Args:
            redis_url: URL для подключения к Redis
            redis_password: Пароль для Redis
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis_password = redis_password or os.getenv("REDIS_PASSWORD")
        self._redis_client = None

    def _get_redis_client(self):
        """Получение клиента Redis (lazy initialization)"""
        if self._redis_client is None:
            import redis

            # Формируем правильный URL с паролем
            if self.redis_password and "://" in self.redis_url:
                # Проверяем, есть ли уже пароль в URL
                if not self.redis_url.startswith("redis://:"):
                    # Добавляем пароль в URL
                    host = self.redis_url.split("://")[1].split(":")[0]
                    port = self.redis_url.split(":")[-1].split("/")[0]
                    db = self.redis_url.split("/")[-1] if "/" in self.redis_url else "0"
                    self.redis_url = f"redis://:{self.redis_password}@{host}:{port}/{db}"

            self._redis_client = redis.from_url(self.redis_url, decode_responses=True)

        return self._redis_client

    def get_chitai_gorod_token(self) -> Optional[str]:
        """
        Получение токена Читай-города из Redis

        Returns:
            Токен или None, если токен не найден
        """
        try:
            redis_client = self._get_redis_client()
            token = redis_client.get("chitai_gorod_token")

            if token:
                logger.info(f"Токен получен из Redis: {token[:20]}...")
                return token
            else:
                logger.warning("Токен не найден в Redis")
                return None

        except Exception as e:
            logger.error(f"Ошибка получения токена из Redis: {e}")
            return None

    def save_chitai_gorod_token(self, token: str, ttl: int = 86400) -> bool:
        """
        Сохранение токена Читай-города в Redis

        Args:
            token: Токен для сохранения
            ttl: Время жизни в секундах (по умолчанию 24 часа)

        Returns:
            True при успехе, False при ошибке
        """
        try:
            redis_client = self._get_redis_client()
            redis_client.setex("chitai_gorod_token", ttl, token)
            logger.info(f"Токен сохранен в Redis (TTL: {ttl} сек)")
            return True

        except Exception as e:
            logger.error(f"Ошибка сохранения токена в Redis: {e}")
            return False

    def get_chitai_gorod_token_from_env(self) -> Optional[str]:
        """
        Получение токена Читай-города из переменных окружения

        Returns:
            Токен или None, если токен не найден
        """
        return os.getenv("CHITAI_GOROD_BEARER_TOKEN")

    def get_chitai_gorod_token_fallback(self) -> str:
        """
        Получение токена Читай-города с fallback механизмом

        Сначала пытается получить из Redis, затем из env

        Returns:
            Токен или пустая строка, если токен не найден
        """
        # Сначала пробуем Redis
        token = self.get_chitai_gorod_token()
        if token:
            logger.info("Токен получен из переменных окружения")
            return token

        # Если в Redis нет, пробуем env
        token = self.get_chitai_gorod_token_from_env()
        if token:
            logger.info("Токен получен из переменных окружения")
            return token

        logger.error("Токен не найден ни в Redis, ни в переменных окружения")
        return ""

    def get_chitai_gorod_cookies(self) -> Optional[Dict[str, str]]:
        """
        Получение cookies Читай-города из Redis

        Returns:
            Словарь cookies или None
        """
        try:
            redis_client = self._get_redis_client()
            cookies_json = redis_client.get("chitai_gorod_cookies")

            if cookies_json:
                import json
                cookies = json.loads(cookies_json)
                logger.info(f"Cookies получены из Redis: {len(cookies)} cookies")
                return cookies
            else:
                logger.warning("Cookies не найдены в Redis")
                return None

        except Exception as e:
            logger.error(f"Ошибка получения cookies из Redis: {e}")
            return None

    def save_chitai_gorod_cookies(self, cookies: Dict[str, str], ttl: int = 86400) -> bool:
        """
        Сохранение cookies Читай-города в Redis

        Args:
            cookies: Словарь cookies
            ttl: Время жизни в секундах (по умолчанию 24 часа)

        Returns:
            True при успехе, False при ошибке
        """
        try:
            redis_client = self._get_redis_client()
            import json
            cookies_json = json.dumps(cookies)
            redis_client.setex("chitai_gorod_cookies", ttl, cookies_json)
            logger.info(f"Cookies сохранены в Redis (TTL: {ttl} сек)")
            return True

        except Exception as e:
            logger.error(f"Ошибка сохранения cookies в Redis: {e}")
            return False

    def trigger_token_update(self) -> bool:
        """
        Триггер Celery задачи для обновления токена

        Returns:
            True при успехе, False при ошибке
        """
        try:
            from services.celery_app import celery_app

            celery_logger = logging.getLogger("celery")
            celery_logger.info("Триггер задачи обновления токена Читай-города")

            # Отправляем задачу в Celery
            result = celery_app.send_task(
                "services.celery_tasks.update_chitai_gorod_token",
                countdown=5  # Запускаем через 5 секунд
            )

            logger.info(f"Задача обновления токена отправлена: {result.id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка триггера задачи обновления токена: {e}")
            return False

    def close(self):
        """Закрытие соединения с Redis"""
        if self._redis_client:
            self._redis_client.close()
            self._redis_client = None

    def send_token_notification(self, status: str, message: str, details: str = None):
        """
        Отправка уведомления о статусе токена в Telegram

        Args:
            status: Статус (success, error, warning)
            message: Сообщение
            details: Дополнительные детали (опционально)
        """
        try:
            bot_token = os.getenv("TELEGRAM_NOTIFICATION_BOT_TOKEN")
            chat_id = os.getenv("TELEGRAM_NOTIFICATION_CHAT_ID")

            if not bot_token or not chat_id:
                logger.warning("Не настроены переменные для Telegram уведомлений")
                return

            # Формируем сообщение
            emoji_map = {
                "success": "✅",
                "error": "❌",
                "warning": "⚠️",
                "info": "ℹ️"
            }

            emoji = emoji_map.get(status, "📢")
            telegram_message = f"{emoji} <b>Уведомление о токене Читай-город</b>\n\n"
            telegram_message += f"{message}\n"

            if details:
                telegram_message += f"\n<code>{details}</code>"

            # Отправляем сообщение
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": telegram_message,
                "parse_mode": "HTML"
            }

            response = requests.post(url, json=data, timeout=10)

            if response.status_code == 200:
                logger.info(f"Уведомление отправлено в Telegram: {status}")
            else:
                logger.error(f"Ошибка отправки уведомления: {response.status_code}")

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления в Telegram: {e}")

    def send_subscriptions_check_notification(
        self,
        total_checked: int,
        active_count: int,
        matched_count: int,
        deactivated_count: int,
        notifications_sent: int,
        duration_seconds: float,
        errors: str = None
    ):
        """
        Отправка уведомления о результатах проверки подписок

        Args:
            total_checked: Всего подписок проверено
            active_count: Активных подписок
            matched_count: Подписок подошли под условия
            deactivated_count: Деактивировано подписок
            notifications_sent: Отправлено уведомлений
            duration_seconds: Время выполнения в секундах
            errors: Ошибки (опционально)
        """
        try:
            bot_token = os.getenv("TELEGRAM_NOTIFICATION_BOT_TOKEN")
            chat_id = os.getenv("TELEGRAM_NOTIFICATION_CHAT_ID")

            if not bot_token or not chat_id:
                logger.warning("Не настроены переменные для Telegram уведомлений")
                return

            # Формируем сообщение
            telegram_message = "🔔 <b>Проверка подписок завершена</b>\n\n"
            telegram_message += f"📊 <b>Статистика:</b>\n"
            telegram_message += f"• Проверено подписок: {total_checked}\n"
            telegram_message += f"• Активных подписок: {active_count}\n"
            telegram_message += f"• Подошли под условия: {matched_count}\n"
            telegram_message += f"• Деактивировано: {deactivated_count}\n"
            telegram_message += f"• Отправлено уведомлений: {notifications_sent}\n"
            telegram_message += f"• Время выполнения: {duration_seconds:.1f} сек\n"

            if errors:
                telegram_message += f"\n⚠️ <b>Ошибки:</b>\n<code>{errors}</code>"

            # Отправляем сообщение
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": telegram_message,
                "parse_mode": "HTML"
            }

            response = requests.post(url, json=data, timeout=10)

            if response.status_code == 200:
                logger.info("Статистика подписок отправлена в Telegram")
            else:
                logger.error(f"Ошибка отправки статистики: {response.status_code}")

        except Exception as e:
            logger.error(f"Ошибка отправки статистики в Telegram: {e}")

    def send_cleanup_notification(
        self,
        books_checked: int,
        books_removed_no_author: int,
        books_removed_no_binding: int,
        books_removed_duplicates: int,
        total_removed: int,
        duration_seconds: float,
        errors: str = None
    ):
        """
        Отправка уведомления о результатах очистки книг

        Args:
            books_checked: Всего книг проверено
            books_removed_no_author: Удалено книг без автора
            books_removed_no_binding: Удалено книг без переплета
            books_removed_duplicates: Удалено дубликатов
            total_removed: Всего удалено
            duration_seconds: Время выполнения в секундах
            errors: Ошибки (опционально)
        """
        try:
            bot_token = os.getenv("TELEGRAM_NOTIFICATION_BOT_TOKEN")
            chat_id = os.getenv("TELEGRAM_NOTIFICATION_CHAT_ID")

            if not bot_token or not chat_id:
                logger.warning("Не настроены переменные для Telegram уведомлений")
                return

            # Формируем сообщение
            telegram_message = "🧹 <b>Очистка книг завершена</b>\n\n"
            telegram_message += f"📊 <b>Статистика:</b>\n"
            telegram_message += f"• Проверено книг: {books_checked}\n"
            telegram_message += f"• Удалено (нет автора): {books_removed_no_author}\n"
            telegram_message += f"• Удалено (нет переплета): {books_removed_no_binding}\n"
            telegram_message += f"• Удалено (дубликаты): {books_removed_duplicates}\n"
            telegram_message += f"• <b>Всего удалено: {total_removed}</b>\n"
            telegram_message += f"• Время выполнения: {duration_seconds:.1f} сек\n"

            if errors:
                telegram_message += f"\n⚠️ <b>Ошибки:</b>\n<code>{errors}</code>"

            # Отправляем сообщение
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": telegram_message,
                "parse_mode": "HTML"
            }

            response = requests.post(url, json=data, timeout=10)

            if response.status_code == 200:
                logger.info("Статистика очистки книг отправлена в Telegram")
            else:
                logger.error(f"Ошибка отправки статистики: {response.status_code}")

        except Exception as e:
            logger.error(f"Ошибка отправки статистики в Telegram: {e}")


# Глобальный экземпляр для использования в приложении
_token_manager_instance = None


def get_token_manager() -> TokenManager:
    """Получение глобального экземпляра менеджера токенов"""
    global _token_manager_instance
    if _token_manager_instance is None:
        _token_manager_instance = TokenManager()
    return _token_manager_instance
