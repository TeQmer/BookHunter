"""Модель для хранения шаблонов уведомлений"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.sql import func
from database.base import Base


class NotificationTemplate(Base):
    """Таблица для хранения шаблонов уведомлений"""
    __tablename__ = "notification_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)  # Уникальное имя шаблона
    title = Column(String(200), nullable=True)  # Заголовок уведомления
    message = Column(Text, nullable=False)  # Текст шаблона (поддерживает {placeholders})
    template_type = Column(String(50), nullable=False, index=True)  # 'subscription_match', 'token_error', 'parsing_complete', 'daily_digest'
    is_active = Column(Boolean, default=True)  # Активен ли шаблон
    description = Column(String(500), nullable=True)  # Описание шаблона
    placeholders = Column(Text, nullable=True)  # JSON массив доступных плейсхолдеров
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<NotificationTemplate {self.name}>"
    
    def get_placeholders_list(self):
        """Получение списка плейсхолдеров"""
        if self.placeholders:
            import json
            return json.loads(self.placeholders)
        return []
