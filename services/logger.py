import logging
import sys
import os
from datetime import datetime
from pathlib import Path

def setup_logger(name: str = None, level: str = "INFO") -> logging.Logger:
    """Настройка логгера для приложения"""
    
    # Создаем директорию для логов если её нет
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Создаем имя логгера
    logger = logging.getLogger(name or __name__)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Очищаем существующие обработчики
    logger.handlers.clear()
    
    # Форматтер для логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Обработчик для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Обработчик для файла
    today = datetime.now().strftime('%Y-%m-%d')
    file_handler = logging.FileHandler(
        log_dir / f'app_{today}.log',
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Обработчик для ошибок в отдельный файл
    error_handler = logging.FileHandler(
        log_dir / f'errors_{today}.log',
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)
    
    return logger

# Основной логгер приложения
logger = setup_logger("book_discount_monitor", "INFO")

# Логгер для Celery задач
celery_logger = setup_logger("celery", "INFO")

# Логгер для парсеров
parser_logger = setup_logger("parsers", "INFO")

# Логгер для веб-интерфейса
web_logger = setup_logger("web", "INFO")

# Логгер для Telegram бота
bot_logger = setup_logger("telegram", "INFO")

# Логгер для API
api_logger = setup_logger("api", "INFO")
