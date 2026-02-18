#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модель пользователей для системы мониторинга скидок на книги
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base


class User(Base):
    """Модель пользователя системы"""
    
    __tablename__ = "users"
    
    # Основные поля
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False, comment="ID пользователя в Telegram")
    username = Column(String(255), nullable=True, comment="Username в Telegram")
    first_name = Column(String(255), nullable=False, comment="Имя пользователя")
    last_name = Column(String(255), nullable=True, comment="Фамилия пользователя")
    
    # Настройки и статус
    is_active = Column(Boolean, default=True, comment="Активен ли пользователь")
    language_code = Column(String(10), default="ru", comment="Язык интерфейса")
    timezone = Column(String(50), default="Europe/Moscow", comment="Часовой пояс")
    
    # Статистика
    total_alerts = Column(Integer, default=0, comment="Всего созданных уведомлений")
    notifications_sent = Column(Integer, default=0, comment="Отправлено уведомлений")
    
    # Лимиты запросов (задача #6)
    daily_requests_used = Column(Integer, default=0, comment="Количество запросов за текущий день")
    daily_requests_limit = Column(Integer, default=15, comment="Лимит запросов в день")
    requests_updated_at = Column(DateTime, default=datetime.utcnow, comment="Дата обновления счетчика запросов")
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow, comment="Дата регистрации")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="Дата последнего обновления")
    last_activity = Column(DateTime, nullable=True, comment="Последняя активность")
    
    # Связи
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username='{self.username}')>"
    
    @property
    def display_name(self):
        """Отображаемое имя пользователя"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.username:
            return f"@{self.username}"
        else:
            return f"User {self.telegram_id}"
    
    def to_dict(self):
        """Преобразование в словарь для API"""
        return {
            "id": self.id,
            "telegram_id": self.telegram_id,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "display_name": self.display_name,
            "is_active": self.is_active,
            "language_code": self.language_code,
            "timezone": self.timezone,
            "total_alerts": self.total_alerts,
            "notifications_sent": self.notifications_sent,
            "daily_requests_used": self.daily_requests_used,
            "daily_requests_limit": self.daily_requests_limit,
            "requests_remaining": max(0, self.daily_requests_limit - self.daily_requests_used),
            "requests_updated_at": self.requests_updated_at.isoformat() if self.requests_updated_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None
        }
