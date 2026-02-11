from typing import Dict, Type
from parsers.base import BaseParser
from services.logger import parser_logger

# Импортируем парсеры (пока только ChitaiGorod)
try:
    from parsers.chitai_gorod import ChitaiGorodParser
    PARSERS_AVAILABLE = True
except ImportError as e:
    parser_logger.warning(f"Не удалось загрузить парсеры: {e}")
    PARSERS_AVAILABLE = False
    ChitaiGorodParser = None

class ParserFactory:
    """Фабрика для создания парсеров магазинов"""
    
    def __init__(self):
        self._parsers: Dict[str, Type[BaseParser]] = {}
        self._load_parsers()
    
    def _load_parsers(self):
        """Загрузка доступных парсеров"""
        if not PARSERS_AVAILABLE:
            parser_logger.warning("Парсеры недоступны")
            return
        
        # Регистрируем парсер "Читай-город"
        if ChitaiGorodParser:
            self._parsers["chitai-gorod"] = ChitaiGorodParser
            parser_logger.info("Парсер 'Читай-город' загружен")
    
    def get_parser(self, source_name: str) -> BaseParser:
        """Получение парсера по названию источника"""
        if source_name not in self._parsers:
            raise ValueError(f"Неизвестный источник: {source_name}")
        
        parser_class = self._parsers[source_name]
        return parser_class()
    
    def get_available_parsers(self) -> Dict[str, BaseParser]:
        """Получение всех доступных парсеров"""
        return {name: self._parsers[name]() for name in self._parsers.keys()}
    
    def get_supported_sources(self) -> list:
        """Получение списка поддерживаемых источников"""
        return list(self._parsers.keys())
    
    def register_parser(self, source_name: str, parser_class: Type[BaseParser]):
        """Регистрация нового парсера"""
        self._parsers[source_name] = parser_class
        parser_logger.info(f"Зарегистрирован парсер для источника: {source_name}")

# Глобальный экземпляр фабрики
parser_factory = ParserFactory()
