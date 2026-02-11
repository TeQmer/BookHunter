#!/usr/bin/env python3
"""
Основной файл запуска Telegram Bot
"""

import asyncio
import logging
import os
import sys
from typing import Optional

# Добавляем путь к модулям
sys.path.append('/app')

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    filters,
    ContextTypes
)

from bot.handlers import (
    start_handler, 
    help_handler, 
    status_handler, 
    alerts_handler, 
    books_handler, 
    settings_handler,
    unknown_handler
)


class TelegramBotRunner:
    """Класс для запуска и управления Telegram Bot"""
    
    def __init__(self, token: Optional[str] = None):
        """
        Инициализация бота
        
        Args:
            token: Токен бота (если None, берется из переменных окружения)
        """
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
        
        self.application = None
        self.logger = logging.getLogger(__name__)
    
    async def setup_application(self):
        """Настройка приложения бота"""
        self.application = (
            ApplicationBuilder()
            .token(self.token)
            .build()
        )
        
        # Регистрируем обработчики команд
        self.application.add_handler(CommandHandler("start", start_handler))
        self.application.add_handler(CommandHandler("help", help_handler))
        self.application.add_handler(CommandHandler("status", status_handler))
        self.application.add_handler(CommandHandler("alerts", alerts_handler))
        self.application.add_handler(CommandHandler("books", books_handler))
        self.application.add_handler(CommandHandler("settings", settings_handler))
        
        # Обработчик неизвестных команд
        self.application.add_handler(MessageHandler(filters.COMMAND, unknown_handler))
        
        self.logger.info("Telegram Bot настроен и готов к работе")
    
    async def start_polling(self):
        """Запуск бота в режиме polling"""
        await self.setup_application()
        self.logger.info("Запуск Telegram Bot в режиме polling...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        self.logger.info("Telegram Bot запущен и ожидает сообщения")
        
        try:
            # Держим бота активным
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Получен сигнал остановки")
        finally:
            await self.stop()
    
    async def stop(self):
        """Остановка бота"""
        if self.application:
            await self.application.stop()
            await self.application.shutdown()
            self.logger.info("Telegram Bot остановлен")


async def test_send_message():
    """Тест отправки сообщения"""
    try:
        from bot.telegram_bot import TelegramBot
        
        bot = TelegramBot()
        
        # Проверяем информацию о боте
        me = await bot.get_me()
        print(f"✅ Бот: @{me['username']} ({me['first_name']})")
        
        # Тест отправки сообщения (замените на ваш chat_id)
        test_chat_id = int(os.getenv("TEST_CHAT_ID", "0"))
        
        if test_chat_id != 0:
            message = await bot.send_message(
                chat_id=test_chat_id,
                text="🤖 <b>Тест подключения</b>\n\nБот успешно запущен и готов к работе!"
            )
            print(f"✅ Тестовое сообщение отправлено: ID {message['message_id']}")
        else:
            print("⚠️ TEST_CHAT_ID не установлен - тестовое сообщение не отправлено")
            print("Для теста отправьте команду /start вашему боту @BookHunter_OfficialBot")
            
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")


async def main():
    """Основная функция"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Проверяем режим работы
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        await test_send_message()
    else:
        # Запуск бота
        runner = TelegramBotRunner()
        await runner.start_polling()


if __name__ == "__main__":
    asyncio.run(main())
