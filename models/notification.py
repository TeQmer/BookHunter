#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модель уведомлений для системы мониторинга скидок на книги
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Index, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base


class Notification(Base):
    """Модель уведомлений (соответствует реальной схеме базы данных)"""
    
    __tablename__ = "notifications"
    
    # Основные поля
    id = Column(Integer, primary_key=True, index=True)
    
    # Связи
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False, comment="ID пользователя")
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False, comment="ID подписки")
    book_id = Column(Integer, ForeignKey("books.id"), nullable=True, comment="ID книги")
    
    # Информация о книге (соответствует схеме БД)
    book_title = Column(String(500), nullable=False, comment="Название книги")
    book_author = Column(String(255), nullable=True, comment="Автор книги")
    book_price = Column(String(50), nullable=True, comment="Цена книги")
    book_discount = Column(String(20), nullable=True, comment="Размер скидки")
    book_url = Column(String(1000), nullable=True, comment="URL книги")
    
    # Информация об уведомлении
    message = Column(Text, nullable=False, comment="Текст уведомления")
    message_type = Column(String(50), default='text', comment="Тип сообщения")
    channel = Column(String(50), default='telegram', comment="Канал отправки")
    telegram_message_id = Column(String(100), nullable=True, comment="ID сообщения в Telegram")
    
    # Статусы отправки
    status = Column(String(50), default='pending', comment="Статус уведомления")
    is_sent = Column(Boolean, default=False, comment="Отправлено ли уведомление")
    sent_at = Column(DateTime, nullable=True, comment="Время отправки")
    error_message = Column(Text, nullable=True, comment="Сообщение об ошибке")
    
    # Логика повторных попыток
    retry_count = Column(Integer, default=0, comment="Количество попыток")
    max_retries = Column(Integer, default=3, comment="Максимальное количество попыток")
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow, comment="Дата создания")
    scheduled_for = Column(DateTime, nullable=True, comment="Запланированное время отправки")
    
    # Временные метки (только основные, которые точно существуют в БД)
    # created_at уже определен выше
    
    # Связи
    user = relationship("User", back_populates="notifications")
    book = relationship("Book", back_populates="notifications")
    alert = relationship("Alert", back_populates="notifications")
    
    # Индексы для оптимизации
    __table_args__ = (
        Index('idx_notification_user', 'user_id'),
        Index('idx_notification_alert', 'alert_id'),
        Index('idx_notification_status', 'status'),
        Index('idx_notification_sent', 'is_sent', 'sent_at'),
        Index('idx_notification_scheduled', 'scheduled_for'),
        Index('idx_notification_created', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Notification(id={self.id}, user_id={self.user_id}, title='{self.book_title}')>"
    
    def to_dict(self):
        """Преобразование в словарь для API"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "alert_id": self.alert_id,
            "book_id": self.book_id,
            "book_title": self.book_title,
            "book_author": self.book_author,
            "book_price": self.book_price,
            "book_discount": self.book_discount,
            "book_url": self.book_url,
            "message": self.message,
            "message_type": self.message_type,
            "channel": self.channel,
            "telegram_message_id": self.telegram_message_id,
            "status": self.status,
            "is_sent": self.is_sent,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None
        }
