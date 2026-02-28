"""
Парсер для магазина 'Читай-город' с использованием API (оптимизирован)

Использует API вместо HTML парсинга:
- Быстрее и надежнее
- Меньше нагрузка на сервер
- Структурированные данные
"""

import asyncio
import time
from typing import List, Optional
from datetime import datetime
from parsers.base import BaseParser, Book
from services.chitai_gorod_api_client import ChitaiGorodAPIClient, ChitaiGorodBook
from services.logger import parser_logger


class ChitaiGorodParser(BaseParser):
    """Парсер для магазина 'Читай-город' с использованием API (оптимизирован)"""

    def __init__(self):
        # Оптимизированные задержки для быстрого парсинга
        super().__init__("chitai-gorod", delay_min=0.5, delay_max=1.5)
        self.api_client = ChitaiGorodAPIClient(
            delay_min=self.delay_min,
            delay_max=self.delay_max
        )
        
    async def search_books(
        self,
        query: str,
        max_pages: int = 1,
        limit: int = None,
        fetch_details: bool = False
    ) -> List[Book]:
        """
        Поиск книг на сайте chitai-gorod.ru через API
        
        Args:
            query: Поисковый запрос
            max_pages: Максимальное количество страниц для поиска
            limit: Максимальное количество книг для возврата
            fetch_details: Загружать ли детальную информацию (всегда True для API)
            
        Returns:
            Список найденных книг
        """
        await self.log_operation("search", "info", f"Поиск книг по запросу: {query}")
        
        # Замеряем время выполнения
        search_start = time.time()

        try:
            all_books = []
            
            for page in range(1, max_pages + 1):
                # Ищем товары через API
                api_books = await self.api_client.search_products(
                    phrase=query,
                    page=page,
                    per_page=60
                )
                
                # Преобразуем в стандартную модель Book
                books = [self._api_book_to_book(book) for book in api_books]
                books = [book for book in books if book is not None]  # Убираем None
                
                all_books.extend(books)
                
                # Если на странице нет результатов, прерываем
                if not api_books:
                    break
                
                # Если достигли лимита, прерываем
                if limit and len(all_books) >= limit:
                    all_books = all_books[:limit]
                    break
            
            await self.log_operation(
                "search",
                "success",
                f"Найдено книг: {len(all_books)}",
                len(all_books)
            )
            
            # Логируем время выполнения поиска
            search_time = time.time() - search_start
            parser_logger.info(f"⏱️ Поиск занял: {search_time:.2f} сек")

            return all_books
            
        except Exception as e:
            await self.log_operation("search", "error", f"Ошибка поиска: {e}")
            return []
    
    async def get_book_details(self, url: str) -> Optional[Book]:
        """
        Получение детальной информации о книге
        
        Args:
            url: Ссылка на книгу
            
        Returns:
            Объект Book с детальной информацией или None
        """
        await self.log_operation("details", "info", f"Получение деталей книги: {url}")
        
        # API возвращает все детали при поиске, поэтому отдельный метод не нужен
        # Можно извлечь ID книги из URL и сделать поиск по ID, но это сложнее
        
        # Для совместимости с интерфейсом BaseParser
        # В будущем можно добавить endpoint для получения деталей по ID
        
        await self.log_operation(
            "details",
            "warning",
            "API возвращает все детали при поиске. Используйте search_books()."
        )
        
        return None
    
    async def check_discounts(self) -> List[Book]:
        """
        Сканирование акционных предложений
        
        Returns:
            Список книг со скидками
        """
        await self.log_operation("discounts", "info", "Сканирование акционных предложений")
        
        all_discount_books = []
        
        # Популярные категории и запросы для поиска скидок
        popular_queries = [
            "книги", "программирование", "python", "javascript", "java",
            "математика", "бизнес", "психология", "фантастика", "детектив"
        ]
        
        for query in popular_queries:
            try:
                # Ищем книги
                books = await self.search_books(query, max_pages=1)
                
                # Фильтруем только книги со скидками 15% и больше
                discount_books = [
                    book for book in books
                    if book.discount_percent and book.discount_percent >= 15
                ]
                
                all_discount_books.extend(discount_books)
                
            except Exception as e:
                await self.log_operation(
                    "discounts",
                    "warning",
                    f"Ошибка при поиске '{query}': {e}"
                )
        
        # Удаляем дубликаты по source_id
        unique_books = []
        seen_ids = set()
        for book in all_discount_books:
            if book.source_id not in seen_ids:
                unique_books.append(book)
                seen_ids.add(book.source_id)
        
        # Сортируем по убыванию скидки
        unique_books.sort(key=lambda x: x.discount_percent or 0, reverse=True)
        
        await self.log_operation(
            "discounts",
            "success",
            f"Найдено акционных книг: {len(unique_books)}",
            len(unique_books)
        )
        
        return unique_books
    
    def _api_book_to_book(self, api_book: ChitaiGorodBook) -> Optional[Book]:
        """
        Преобразование модели API в стандартную модель Book
        
        Args:
            api_book: Книга из API
            
        Returns:
            Стандартная модель Book или None
        """
        try:
            # Проверяем, что это реальная книга
            if not self._is_real_book(api_book):
                return None
            
            # Проверяем, что это не исключенный контент
            if self._is_excluded_content(api_book.title, api_book.author):
                return None
            
            # Создаем стандартную модель Book
            book = Book(
                source="chitai-gorod",
                source_id=api_book.source_id,
                title=api_book.title,
                author=api_book.author,
                publisher=api_book.publisher,
                binding=api_book.binding,
                current_price=api_book.current_price,
                original_price=api_book.original_price,
                discount_percent=api_book.discount_percent,
                url=api_book.url,
                image_url=api_book.image_url,
                genres=api_book.genres,
                isbn=None,  # API не возвращает ISBN
                parsed_at=api_book.parsed_at or datetime.now()
            )
            
            return book
            
        except Exception as e:
            self.logger.warning(f"Ошибка при преобразовании книги: {e}")
            return None
    
    def _is_real_book(self, api_book: ChitaiGorodBook) -> bool:
        """
        Проверка, что это реальная книга, а не другой товар
        
        Args:
            api_book: Книга из API
            
        Returns:
            True если это книга, False если нет
        """
        title = api_book.title.lower() if api_book.title else ""
        
        # Исключаем явно не книги
        non_book_keywords = [
            'игра', 'игрушка', 'конструктор', 'пазл', 'кубики', 'тетрадь', 'блокнот',
            'планнер', 'ежедневник', 'записная книжка', 'канцтовары', 'офисные товары'
        ]
        
        for keyword in non_book_keywords:
            if keyword in title:
                return False
        
        # Проверяем, что цена разумная для книги
        price = api_book.current_price
        if price < 50 or price > 5000:
            return False
        
        # Проверяем, что книга есть в наличии или предзаказ
        if api_book.status and api_book.status not in ['canBuy', 'preOrder', 'offline']:
            return False
        
        return True
    
    def _is_excluded_content(self, title: str, author: str = None) -> bool:
        """
        Проверка, является ли контент исключаемым (детские книги и т.д.)
        
        Args:
            title: Название книги
            author: Автор книги
            
        Returns:
            True если контент исключен, False если нет
        """
        # Объединяем заголовок и автора для анализа
        text_to_check = f"{title} {author or ''}".lower()
        
        # Исключаемые категории
        excluded_keywords = [
            # Детские товары
            'для детей', 'детская', 'детские', 'дошкольник', 'дошкольная', 'дошкольное',
            'малыш', 'малыша', 'ребенок', 'детский', 'детского', 'детских',
            'книжка-картинка', 'книжка с картинками', 'раскраска', 'раскраски',
            'прописи', 'пропись', 'азбука', 'букварь', 'слог', 'слоги',
            
            # Игры и игрушки
            'игра', 'игры', 'игрушка', 'игрушки', 'пазл', 'пазлы', 'конструктор',
            'кубики', 'мягкая игрушка', 'плюшевый', 'плюшевая', 'плюшевое',
            'настольная игра', 'настольные игры', 'детская игра', 'детские игры',
            
            # Канцелярские товары
            'тетрадь', 'тетради', 'планнер', 'планнеры', 'ежедневник', 'ежедневники',
            'блокнот', 'блокноты', 'записная книжка', 'записные книжки',
            'канцтовары', 'канцелярские товары', 'офисные товары',
            
            # Развивающие материалы
            'развивающая', 'развивающие', 'для развития', 'обучающая', 'обучающие',
            'развивающая игра', 'развивающие игры', 'обучающая игра', 'обучающие игры'
        ]
        
        # Проверяем на наличие исключаемых ключевых слов
        for keyword in excluded_keywords:
            if keyword in text_to_check:
                return True
        
        return False
    
    async def get_book_by_id(self, source_id: str) -> Optional[Book]:
        """
        Получение книги по ID (точное совпадение)
        
        Args:
            source_id: ID товара в магазине (например, '2558779')
            
        Returns:
            Объект Book или None
        """
        await self.log_operation("get_by_id", "info", f"Получение книги по ID: {source_id}")
        
        try:
            api_book = await self.api_client.get_product_by_id(source_id)
            
            if api_book:
                book = self._api_book_to_book(api_book)
                await self.log_operation("get_by_id", "success", f"Найдена книга: {book.title}")
                return book
            else:
                await self.log_operation("get_by_id", "warning", f"Книга с ID {source_id} не найдена")
                return None
                
        except Exception as e:
            await self.log_operation("get_by_id", "error", f"Ошибка получения книги по ID: {e}")
            return None
    
    def get_stats(self) -> dict:
        """
        Получение статистики работы парсера
        
        Returns:
            Словарь со статистикой
        """
        return self.api_client.get_stats()
