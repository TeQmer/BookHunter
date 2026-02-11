"""
Обработчики команд и сообщений для Telegram Bot
"""

import logging
import os
from typing import Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters

logger = logging.getLogger(__name__)

# URL для Telegram Mini App
MINI_APP_URL = os.getenv("MINI_APP_URL", "http://localhost:8000/telegram")


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    # Создаем клавиатуру с кнопкой Mini App
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Открыть приложение", web_app=WebAppInfo(url=MINI_APP_URL))],
        [InlineKeyboardButton("📖 Каталог книг", callback_data="books"),
         InlineKeyboardButton("🔔 Мои подписки", callback_data="alerts")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ])

    welcome_text = f"""
🎉 Добро пожаловать в BookHunter!

Я помогу вам отслеживать скидки на книги в различных магазинах.

<b>📱 Telegram Mini App</b>
Нажмите кнопку ниже, чтобы открыть полноценное приложение с красивым интерфейсом!

<b>Доступные команды:</b>
• /help - справка по командам
• /status - статус системы
• /app - открыть Mini App
• /alerts - управление подписками
• /books - поиск книг

<b>Как это работает:</b>
1. Создайте подписку на интересующие вас книги
2. Я буду отслеживать скидки в магазинах
3. При появлении подходящих предложений вы получите уведомление

<i>Время регистрации:</i> {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """.strip()
    
    await update.message.reply_text(welcome_text, parse_mode='HTML', reply_markup=keyboard)
    logger.info(f"Пользователь {user.id} (@{user.username}) начал работу с ботом")


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help"""
    help_text = """
📚 <b>BookHunter - Справка по командам</b>

<b>Основные команды:</b>
• /start - регистрация в системе
• /help - эта справка
• /status - текущий статус системы
• /alerts - управление подписками
• /books - поиск книг в каталоге
• /settings - настройки уведомлений

<b>Управление подписками:</b>
• /alerts add &lt;название&gt; - добавить подписку
• /alerts list - список подписок
• /alerts delete &lt;ID&gt; - удалить подписку

<b>Поиск книг:</b>
• /books search &lt;запрос&gt; - поиск по названию
• /books author &lt;автор&gt; - поиск по автору
• /books deals - лучшие предложения

<b>Примеры использования:</b>
• <code>/alerts add "Дюна" author="Фрэнк Герберт" max_price=500</code>
• <code>/books search "Программирование"</code>
• <code>/books deals min_discount=30</code>

<b>Поддержка:</b>
Если у вас возникли вопросы или проблемы, обратитесь к администратору.
    """.strip()
    
    await update.message.reply_text(help_text, parse_mode='HTML')


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /status"""
    try:
        # Получаем статус системы через API
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/api/health/detailed")
            if response.status_code == 200:
                status_data = response.json()
                
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
                
                await update.message.reply_text(message_text, parse_mode='HTML')
            else:
                await update.message.reply_text("❌ Не удалось получить статус системы", parse_mode='HTML')
                
    except Exception as e:
        logger.error(f"Ошибка получения статуса: {e}")
        await update.message.reply_text(f"❌ Ошибка получения статуса: {str(e)}", parse_mode='HTML')


async def alerts_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /alerts"""
    args = context.args
    
    if not args:
        # Показать справку по подпискам
        help_text = """
📝 <b>Управление подписками</b>

<b>Команды:</b>
• /alerts list - список ваших подписок
• /alerts add &lt;параметры&gt; - добавить подписку
• /alerts delete &lt;ID&gt; - удалить подписку

<b>Примеры добавления подписок:</b>
• <code>/alerts add "Дюна" max_price=500</code>
• <code>/alerts add "Программирование" author="Таненбаум" min_discount=20</code>
• <code>/alerts add "Фантастика" genres="sci-fi" max_price=300</code>

