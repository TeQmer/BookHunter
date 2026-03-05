# parsers/wildberries.py
from typing import List, Optional, Dict
from parsers.base import BaseParser, Book
from services.logger import parser_logger
import aiohttp
import asyncio
import re
import time
import random


class WildberriesParser(BaseParser):
    """Парсер для Wildberries (wb.ru)"""
    
    def __init__(self):
        # Задержки для WB - побольше чем для Chitai-Gorod
        super().__init__("wildberries", delay_min=2.0, delay_max=5.0)
        self.base_url = "https://www.wildberries.ru"
        
        # Рабочий API
        self.api_url = "https://search.wb.ru/exactmatch/ru/common/v4"
        
        # Мобильный прокси
        self.proxy = "http://yMKAw7:yr3yt8aryC7G@fproxy.site:14388"
        
        # Счетчик попыток
        self._request_attempts = 0
        self._max_attempts = 3
    
    def _get_headers(self) -> Dict[str, str]:
        """Получение заголовков запроса"""
        headers = {
            "accept": "application/json",
            "accept-language": "ru-RU,ru;q=0.9,en;q=0.8",
            "accept-encoding": "gzip, deflate, br",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "referer": "https://www.wildberries.ru/catalog/0/search.aspx?search=гарри+поттер",
            "origin": "https://www.wildberries.ru",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
        }
        return headers
    
    async def search_books(
        self,
        query: str,
        max_pages: int = 1,
        limit: int = None,
        fetch_details: bool = False
    ) -> List[Book]:
        """
        Поиск книг на Wildberries
        
        Args:
            query: Поисковый запрос (название или автор)
            max_pages: Максимальное количество страниц
            limit: Максимальное количество книг
            fetch_details: Загружать детальную информацию
            
        Returns:
            Список найденных книг
        """
        await self.log_operation("search", "info", f"Поиск книг по запросу: {query}")
        
        search_start = time.time()
        books = []
        
        self._request_attempts = 0
        
        # Цикл с повторами
        while self._request_attempts < self._max_attempts:
            self._request_attempts += 1
            attempt_info = f"Попытка {self._request_attempts}/{self._max_attempts}"
            parser_logger.info(f"[Wildberries] {attempt_info}: поиск '{query}'")
            
            try:
                page_books = []
                
                for page in range(1, max_pages + 1):
                    # Рабочий API v4
                    search_url = f"{self.api_url}/search"
                    
                    # Параметры
                    params = {
                        "appType": 1,
                        "curr": "rub",
                        "dest": "-1257786",
                        "lang": "ru",
                        "page": page,
                        "query": query,
                        "resultset": "catalog",
                        "sort": "popular",
                        "spp": 30
                    }
            
                    headers = self._get_headers()
                    
                    # Задержка перед запросом
                    await asyncio.sleep(random.uniform(1, 2))
                    
                    # С прокси
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            search_url, 
                            params=params, 
                            headers=headers,
                            proxy=self.proxy
                        ) as response:
                            parser_logger.info(f"[Wildberries] HTTP status: {response.status}")
                            
                            if response.status == 200:
                                data = await response.json()
                                
                                # Пробуем разные пути к продуктам
                                products = data.get("data", {}).get("products", [])
                                if not products:
                                    products = data.get("search_result", {}).get("products", [])
                                if not products:
                                    parser_logger.warning(f"[Wildberries] Пустой ответ на странице {page}")
                                
                                parser_logger.info(f"[Wildberries] Страница {page}: найдено {len(products)} товаров")
                                
                                for product in products:
                                    book = self._parse_product(product, query)
                                    if book:
                                        page_books.append(book)
                                
                            elif response.status == 429:
                                # Rate limit - большая задержка
                                wait_time = random.randint(60, 120)
                                parser_logger.warning(f"[Wildberries] Rate limit (429), ждём {wait_time} сек...")
                                await asyncio.sleep(wait_time)
                                continue
                            
                            elif response.status == 403:
                                parser_logger.warning("[Wildberries] 403 Forbidden")
                                break
                            
                            else:
                                parser_logger.error(f"[Wildberries] HTTP {response.status}")
                    
                    # Если достигли лимита
                    if limit and len(page_books) >= limit:
                        break
                
                # Если получили результаты - выходим
                if page_books:
                    books = page_books
                    break
                    
                # Иначе пробуем ещё раз
                if self._request_attempts < self._max_attempts:
                    await asyncio.sleep(3)
                    continue
                else:
                    break
                    
            except Exception as e:
                parser_logger.error(f"[Wildberries] Ошибка поиска: {e}")
                await self.log_operation("search", "error", f"Ошибка поиска: {e}")
                break
        
        # Применяем лимит
        if limit and len(books) > limit:
            books = books[:limit]
        
        search_time = time.time() - search_start
        await self.log_operation(
            "search", 
            "success", 
            f"Найдено книг: {len(books)}", 
            len(books)
        )
        parser_logger.info(f"⏱️ Поиск занял: {search_time:.2f} сек")
        
        return books
    
    def _parse_product(self, product: dict, query: str) -> Optional[Book]:
        """Преобразование данных продукта в модель Book"""
        try:
            # ID книги в WB
            source_id = str(product.get("id", ""))
            
            # Название
            title = product.get("name", "")
            if not title:
                return None
                
            # Цены - WB хранит в копейках в поле priceU
            price_u = product.get("priceU", 0)
            current_price = price_u / 100 if price_u else 0
            
            # Цена без скидки
            old_price_u = product.get("oldPrice", 0)
            original_price = old_price_u / 100 if old_price_u else current_price
            
            # Вычисляем скидку
            discount_percent = None
            if original_price and current_price and original_price > current_price:
                discount_percent = int(((original_price - current_price) / original_price) * 100)
            
            # URL книги
            product_url = f"{self.base_url}/catalog/{source_id}/detail.aspx"
            
            # Изображение
            image_url = None
            images = product.get("images", [])
            if images:
                img_path = images[0].get("path", "")
                if img_path:
                    image_url = f"https:{img_path}"
            
            # Бренд (часто = автор для книг)
            author = product.get("brand", "")
            
            # Создаем объект книги
            book = Book(
                source="wildberries",
                source_id=source_id,
                title=title,
                author=author if author else None,
                publisher=None,
                binding=None,
                current_price=current_price,
                original_price=original_price if original_price != current_price else None,
                discount_percent=discount_percent,
                url=product_url,
                image_url=image_url,
                genres=None,
                isbn=None
            )
            
            return book
            
        except Exception as e:
            parser_logger.error(f"[Wildberries] Ошибка парсинга продукта: {e}")
            return None
    
    async def get_book_details(self, url: str) -> Optional[Book]:
        """
        Получение детальной информации о книге
        
        Args:
            url: Ссылка на книгу
            
        Returns:
            Объект Book с детальной информацией
        """
        await self.log_operation("details", "info", f"Получение деталей: {url}")
        
        try:
            match = re.search(r'/catalog/(\d+)', url)
            if not match:
                return None
                
            product_id = match.group(1)
            
            # API детальной информации
            detail_url = f"{self.api_url}/product/{product_id}"
            
            headers = self._get_headers()
            
            await self._random_delay()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    detail_url, 
                    headers=headers,
                    proxy=self.proxy
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_product(data, "")
                        
        except Exception as e:
            parser_logger.error(f"[Wildberries] Ошибка получения деталей: {e}")
            
        return None
    
    async def check_discounts(self) -> List[Book]:
        """
        Сканирование акционных книг на WB
        
        Returns:
            Список книг со скидками
        """
        await self.log_operation("discounts", "info", "Сканирование акционных книг")
        
        books = []
        
        try:
            # Используем API v4
            discount_url = f"{self.api_url}/search"
            params = {
                "appType": 1,
                "curr": "rub",
                "dest": "-1257786",
                "lang": "ru",
                "page": 1,
                "query": "книги",
                "resultset": "catalog",
                "sort": "popular",
                "spp": 30
            }
            
            headers = self._get_headers()
            
            await self._random_delay()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    discount_url, 
                    params=params,
                    headers=headers,
                    proxy=self.proxy
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        products = data.get("data", {}).get("products", [])
                        
                        for product in products:
                            book = self._parse_product(product, "")
                            if book and book.discount_percent and book.discount_percent >= 15:
                                books.append(book)
            
            # Удаляем дубликаты
            unique_books = []
            seen_ids = set()
            for book in books:
                if book.source_id not in seen_ids:
                    unique_books.append(book)
                    seen_ids.add(book.source_id)
            
            unique_books.sort(key=lambda x: x.discount_percent or 0, reverse=True)
            
            await self.log_operation(
                "discounts",
                "success",
                f"Найдено акционных книг: {len(unique_books)}",
                len(unique_books)
            )
            
            return unique_books
            
        except Exception as e:
            await self.log_operation("discounts", "error", f"Ошибка сканирования: {e}")
            
        return []
