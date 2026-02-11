#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модели данных для системы мониторинга скидок на книги
"""

from .base import Base
from .user import User
from .book import Book
from .alert import Alert
from .notification import Notification
from .parsing_log import ParsingLog

__all__ = [
    "Base",
    "User",
    "Book", 
    "Alert",
    "Notification",
    "ParsingLog"
]
