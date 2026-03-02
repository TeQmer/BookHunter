# parsers/wildberries.py
from typing import List, Optional, Dict
from parsers.base import BaseParser, Book
from services.logger import parser_logger
import aiohttp
import asyncio
import re
import time


class WildberriesParser(BaseParser):
    """Парсер для Wildberries (wb.ru) с использованием cookies"""
    
    def __init__(self):
        # Задержки для WB - больше чем для Chitai-Gorod из-за защиты
        super().__init__("wildberries", delay_min=1.5, delay_max=3.0)
        self.base_url = "https://www.wildberries.ru"
        self.api_url = "https://search.wb.ru"
        
        # Флаг для отслеживания обновления cookies
        self._cookies_update_triggered = False
    
    def _get_headers(self, include_token: bool = False) -> Dict[str, str]:
        """
        Получение заголовков запроса с реалистичным User-Agent
        
        Args:
            include_token: Добавлять ли x-wbaas-token в заголовки
        """
        headers = {
            "accept": "*/*",
            "accept-language": "ru,en;q=0.9",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 YaBrowser/25.12.0.0 Yowser/2.5",
            "sec-ch-ua": '"Chromium";v="142", "YaBrowser";v="25.12", "Not_A Brand";v="99", "Yowser";v="2.5"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "origin": "https://www.wildberries.ru",
            "referer": "https://www.wildberries.ru/",
        }
        
        # Добавляем x-wbaas-token если запрошено
        if include_token:
            try:
                from services.token_manager import get_token_manager
                token_manager = get_token_manager()
                
                # Сначала пробуем получить из cookies
                wb_cookies = token_manager.get_wildberries_cookies()
                if wb_cookies and 'x_wbaas_token' in wb_cookies:
                    headers["x-wbaas-token"] = wb_cookies['x_wbaas_token']
                    parser_logger.info("[Wildberries] Используем x-wbaas-token из cookies")
                else:
                    # Fallback на env
                    token = token_manager.get_wildberries_token_fallback()
                    if token:
                        headers["x-wbaas-token"] = token
                        parser_logger.info("[Wildberries] Используем x-wbaas-token из .env (fallback)")
                    else:
                        parser_logger.warning("[Wildberries] Токен не найден ни в cookies, ни в .env!")
            except Exception as e:
                parser_logger.warning(f"[Wildberries] Не удалось получить token: {e}")
        
        return headers
    
    def _get_cookies(self) -> Optional[Dict[str, str]]:
        """Получение cookies из Redis"""
        try:
            from services.token_manager import get_token_manager
            token_manager = get_token_manager()
            return token_manager.get_wildberries_cookies()
        except Exception as e:
            parser_logger.warning(f"[Wildberries] Не удалось получить cookies: {e}")
            return None
    
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
        
        try:
            # Получаем cookies
            cookies = self._get_cookies()
            if cookies:
                parser_logger.info(f"[Wildberries] Используем cookies: {len(cookies)} шт")
            else:
                parser_logger.warning("[Wildberries] Cookies не найдены!")
            
            for page in range(1, max_pages + 1):
                # WB использует API каталога
                search_url = f"{self.api_url}/exactmatch/ru/common/v18/search"
                params = {
                    "appType": 1,
                    "curr": "rub",
                    "dest": "-1257786",  # Москва (можно сделать настраиваемым)
                    "lang": "ru",
                    "page": page,
                    "query": query,
                    "resultset": "catalog",
                    "sort": "popular",
                    "spp": 30
                }
        
                # Получаем заголовки с token
                headers = self._get_headers(include_token=True)
                
                await self._random_delay()
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        search_url, 
                        params=params, 
                        headers=headers,
                        cookies=cookies
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            products = data.get("data", {}).get("products", [])
                            
                            for product in products:
                                book = self._parse_product(product, query)
                                if book:
                                    books.append(book)
                            
                            parser_logger.info(f"[Wildberries] Страница {page}: найдено {len(products)} товаров")
                            
                        elif response.status == 401:
                            parser_logger.warning("[Wildberries] Ошибка авторизации (401)")
                            await self._handle_cookies_expired()
                            break
                            
                        elif response.status == 429:
                            parser_logger.warning("[Wildberries] Rate limit (429), увеличиваем задержку...")
                            await asyncio.sleep(30)  # Большая задержка при 429
                            # Пробуем еще раз без continue, выходим после повторной попытки
                            retry_count = getattr(self, '_retry_count', 0)
                            if retry_count >= 1:
                                parser_logger.error("[Wildberries] Превышен лимит повторов после 429")
                                break
                            self._retry_count = retry_count + 1
                            parser_logger.info(f"[Wildberries] Повторная попытка {self._retry_count}/1")
                            continue
                        
                        else:
                            parser_logger.error(f"[Wildberries] HTTP {response.status}")
                
                # Если достигли лимита
                if limit and len(books) >= limit:
                    books = books[:limit]
                    break
            
            search_time = time.time() - search_start
            await self.log_operation(
                "search", 
                "success", 
                f"Найдено книг: {len(books)}", 
                len(books)
            )
            parser_logger.info(f"⏱️ Поиск занял: {search_time:.2f} сек")
            
        except Exception as e:
            await self.log_operation("search", "error", f"Ошибка поиска: {e}")
            
        return books
    
    async def _handle_cookies_expired(self):
        """Обработка истекших cookies - триггер обновления"""
        if not self._cookies_update_triggered:
            try:
                from services.token_manager import get_token_manager
                token_manager = get_token_manager()
                token_manager.trigger_wildberries_cookies_update()
                self._cookies_update_triggered = True
                parser_logger.info("[Wildberries] Триггер обновления cookies отправлен")
            except Exception as e:
                parser_logger.error(f"[Wildberries] Ошибка триггера: {e}")
    
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
            detail_url = f"{self.api_url}/exactmatch/ru/common/v18/product/{product_id}"
            
            cookies = self._get_cookies()
            headers = self._get_headers(include_token=True)
            
            await self._random_delay()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    detail_url, 
                    headers=headers,
                    cookies=cookies
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
            discount_url = f"{self.api_url}/exactmatch/ru/common/v18/search"
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
            
            cookies = self._get_cookies()
            headers = self._get_headers(include_token=True)
            
            await self._random_delay()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    discount_url, 
                    params=params,
                    headers=headers,
                    cookies=cookies
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
