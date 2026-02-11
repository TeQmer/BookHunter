import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import MetaData
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# URL базы данных
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://bookuser:bookpass@postgres:5432/book_discounts"
)

# Безопасное логирование: скрываем пароль
safe_db_url = DATABASE_URL
if "@" in DATABASE_URL:
    # Заменяем пароль в URL на ***
    parts = DATABASE_URL.split("@")
    if "://" in parts[0]:
        protocol = parts[0].split("://")[0]
        credentials = parts[0].split("://")[1]
        if ":" in credentials:
            user = credentials.split(":")[0]
            safe_db_url = f"{protocol}://{user}:***@{parts[1]}"

print(f"Using database: {safe_db_url}")

# Глобальные переменные для движка и сессии
_engine = None
_AsyncSessionLocal = None

def get_engine():
    """Получение или создание асинхронного движка"""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            DATABASE_URL,
            echo=False,  # Отключаем логирование для продакшена
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    return _engine

def get_session_factory():
    """Получение или создание фабрики сессий"""
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        engine = get_engine()
        _AsyncSessionLocal = sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    return _AsyncSessionLocal

async def get_db() -> AsyncSession:
    """Получение асинхронной сессии базы данных"""
    SessionLocal = get_session_factory()
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    """Инициализация базы данных с импортом моделей"""
    # Импортируем модели для их регистрации в Base.metadata
    from models import User, Book, Alert, Notification, ParsingLog, Base
    
    async with get_engine().begin() as conn:
        # Создаем все таблицы
        await conn.run_sync(Base.metadata.create_all)
        print("Database tables created successfully")

async def close_db():
    """Закрытие соединения с базой данных"""
    engine = get_engine()
    await engine.dispose()

__all__ = [
    "get_engine",
    "get_session_factory", 
    "get_db",
    "init_db",
    "close_db"
]
