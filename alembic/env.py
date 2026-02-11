import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

# Добавляем путь к корню проекта в sys.path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Импортируем настройки базы данных
from database.config import DATABASE_URL

# Настройки Alembic
config = context.config

# Устанавливаем URL базы данных из переменной окружения
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Импортируем все модели для автогенерации миграций
from models import Base
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Запуск миграций в 'оффлайн' режиме."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Запуск миграций в 'онлайн' режиме."""
    # Для SQLite используем синхронное подключение
    if "sqlite" in DATABASE_URL:
        sync_url = DATABASE_URL.replace("sqlite+aiosqlite://", "sqlite://")
        connectable = engine_from_config(
            {"sqlalchemy.url": sync_url},
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
    else:
        # Для PostgreSQL используем синхронный драйвер psycopg2 вместо asyncpg
        # Alembic работает только с синхронными драйверами
        sync_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        connectable = engine_from_config(
            {"sqlalchemy.url": sync_url},
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
