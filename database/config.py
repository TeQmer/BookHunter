import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import MetaData, create_engine
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# URL базы данных (обязательная переменная окружения)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is required! "
        "Please set it in your .env file or environment."
    )

# Преобразуем асинхронный URL в синхронный
SYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

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
_sync_engine = None
_SyncSessionLocal = None

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

def get_sync_engine():
    """Получение или создание синхронного движка"""
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(
            SYNC_DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    return _sync_engine

def get_session_factory():
    """Получение или создание фабрики асинхронных сессий"""
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        engine = get_engine()
        _AsyncSessionLocal = sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    return _AsyncSessionLocal

def get_sync_session_factory():
    """Получение или создание фабрики синхронных сессий"""
    global _SyncSessionLocal
    if _SyncSessionLocal is None:
        engine = get_sync_engine()
        _SyncSessionLocal = sessionmaker(
            engine,
            class_=Session,
            expire_on_commit=False
        )
    return _SyncSessionLocal

async def get_db() -> AsyncSession:
    """Получение асинхронной сессии базы данных"""
    SessionLocal = get_session_factory()
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

def get_sync_db():
    """Получение синхронной сессии базы данных"""
    SessionLocal = get_sync_session_factory()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

async def init_db():
    """Инициализация базы данных с импортом моделей"""
    # Импортируем модели для их регистрации в Base.metadata
    from models import User, Book, Alert, Notification, ParsingLog, Base
    from models.user_activity import UserActivity
    from models.settings import Settings
    from models.notification_template import NotificationTemplate
    
    async with get_engine().begin() as conn:
        # Создаем все таблицы (checkfirst=True пропускает уже существующие)
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)
        print("Database tables created successfully")

async def close_db():
    """Закрытие соединения с базой данных"""
    engine = get_engine()
    await engine.dispose()

    # Закрываем синхронный движок
    global _sync_engine
    if _sync_engine:
        _sync_engine.dispose()

__all__ = [
    "get_engine",
    "get_sync_engine",
    "get_session_factory", 
    "get_sync_session_factory",
    "get_db",
    "get_sync_db",
    "init_db",
    "close_db"
]
