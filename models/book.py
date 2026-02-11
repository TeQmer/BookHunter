#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модель книг для системы мониторинга скидок на книги
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base


class Book(Base):
    """Модель книги в системе мониторинга"""
    
    __tablename__ = "books"
    
    # Основные поля
    id = Column(Integer, primary_key=True, index=True)
    
    # Информация о книге
    title = Column(String(500), nullable=False, comment="Название книги")
    author = Column(String(255), nullable=True, comment="Автор")
    publisher = Column(String(255), nullable=True, comment="Издательство")
    binding = Column(String(100), nullable=True, comment="Переплёт")
    isbn = Column(String(20), nullable=True, comment="ISBN")
    
    # Ценовая информация
    current_price = Column(Numeric(10, 2), nullable=False, comment="Текущая цена")
    original_price = Column(Numeric(10, 2), nullable=True, comment="Оригинальная цена")
    discount_percent = Column(Integer, nullable=True, comment="Размер скидки в процентах")
    
    # Информация о товаре
    url = Column(String(1000), nullable=False, comment="Ссылка на товар")
    image_url = Column(String(1000), nullable=True, comment="Ссылка на изображение")
    genres = Column(Text, nullable=True, comment="Жанры книги")
    
    # Магазин и источник
    source = Column(String(100), nullable=False, comment="Название магазина")
    source_id = Column(String(255), nullable=False, comment="ID товара в магазине")
    
    # Время парсинга
    parsed_at = Column(DateTime, nullable=True, comment="Время парсинга данных")
    
    # Связи
    alerts = relationship("Alert", back_populates="book", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="book", cascade="all, delete-orphan")
    
    # Индексы для оптимизации поиска
    __table_args__ = (
        Index('idx_book_title_author', 'title', 'author'),
        Index('idx_book_source_price', 'source', 'current_price'),
        Index('idx_book_discount', 'discount_percent'),
        Index('idx_book_parsed_at', 'parsed_at'),
        Index('books_source_source_id_key', 'source', 'source_id'),
    )
    
    def __repr__(self):
        return f"<Book(id={self.id}, title='{self.title}', author='{self.author}', price={self.current_price})>"
    
    @property
    def display_price(self):
        """Отформатированная цена для отображения"""
        if self.current_price:
            return f"{float(self.current_price):.0f} ₽"
        return "Не указано"
    
    @property
    def display_original_price(self):
        """Отформатированная оригинальная цена"""
        if self.original_price:
            return f"{float(self.original_price):.0f} ₽"
        return None
    
    @property
    def display_discount(self):
        """Отформатированная скидка"""
        if self.discount_percent:
            return f"{self.discount_percent}%"
        return None
    
    @property
    def is_discounted(self):
        """Есть ли скидка на книгу"""
        return self.discount_percent and self.discount_percent > 0
    
    def to_dict(self):
        """Преобразование в словарь для API"""
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "publisher": self.publisher,
            "binding": self.binding,
            "isbn": self.isbn,
            "current_price": float(self.current_price) if self.current_price else 0,
            "original_price": float(self.original_price) if self.original_price else 0,
            "discount_percent": self.discount_percent,
            "display_price": self.display_price,
            "display_original_price": self.display_original_price,
            "display_discount": self.display_discount,
            "is_discounted": self.is_discounted,
            "url": self.url,
            "image_url": self.image_url,
            "genres": self.genres,
            "source": self.source,
            "source_id": self.source_id,
            "parsed_at": self.parsed_at.isoformat() if self.parsed_at else None
        }
