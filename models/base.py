#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Базовый класс для SQLAlchemy моделей
"""

from sqlalchemy.ext.declarative import declarative_base

# Создаем базовый класс для всех моделей
Base = declarative_base()