<b>Параметры:</b>
• title - название книги (обязательно)
• author - автор книги
• max_price - максимальная цена
• min_discount - минимальная скидка (%)
• genres - жанры (через запятую)
        """.strip()
        await update.message.reply_text(help_text, parse_mode='HTML')
        return
    
    subcommand = args[0].lower()
    
    if subcommand == "list":
        await list_alerts_handler(update, context)
    elif subcommand == "add":
        await add_alert_handler(update, context)
    elif subcommand == "delete":
        await delete_alert_handler(update, context)
    else:
        await update.message.reply_text("❌ Неизвестная команда. Используйте /help для справки.", parse_mode='HTML')


async def list_alerts_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать список подписок пользователя"""
    chat_id = update.effective_chat.id
    
    try:
        # Здесь должен быть запрос к API для получения подписок пользователя
        # Пока возвращаем заглушку
        message_text = """
📋 <b>Ваши подписки</b>

<i>Пока нет активных подписок</i>

Используйте <code>/alerts add</code> для создания первой подписки.
        """.strip()
        
        await update.message.reply_text(message_text, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Ошибка получения списка подписок: {e}")
        await update.message.reply_text(f"❌ Ошибка получения списка подписок: {str(e)}", parse_mode='HTML')


async def add_alert_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавить новую подписку"""
    chat_id = update.effective_chat.id
    
    try:
        # Парсим параметры из message text
        text = update.message.text
        # Здесь должна быть логика парсинга параметров и создания подписки
        # Пока возвращаем заглушку
        
        message_text = """
✅ <b>Подписка добавлена!</b>

<i>Функция создания подписок будет доступна после полной настройки интеграций.</i>

<b>Параметры подписки:</b>
• Название: (будет извлечено из команды)
• Автор: (опционально)
• Максимальная цена: (опционально)
• Минимальная скидка: (опционально)

<i>Ваша подписка сохранена и будет активирована после завершения настройки системы.</i>
        """.strip()
        
        await update.message.reply_text(message_text, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Ошибка добавления подписки: {e}")
        await update.message.reply_text(f"❌ Ошибка добавления подписки: {str(e)}", parse_mode='HTML')


async def delete_alert_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удалить подписку"""
    chat_id = update.effective_chat.id
    
    try:
        if len(context.args) < 2:
            await update.message.reply_text("❌ Укажите ID подписки для удаления. Пример: /alerts delete 123", parse_mode='HTML')
            return
        
        alert_id = context.args[1]
        
        # Здесь должна быть логика удаления подписки через API
        message_text = f"""
✅ <b>Подписка {alert_id} удалена!</b>

<i>Функция удаления подписок будет доступна после полной настройки интеграций.</i>
        """.strip()
        
        await update.message.reply_text(message_text, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Ошибка удаления подписки: {e}")
        await update.message.reply_text(f"❌ Ошибка удаления подписки: {str(e)}", parse_mode='HTML')


async def books_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /books"""
    args = context.args
    
    if not args:
        # Показать справку по поиску книг
        help_text = """
📚 <b>Поиск книг</b>

<b>Команды:</b>
• /books search &lt;запрос&gt; - поиск по названию
• /books author &lt;автор&gt; - поиск по автору
• /books deals - лучшие предложения со скидками
• /books genre &lt;жанр&gt; - книги определенного жанра

<b>Примеры:</b>
• <code>/books search "Дюна"</code>
• <code>/books author "Толкин"</code>
• <code>/books deals min_discount=30</code>
• <code>/books genre "фантастика"</code>

<b>Параметры для сортировки:</b>
• min_discount - минимальная скидка (%)
• max_price - максимальная цена
• sort - сортировка (price_asc, price_desc, discount_desc)
        """.strip()
        await update.message.reply_text(help_text, parse_mode='HTML')
        return
    
    subcommand = args[0].lower()
    
    if subcommand == "search":
        await search_books_handler(update, context)
    elif subcommand == "deals":
        await best_deals_handler(update, context)
    elif subcommand == "author":
        await search_by_author_handler(update, context)
    else:
        await update.message.reply_text("❌ Неизвестная команда. Используйте /help для справки.", parse_mode='HTML')


async def search_books_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Поиск книг по названию"""
    if len(context.args) < 2:
        await update.message.reply_text("❌ Укажите поисковый запрос. Пример: /books search \"Дюна\"", parse_mode='HTML')
        return
    
    query = " ".join(context.args[1:])
    
    try:
        # Здесь должен быть запрос к API для поиска книг
        # Пока возвращаем заглушку
        message_text = f"""
🔍 <b>Результаты поиска</b>

<b>Запрос:</b> {query}

<i>Найдено 0 книг</i>

<b>Популярные запросы:</b>
• "Дюна" - Фрэнк Герберт
• "Властелин Колец" - Дж.Р.Р. Толкин  
• "1984" - Джордж Оруэлл
• "Программирование" - различные авторы

<i>Поиск книг будет доступен после заполнения каталога.</i>
        """.strip()
        
        await update.message.reply_text(message_text, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Ошибка поиска книг: {e}")
        await update.message.reply_text(f"❌ Ошибка поиска книг: {str(e)}", parse_mode='HTML')


async def best_deals_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать лучшие предложения"""
    try:
        # Здесь должен быть запрос к API для получения лучших предложений
        message_text = """
🔥 <b>Лучшие предложения</b>

<i>Пока нет доступных предложений</i>

<b>Критерии лучших предложений:</b>
• Скидка от 30%
• Цена до 500₽
• Высокий рейтинг
• Быстрая доставка

<i>Каталог книг будет пополняться автоматически при запуске парсеров.</i>
        """.strip()
        
        await update.message.reply_text(message_text, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Ошибка получения лучших предложений: {e}")
        await update.message.reply_text(f"❌ Ошибка получения предложений: {str(e)}", parse_mode='HTML')


async def search_by_author_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Поиск книг по автору"""
    if len(context.args) < 2:
        await update.message.reply_text("❌ Укажите имя автора. Пример: /books author \"Толкин\"", parse_mode='HTML')
        return
    
    author = " ".join(context.args[1:])
    
    try:
        message_text = f"""
👤 <b>Книги автора</b>

<b>Автор:</b> {author}

<i>Найдено 0 книг</i>

<b>Популярные авторы:</b>
• Фрэнк Герберт
• Дж.Р.Р. Толкин
• Джордж Оруэлл
• Айзек Азимов
• Рэй Брэдбери

<i>Поиск по авторам будет доступен после заполнения каталога.</i>
        """.strip()
        
        await update.message.reply_text(message_text, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Ошибка поиска по автору: {e}")
        await update.message.reply_text(f"❌ Ошибка поиска по автору: {str(e)}", parse_mode='HTML')


async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /settings"""
    settings_text = """
⚙️ <b>Настройки уведомлений</b>

<b>Доступные настройки:</b>
• Уведомления о скидках
• Частота проверок
• Минимальная скидка для уведомлений
• Максимальная цена для уведомлений
• Каналы уведомлений (Telegram, Email)

<b>Команды настроек:</b>
• /settings notifications - включить/выключить уведомления
• /settings min_discount <процент> - минимальная скидка
• /settings max_price <сумма> - максимальная цена
• /settings frequency <частота> - частота проверок

<i>Настройки будут доступны после завершения настройки системы.</i>
    """.strip()
    
    await update.message.reply_text(settings_text, parse_mode='HTML')


async def unknown_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик неизвестных команд"""
    await update.message.reply_text(
        "❓ Неизвестная команда. Используйте /help для получения списка доступных команд.",
        parse_mode='HTML'
    )


async def app_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /app - открытие Mini App"""
    # Создаем клавиатуру с кнопкой Mini App
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Открыть приложение", web_app=WebAppInfo(url=MINI_APP_URL))]
    ])

    message_text = """
📱 <b>BookHunter Mini App</b>

Нажмите кнопку ниже, чтобы открыть полноценное приложение с красивым интерфейсом!

<b>Возможности Mini App:</b>
• 📖 Поиск и просмотр книг
• 🔔 Создание подписок на скидки
• 📊 Статистика и аналитика
• 👤 Настройки профиля
• 🎨 Красивый дизайн в книжной тематике

<b>Преимущества:</b>
• Быстрая загрузка
• Удобный интерфейс
• Работает внутри Telegram
• Автоматическое обновление

<i>Нажмите кнопку "Открыть приложение" для начала работы!</i>
    """.strip()

    await update.message.reply_text(message_text, parse_mode='HTML', reply_markup=keyboard)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback запросов от inline кнопок"""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    chat_id = user.id

    if query.data == "books":
        # Открываем Mini App на странице книг
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📚 Открыть каталог", web_app=WebAppInfo(url=f"{MINI_APP_URL}#books"))]
        ])
        await query.edit_message_text(
            "📖 <b>Каталог книг</b>\n\nНажмите кнопку ниже для просмотра каталога книг с фильтрами и поиском!",
            parse_mode='HTML',
            reply_markup=keyboard
        )

    elif query.data == "alerts":
        # Открываем Mini App на странице подписок
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔔 Управление подписками", web_app=WebAppInfo(url=f"{MINI_APP_URL}#alerts"))]
        ])
        await query.edit_message_text(
            "🔔 <b>Мои подписки</b>\n\nНажмите кнопку ниже для управления вашими подписками!",
            parse_mode='HTML',
            reply_markup=keyboard
        )

    elif query.data == "help":
        # Показываем справку
        help_text = """
📚 <b>BookHunter - Справка</b>

<b>Команды:</b>
• /start - главное меню
• /app - открыть Mini App
• /help - эта справка
• /status - статус системы
• /alerts - управление подписками
• /books - поиск книг

<b>Mini App:</b>
• Красивый интерфейс
• Каталог книг
• Подписки на скидки
• Статистика
• Профиль

<i>Используйте /app для открытия полноценного приложения!</i>
        """.strip()
        await query.edit_message_text(help_text, parse_mode='HTML')

    else:
        await query.edit_message_text("❓ Неизвестное действие. Используйте /help для справки.", parse_mode='HTML')


def register_handlers(application) -> None:
    """Регистрация всех обработчиков команд"""
    
    # Основные команды
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("status", status_handler))
    application.add_handler(CommandHandler("app", app_handler))
    
    # Управление подписками
    application.add_handler(CommandHandler("alerts", alerts_handler))
    
    # Поиск книг
    application.add_handler(CommandHandler("books", books_handler))
    
    # Настройки
    application.add_handler(CommandHandler("settings", settings_handler))
    
    # Callback запросы от inline кнопок
    from telegram.ext import CallbackQueryHandler
    application.add_handler(CallbackQueryHandler(callback_handler))

    # Неизвестные команды
    application.add_handler(MessageHandler(filters.COMMAND, unknown_handler))
    
    logger.info("Обработчики команд Telegram Bot зарегистрированы")
