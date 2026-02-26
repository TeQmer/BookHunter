"""Менеджер для работы с настройками системы"""
import logging

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = [
    # Настройки подписок
    {
        "key": "subscriptions_check_interval",
        "value": "14400",
        "value_type": "int",
        "description": "Интервал проверки подписок в секундах (по умолчанию 4 часа)",
        "category": "subscriptions"
    },
    # Настройки парсинга
    {
        "key": "parsing_delay_seconds",
        "value": "2",
        "value_type": "int",
        "description": "Задержка между запросами при парсинге",
        "category": "parsing"
    },
    # Настройки уведомлений
    {
        "key": "notifications_enabled",
        "value": "true",
        "value_type": "bool",
        "description": "Включены ли уведомления",
        "category": "notifications"
    },
]


async def init_default_settings():
    """Инициализация настроек по умолчанию, если они не существуют"""
    from database.config import get_session_factory
    from models.settings import Settings
    from sqlalchemy import select
    
    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            for setting in DEFAULT_SETTINGS:
                # Проверяем существует ли настройка
                result = await db.execute(
                    select(Settings).where(Settings.key == setting["key"])
                )
                existing = result.scalar_one_or_none()
                
                if not existing:
                    new_setting = Settings(
                        key=setting["key"],
                        value=setting["value"],
                        value_type=setting["value_type"],
                        description=setting["description"],
                        category=setting["category"]
                    )
                    db.add(new_setting)
                    logger.info(f"Создана настройка по умолчанию: {setting['key']}")
            
            await db.commit()
            logger.info("Инициализация настроек завершена")
        except Exception as e:
            logger.error(f"Ошибка инициализации настроек: {e}")
            await db.rollback()


async def get_setting_value(key: str, default=None):
    """Получение значения настройки"""
    from database.config import get_session_factory
    from models.settings import Settings
    from sqlalchemy import select
    
    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            result = await db.execute(
                select(Settings).where(Settings.key == key)
            )
            setting = result.scalar_one_or_none()
            
            if setting:
                return setting.get_value()
            return default
        except Exception as e:
            logger.error(f"Ошибка получения настройки {key}: {e}")
            return default


async def set_setting_value(key: str, value, value_type: str = None):
    """Установка значения настройки"""
    from database.config import get_session_factory
    from models.settings import Settings
    from sqlalchemy import select
    
    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            result = await db.execute(
                select(Settings).where(Settings.key == key)
            )
            setting = result.scalar_one_or_none()
            
            if setting:
                setting.set_value(value, value_type)
            else:
                new_setting = Settings(key=key)
                new_setting.set_value(value, value_type)
                db.add(new_setting)
            
            await db.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка установки настройки {key}: {e}")
            await db.rollback()
            return False
