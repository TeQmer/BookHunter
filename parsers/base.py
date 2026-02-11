from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import random
import aiohttp
from pydantic import BaseModel, Field
from services.logger import parser_logger

class Book(BaseModel):
    """Модель книги для унификации данных от всех парсеров"""
    source: str = Field(..., description="Название источника (chitai-gorod, ozon, etc.)")
    source_id: str = Field(..., description="ID книги в магазине")
    title: str = Field(..., description="Название книги")
    author: Optional[str] = Field(None, description="Автор книги")
    publisher: Optional[str] = Field(None, description="Издательство")
    binding: Optional[str] = Field(None, description="Переплёт")
    current_price: float = Field(..., description="Текущая цена")
    original_price: Optional[float] = Field(None, description="Изначальная цена")
    discount_percent: Optional[int] = Field(None, description="Процент скидки")
    url: str = Field(..., description="Ссылка на книгу")
    image_url: Optional[str] = Field(None, description="URL обложки книги")
    genres: Optional[List[str]] = Field(None, description="Список жанров")
    isbn: Optional[str] = Field(None, description="ISBN книги")
    parsed_at: datetime = Field(default_factory=datetime.now, description="Время парсинга")
    
    def __str__(self) -> str:
        return f"{self.title} by {self.author or 'Unknown'} - {self.current_price}₽"

class BaseParser(ABC):
    """Абстрактный базовый класс для всех парсеров магазинов"""
    
    def __init__(self, name: str, delay_min: int = 1, delay_max: int = 3):
        self.name = name
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.logger = parser_logger
        
    async def _random_delay(self):
        """Случайная задержка между запросами"""
        delay = random.uniform(self.delay_min, self.delay_max)
        await asyncio.sleep(delay)
        
    async def _make_request(self, url: str, headers: Dict[str, str] = None) -> Optional[str]:
        """Выполнение HTTP запроса с обработкой ошибок"""
        if headers is None:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
        for attempt in range(3):  # До 3 попыток
            try:
                await self._random_delay()
                
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=30),
                    headers=headers
                ) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            return await response.text()
                        else:
                            self.logger.warning(
                                f"HTTP {response.status} for {url}"
                            )
                            
            except asyncio.TimeoutError:
                self.logger.warning(f"Timeout for {url} (attempt {attempt + 1})")
            except Exception as e:
                self.logger.error(f"Request error for {url}: {e} (attempt {attempt + 1})")
                
            if attempt < 2:  # Не ждем после последней попытки
                await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
                
        return None
    
    @abstractmethod
    async def search_books(self, query: str) -> List[Book]:
        """Поиск книг по названию/автору
        
        Args:
            query: Строка поиска (название или автор)
            
        Returns:
            Список найденных книг
        """
        pass
    
    @abstractmethod
    async def get_book_details(self, url: str) -> Optional[Book]:
        """Получение детальной информации о книге
        
        Args:
            url: Ссылка на книгу
            
        Returns:
            Объект Book с детальной информацией или None
        """
        pass
    
    @abstractmethod
    async def check_discounts(self) -> List[Book]:
        """Сканирование акционных страниц
        
        Returns:
            Список книг со скидками
        """
        pass
    
    def calculate_discount(self, current_price: float, original_price: float) -> Optional[int]:
        """Вычисление процента скидки"""
        if original_price and original_price > current_price:
            discount = round(((original_price - current_price) / original_price) * 100)
            return max(0, discount)
        return None
    
    def validate_book_data(self, book_data: Dict[str, Any]) -> bool:
        """Валидация данных книги"""
        required_fields = ['title', 'current_price', 'url']
        return all(field in book_data and book_data[field] for field in required_fields)
    
    async def log_operation(self, operation: str, status: str, message: str = "", books_found: int = 0):
        """Логирование операций парсера"""
        self.logger.info(f"[{self.name}] {operation}: {status} - {message} (found: {books_found})")
        
    def __str__(self) -> str:
        return f"Parser({self.name})"
