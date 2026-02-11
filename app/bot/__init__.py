"""
Модуль интеграции с Telegram Bot для системы мониторинга скидок на книги.
"""

from .telegram_bot import TelegramBot
from .handlers import register_handlers

__all__ = ["TelegramBot", "register_handlers"]
