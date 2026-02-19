#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модель уведомлений для системы мониторинга скидок на книги
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base


class Alert(Base):
    """Модель уведомления пользователя о скидке на книгу"""
    
    __tablename__ = "alerts"
    
    # Основные поля
    id = Column(Integer, primary_key=True, index=True)
    
    # Связи
    user_id = Column(Integer, ForeignKey("bh_users.id"), nullable=False, comment="ID пользователя")
    book_id = Column(Integer, ForeignKey("books.id"), nullable=True, comment="ID книги (опционально)")
    
    # Информация о книге для уведомления
    book_title = Column(String(500), nullable=False, comment="Название книги")
    book_author = Column(String(255), nullable=True, comment="Автор книги")
    book_source = Column(String(50), nullable=False, comment="Источник книги")
    
    # Параметры уведомления
    target_price = Column(Float, nullable=True, comment="Целевая цена для уведомления")
    target_discount = Column(Float, nullable=True, comment="Целевая скидка в процентах")
    
    # Фильтры
    min_discount = Column(Float, nullable=True, comment="Минимальная скидка")
    max_price = Column(Float, nullable=True, comment="Максимальная цена")
    author_filter = Column(String(255), nullable=True, comment="Фильтр по автору")
    publisher_filter = Column(String(255), nullable=True, comment="Фильтр по издательству")
    
    # Статус и метаданные
    is_active = Column(Boolean, default=True, comment="Активно ли уведомление")
    notification_type = Column(String(50), default="price_drop", comment="Тип уведомления")
    
    # Статистика
    matches_found = Column(Integer, default=0, comment="Найдено совпадений")
    notifications_sent = Column(Integer, default=0, comment="Отправлено уведомлений")
    last_notification = Column(DateTime, nullable=True, comment="Последнее уведомление")
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow, comment="Дата создания")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="Дата обновления")
    expires_at = Column(DateTime, nullable=True, comment="Дата истечения")
    
    # Дополнительная информация
    notes = Column(Text, nullable=True, comment="Заметки пользователя")
    search_query = Column(String(500), nullable=True, comment="Поисковый запрос")
    
    # Связи
    user = relationship("User", back_populates="alerts")
    book = relationship("Book", back_populates="alerts")
    notifications = relationship("Notification", back_populates="alert", cascade="all, delete-orphan")
    
    # Индексы для оптимизации
    __table_args__ = (
        Index('idx_alert_user_active', 'user_id', 'is_active'),
        Index('idx_alert_source', 'book_source'),
        Index('idx_alert_price', 'target_price'),
        Index('idx_alert_discount', 'target_discount'),
        Index('idx_alert_expires', 'expires_at'),
    )
    
    def __repr__(self):
        return f"<Alert(id={self.id}, user_id={self.user_id}, title='{self.book_title}', target_price={self.target_price})>"
    
    @property
    def is_expired(self):
        """Истекло ли уведомление"""
        return self.expires_at and datetime.utcnow() > self.expires_at
    
    @property
    def display_price(self):
        """Отформатированная целевая цена"""
        if self.target_price:
            return f"{self.target_price:.0f} ₽"
        return None
    
    @property
    def display_discount(self):
        """Отформатированная целевая скидка"""
        if self.target_discount:
            return f"{self.target_discount:.0f}%"
        return None
    
    @property
    def status(self):
        """Статус уведомления"""
        if not self.is_active:
            return "inactive"
        elif self.is_expired:
            return "expired"
        elif self.matches_found > 0:
            return "active"
        else:
            return "pending"
    
    def increment_matches(self):
        """Увеличить счетчик найденных совпадений"""
        self.matches_found += 1
    
    def send_notification(self):
        """Отметить отправку уведомления"""
        self.notifications_sent += 1
        self.last_notification = datetime.utcnow()
    
    def to_dict(self):
        """Преобразование в словарь для API"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "book_id": self.book_id,
            "book_title": self.book_title,
            "book_author": self.book_author,
            "book_source": self.book_source,
            "target_price": self.target_price,
            "display_price": self.display_price,
            "target_discount": self.target_discount,
            "display_discount": self.display_discount,
            "min_discount": self.min_discount,
            "max_price": self.max_price,
            "author_filter": self.author_filter,
            "publisher_filter": self.publisher_filter,
            "is_active": self.is_active,
            "notification_type": self.notification_type,
            "matches_found": self.matches_found,
            "notifications_sent": self.notifications_sent,
            "status": self.status,
            "is_expired": self.is_expired,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "notes": self.notes,
            "search_query": self.search_query,
            "last_notification": self.last_notification.isoformat() if self.last_notification else None
        }
