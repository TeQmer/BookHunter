"""Модель для отслеживания активности пользователей"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean
from sqlalchemy.sql import func
from models.base import Base


class UserActivity(Base):
    """Таблица для хранения активности пользователей в Telegram Mini App"""
    __tablename__ = "user_activities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), nullable=False, index=True)  # Telegram ID пользователя
    session_id = Column(String(100), nullable=True, index=True)  # ID сессии
    
    # Тип активности
    activity_type = Column(String(50), nullable=False)  # 'page_view', 'search', 'alert_created', 'alert_deleted', 'book_viewed', 'navigation'
    
    # Дополнительные данные
    page = Column(String(100), nullable=True)  # Название страницы
    query = Column(Text, nullable=True)  # Поисковый запрос
    book_id = Column(Integer, nullable=True)  # ID книги (если применимо)
    alert_id = Column(Integer, nullable=True)  # ID подписки (если применимо)
    
    # Время
    duration_seconds = Column(Float, nullable=True)  # Продолжительность сессии/действия
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Дополнительная информация
    user_agent = Column(String(500), nullable=True)
    platform = Column(String(50), nullable=True)  # 'telegram_ios', 'telegram_android', 'web'
    
    def __repr__(self):
        return f"<UserActivity {self.id}: {self.user_id} - {self.activity_type}>"
