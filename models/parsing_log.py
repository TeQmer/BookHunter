#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модель логов парсинга для системы мониторинга скидок на книги
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, Index
from datetime import datetime
from .base import Base


class ParsingLog(Base):
    """Модель лога процесса парсинга сайтов"""
    
    __tablename__ = "parsing_logs"
    
    # Основные поля
    id = Column(Integer, primary_key=True, index=True)
    
    # Информация о парсинге
    source = Column(String(50), nullable=False, comment="Источник (chitai_gorod, ozon, etc.)")
    task_type = Column(String(50), default="discount_check", comment="Тип задачи парсинга")
    
    # Статус и результаты
    status = Column(String(50), default="running", comment="Статус парсинга")
    is_success = Column(Boolean, default=False, comment="Успешен ли парсинг")
    
    # Статистика
    pages_parsed = Column(Integer, default=0, comment="Количество обработанных страниц")
    books_found = Column(Integer, default=0, comment="Найдено книг")
    books_updated = Column(Integer, default=0, comment="Обновлено книг")
    books_added = Column(Integer, default=0, comment="Добавлено новых книг")
    books_removed = Column(Integer, default=0, comment="Удалено книг")
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow, comment="Время создания записи")
    started_at = Column(DateTime, nullable=False, comment="Время начала парсинга")
    finished_at = Column(DateTime, nullable=True, comment="Время окончания парсинга")
    duration_seconds = Column(Float, nullable=True, comment="Продолжительность в секундах")
    
    # Ошибки и предупреждения
    error_message = Column(Text, nullable=True, comment="Сообщение об ошибке")
    warning_message = Column(Text, nullable=True, comment="Предупреждение")
    
    # Детали процесса
    request_count = Column(Integer, default=0, comment="Количество HTTP запросов")
    successful_requests = Column(Integer, default=0, comment="Успешные HTTP запросы")
    failed_requests = Column(Integer, default=0, comment="Неудачные HTTP запросы")
    
    # Параметры парсинга
    search_query = Column(String(500), nullable=True, comment="Поисковый запрос")
    max_pages = Column(Integer, nullable=True, comment="Максимальное количество страниц")
    rate_limit_delay = Column(Float, default=2.0, comment="Задержка между запросами (сек)")
    
    # Дополнительная информация
    user_agent = Column(String(500), nullable=True, comment="User-Agent для запросов")
    proxy_used = Column(String(100), nullable=True, comment="Использованный прокси")
    ip_address = Column(String(45), nullable=True, comment="IP адрес парсера")
    
    # Метаданные
    extra_metadata = Column(Text, nullable=True, comment="Дополнительные метаданные в JSON")
    
    # Индексы для оптимизации
    __table_args__ = (
        Index('idx_parsing_source_status', 'source', 'status'),
        Index('idx_parsing_created', 'created_at'),
        Index('idx_parsing_started', 'started_at'),
        Index('idx_parsing_success', 'is_success'),
        Index('idx_parsing_duration', 'duration_seconds'),
        Index('idx_parsing_books_found', 'books_found'),
    )
    
    def __repr__(self):
        return f"<ParsingLog(id={self.id}, source='{self.source}', status='{self.status}', books_found={self.books_found})>"
    
    @property
    def display_duration(self):
        """Отформатированная продолжительность"""
        if self.duration_seconds:
            if self.duration_seconds < 60:
                return f"{self.duration_seconds:.1f} сек"
            elif self.duration_seconds < 3600:
                minutes = self.duration_seconds / 60
                return f"{minutes:.1f} мин"
            else:
                hours = self.duration_seconds / 3600
                return f"{hours:.1f} час"
        return "Не завершено"
    
    @property
    def success_rate(self):
        """Процент успешных запросов"""
        if self.request_count > 0:
            return (self.successful_requests / self.request_count) * 100
        return 0
    
    @property
    def display_success_rate(self):
        """Отформатированный процент успешных запросов"""
        rate = self.success_rate
        return f"{rate:.1f}%"
    
    @property
    def is_completed(self):
        """Завершен ли парсинг"""
        return self.status in ["completed", "failed", "cancelled"]
    
    @property
    def net_books_change(self):
        """Чистое изменение количества книг"""
        return self.books_added - self.books_removed
    
    def start_parsing(self):
        """Начать парсинг"""
        if not self.created_at:
            self.created_at = datetime.utcnow()
        self.started_at = datetime.utcnow()
        self.status = "running"
        self.is_success = False
    
    def complete_parsing(self, is_success: bool = True, error_message: str = None):
        """Завершить парсинг"""
        self.finished_at = datetime.utcnow()
        self.status = "completed" if is_success else "failed"
        self.is_success = is_success
        
        if self.started_at:
            self.duration_seconds = (self.finished_at - self.started_at).total_seconds()
        
        if error_message:
            self.error_message = error_message
    
    def add_warning(self, warning_message: str):
        """Добавить предупреждение"""
        if self.warning_message:
            self.warning_message += f"\n{warning_message}"
        else:
            self.warning_message = warning_message
    
    def to_dict(self):
        """Преобразование в словарь для API"""
        return {
            "id": self.id,
            "source": self.source,
            "status": self.status,
            "is_success": self.is_success,
            "is_completed": self.is_completed,
            "pages_parsed": self.pages_parsed,
            "books_found": self.books_found,
            "books_updated": self.books_updated,
            "books_added": self.books_added,
            "books_removed": self.books_removed,
            "net_books_change": self.net_books_change,
            "display_duration": self.display_duration,
            "success_rate": self.success_rate,
            "display_success_rate": self.display_success_rate,
            "request_count": self.request_count,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "error_message": self.error_message,
            "warning_message": self.warning_message,
            "search_query": self.search_query,
            "max_pages": self.max_pages,
            "rate_limit_delay": self.rate_limit_delay,
            "user_agent": self.user_agent,
            "proxy_used": self.proxy_used,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": self.duration_seconds,
            "extra_metadata": self.extra_metadata
        }
