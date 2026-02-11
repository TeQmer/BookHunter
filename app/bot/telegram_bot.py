"""
Telegram Bot для системы мониторинга скидок на книги
"""

import logging
import os
from typing import Optional, Dict, Any
import asyncio

import httpx
from telegram import Bot

logger = logging.getLogger(__name__)


class TelegramBot:
    """Класс для работы с Telegram Bot"""
    
    def __init__(self, token: Optional[str] = None):
        """
        Инициализация бота
        
        Args:
            token: Токен бота (если None, берется из переменных окружения)
        """
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
        
        self.bot = Bot(token=self.token)
        logger.info("Telegram Bot инициализирован")
    
    async def get_me(self) -> Dict[str, Any]:
        """Получение информации о боте"""
        try:
            bot_info = await self.bot.get_me()
            return {
                "id": bot_info.id,
                "username": bot_info.username,
                "first_name": bot_info.first_name,
                "is_bot": bot_info.is_bot
            }
        except Exception as e:
            logger.error(f"Ошибка получения информации о боте: {e}")
            raise
    
    async def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML") -> Dict[str, Any]:
        """Отправка сообщения"""
        try:
            message = await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode
            )
            logger.info(f"Сообщение отправлено пользователю {chat_id}")
            return {
                "message_id": message.message_id,
                "chat_id": message.chat.id,
                "text": message.text
            }
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            raise
    
    async def send_book_alert(self, chat_id: int, book_data: Dict[str, Any]) -> Dict[str, Any]:
        """Отправка уведомления о книге"""
        try:
            title = book_data.get("title", "Без названия")
            author = book_data.get("author", "Неизвестный автор")
            current_price = book_data.get("current_price", 0)
            original_price = book_data.get("original_price", 0)
            discount_percent = book_data.get("discount_percent", 0)
            url = book_data.get("url", "")
            source = book_data.get("source", "Неизвестный магазин")
            
            # Формирование сообщения
            message_text = f"""
📚 <b>Найдена подходящая книга!</b>

<b>Название:</b> {title}
<b>Автор:</b> {author}
<b>Магазин:</b> {source}

💰 <b>Цена:</b> {current_price} ₽
📉 <b>Скидка:</b> {discount_percent}% (было {original_price} ₽)

🔗 <a href="{url}">Открыть в магазине</a>

#книги #скидки #{source.replace(' ', '_').lower()}
            """.strip()
            
            return await self.send_message(chat_id, message_text)
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о книге: {e}")
            raise
    
    async def send_error_notification(self, chat_id: int, error_message: str) -> Dict[str, Any]:
        """Отправка уведомления об ошибке"""
        message_text = f"""
❌ <b>Ошибка системы</b>

{error_message}

<i>Время:</i> {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """.strip()
        
        return await self.send_message(chat_id, message_text)
    
    async def send_system_status(self, chat_id: int, status_data: Dict[str, Any]) -> Dict[str, Any]:
        """Отправка статуса системы"""
        status = status_data.get("status", "unknown")
        components = status_data.get("components", {})
        
        # Эмодзи для статуса
        status_emoji = {
            "healthy": "✅",
            "degraded": "⚠️",
            "unhealthy": "❌"
        }.get(status, "❓")
        
        message_text = f"""
🔍 <b>Статус системы мониторинга</b>

<b>Общий статус:</b> {status_emoji} {status.upper()}

<b>Компоненты:</b>
        """
        
        for component, info in components.items():
            emoji = "✅" if info.get("status") == "healthy" else "⚠️" if info.get("status") == "warning" else "❌"
            message_text += f"\n{emoji} <b>{component}:</b> {info.get('message', 'Нет данных')}"
        
        message_text += f"\n\n<i>Время проверки:</i> {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return await self.send_message(chat_id, message_text)
    
    async def get_webhook_info(self) -> Dict[str, Any]:
        """Получение информации о webhook"""
        try:
            webhook_info = await self.bot.get_webhook_info()
            return {
                "url": webhook_info.url,
                "has_custom_certificate": webhook_info.has_custom_certificate,
                "pending_update_count": webhook_info.pending_update_count,
                "last_error_date": webhook_info.last_error_date,
                "last_error_message": webhook_info.last_error_message
            }
        except Exception as e:
            logger.error(f"Ошибка получения информации о webhook: {e}")
            raise
    
    async def set_webhook(self, url: str) -> Dict[str, Any]:
        """Настройка webhook"""
        try:
            webhook_info = await self.bot.set_webhook(url=url)
            return {
                "result": webhook_info,
                "webhook_url": url
            }
        except Exception as e:
            logger.error(f"Ошибка настройки webhook: {e}")
            raise
    
    async def delete_webhook(self) -> Dict[str, Any]:
        """Удаление webhook"""
        try:
            result = await self.bot.delete_webhook()
            return {"result": result}
        except Exception as e:
            logger.error(f"Ошибка удаления webhook: {e}")
            raise
