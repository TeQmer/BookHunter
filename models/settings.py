"""Модель для хранения настроек системы"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.sql import func
from models.base import Base


class Settings(Base):
    """Таблица для хранения настроек системы"""
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)  # Уникальный ключ настройки
    value = Column(Text, nullable=True)  # Значение настройки
    value_type = Column(String(20), default='string')  # 'string', 'int', 'float', 'bool', 'json'
    description = Column(String(500), nullable=True)  # Описание настройки
    category = Column(String(50), nullable=True, index=True)  # Категория настройки
    is_public = Column(Boolean, default=False)  # Доступно ли для изменения через API
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Settings {self.key}={self.value}>"
    
    def get_value(self):
        """Получение значения с правильным типом"""
        if self.value_type == 'int':
            return int(self.value) if self.value else 0
        elif self.value_type == 'float':
            return float(self.value) if self.value else 0.0
        elif self.value_type == 'bool':
            return self.value.lower() in ('true', '1', 'yes') if self.value else False
        elif self.value_type == 'json':
            import json
            return json.loads(self.value) if self.value else {}
        return self.value
    
    def set_value(self, value, value_type=None):
        """Установка значения с автоматическим определением типа"""
        if value_type is None:
            if isinstance(value, bool):
                self.value_type = 'bool'
            elif isinstance(value, int):
                self.value_type = 'int'
            elif isinstance(value, float):
                self.value_type = 'float'
            elif isinstance(value, dict) or isinstance(value, list):
                self.value_type = 'json'
                import json
                value = json.dumps(value)
            else:
                self.value_type = 'string'
        else:
            self.value_type = value_type
            if value_type == 'json':
                import json
                value = json.dumps(value)
        
        self.value = str(value)
