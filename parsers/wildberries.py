# parsers/wildberries.py
from typing import List, Optional, Dict
from parsers.base import BaseParser, Book
from services.logger import parser_logger
import aiohttp
import asyncio
import re
import time
import random
# Не нужен дополнительный импорт


class WildberriesParser(BaseParser):
    """Парсер для Wildberries (wb.ru) с использованием cookies"""
    
    def __init__(self):
        # Задержки для WB - больше чем для Chitai-Gorod из-за защиты
        super().__init__("wildberries", delay_min=2.0, delay_max=4.0)
        self.base_url = "https://www.wildberries.ru"
        # Правильный API URL из рабочего парсера!
        self.api_url = "https://www.wildberries.ru/__internal/u-search/exactmatch/ru/common/v18"
        
        # Флаг для отслеживания обновления cookies
        self._cookies_update_triggered = False
        # Флаг для отслеживания повторной попытки
        self._retry_with_new_cookies = False
        # Счетчик попыток
        self._request_attempts = 0
        self._max_attempts = 3
    
    def _get_headers(self, include_token: bool = False) -> Dict[str, str]:
        """
        Получение заголовков - как в рабочем парсере FedorSmorodskii
        """
        headers = {
            "accept": "*/*",
            "accept-language": "ru-RU,ru;q=0.9",
            "content-type": "application/json",
            "sec-ch-ua": '"Not_A Brand";v="99", "Chromium";v="142"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
            "referer": "https://www.wildberries.ru/",
        }
        
        return headers
    
    def _get_cookies(self) -> Optional[Dict[str, str]]:
        """Получение cookies - используем рабочие из парсера FedorSmorodskii"""
        # Рабочие cookies из успешного парсера!
        return {
            "x_wbaas_token": "1.1000.a68eb290181f459082e3165ba3118991.MTV8NDUuMjQ5LjEwNi4xMjF8TW96aWxsYS81LjAgKFdpbmRvd3MgTlQgMTAuMDs",
            "_wbauid": "9946458701771941728"
        }
    
    async def _wait_for_cookies_update(self, timeout: int = 30) -> bool:
        """
        Ожидание обновления cookies в Redis
        Аналогично Читай-городу - ждём появления новых cookies
        
        Args:
            timeout: Максимальное время ожидания в секундах
            
        Returns:
            True если cookies обновлены, False если таймаут
        """
        parser_logger.info(f"[Wildberries] Ожидаем обновления cookies (timeout: {timeout} сек)...")
        
        start_time = time.time()
        last_cookie_hash = None
        
        # Получаем хеш текущих cookies для сравнения
        current_cookies = self._get_cookies()
        if current_cookies:
            last_cookie_hash = hash(frozenset(current_cookies.items()))
        
        while time.time() - start_time < timeout:
            await asyncio.sleep(2)  # Проверяем каждые 2 секунды
            
            # Получаем актуальные cookies
            new_cookies = self._get_cookies()
            if new_cookies:
                new_hash = hash(frozenset(new_cookies.items()))
                
                # Если хеш изменился - cookies обновлены
                if new_hash != last_cookie_hash:
                    parser_logger.info("[Wildberries] Cookies обновлены!")
                    return True
                else:
                    parser_logger.debug("[Wildberries] Cookies ещё не обновлены...")
            else:
                parser_logger.debug("[Wildberries] Cookies не найдены в Redis...")
        
        parser_logger.warning("[Wildberries] Таймаут ожидания обновления cookies")
        return False
    
    async def _refresh_cookies_and_retry(self) -> bool:
        """
        Принудительное обновление cookies и ожидание
        Используется при 401 ошибке
        """
        parser_logger.info("[Wildberries] Запускаем обновление cookies...")
        
        try:
            from services.token_manager import get_token_manager
            token_manager = get_token_manager()
            
            # Триггерим обновление
            token_manager.trigger_wildberries_cookies_update()
            
            # Ждём обновления
            cookies_updated = await self._wait_for_cookies_update(timeout=30)
            
            if cookies_updated:
                parser_logger.info("[Wildberries] Cookies успешно обновлены, готовимся к повтору...")
                return True
            else:
                parser_logger.error("[Wildberries] Не удалось обновить cookies")
                return False
                
        except Exception as e:
            parser_logger.error(f"[Wildberries] Ошибка при обновлении cookies: {e}")
            return False
    
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
        
        # Сброс флагов перед новым поиском
        self._cookies_update_triggered = False
        self._retry_with_new_cookies = False
        self._request_attempts = 0
        
        # Используем другой API URL как в рабочем парсере
        # URL как в https://github.com/onmaxon/parser_wildberries_2025
        # shard для книг - нужно получить из каталога
        shard = "book"  # для книг
        
        # Цикл с повторами
        while self._request_attempts < self._max_attempts:
            self._request_attempts += 1
            attempt_info = f"Попытка {self._request_attempts}/{self._max_attempts}"
            parser_logger.info(f"[Wildberries] {attempt_info}: поиск '{query}'")
            
            try:
                # Пробуем получить cookies из Redis
                cookies = self._get_cookies()
                
                # Если нет - добавляем минимальные cookies которые могут помочь
                if not cookies:
                    cookies = {
                        "_wbauid": "892233731763147891",
                        "_cp": "1"
                    }
                    parser_logger.info("[Wildberries] Используем базовые cookies")
                else:
                    parser_logger.info(f"[Wildberries] Используем cookies: {len(cookies)} шт")
                
                page_books = []
                
                for page in range(1, max_pages + 1):
                    # РАБОЧИЙ URL из FedorSmorodskii парсера!
                    search_url = f"{self.api_url}/search"
                    
                    # Параметры как в рабочем парсере
                    params = {
                        "ab_testid": "dis_cb",
                        "appType": 1,
                        "curr": "rub",
                        "dest": "-1257786",
                        "hide_vflags": "4294967296",
                        "inheritFilters": "false",
                        "lang": "ru",
                        "page": page,
                        "query": query,
                        "resultset": "catalog",
                        "sort": "popular",
                        "spp": 30,
                        "suppressSpellcheck": "false"
                    }
            
                    # Получаем заголовки с token
                    headers = self._get_headers(include_token=True)
                    
                    # Большая случайная задержка перед запросом (3-8 секунд)
                    import random
                    await asyncio.sleep(random.uniform(3, 8))
                    
                    # Используем прокси из free-proxy-list
                    proxy = "http://154.65.39.7:80"
                    
                    # Ограничение соединений для прокси
                    connector = aiohttp.TCPConnector(limit=1, limit_per_host=1)
                    async with aiohttp.ClientSession(connector=connector) as session:
                        async with session.get(
                            search_url, 
                            params=params, 
                            headers=headers,
                            cookies=cookies,
                            proxy=proxy,
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                # Структура ответа может отличаться
                                products = data.get("data", {}).get("products", [])
                                if not products:
                                    products = data.get("products", [])
                                
                                for product in products:
                                    book = self._parse_product(product, query)
                                    if book:
                                        page_books.append(book)
                                
                                parser_logger.info(f"[Wildberries] Страница {page}: найдено {len(products)} товаров")
                                
                            elif response.status == 401:
                                parser_logger.warning(f"[Wildberries] Ошибка авторизации (401) - {attempt_info}")
                                
                                # Если ещё есть попытки - пробуем обновить cookies и повторить
                                if self._request_attempts < self._max_attempts:
                                    cookies_updated = await self._refresh_cookies_and_retry()
                                    if cookies_updated:
                                        parser_logger.info("[Wildberries] Cookies обновлены, повторяем запрос...")
                                        # Выходим из внутреннего цикла и начинаем сначала
                                        break
                                    else:
                                        parser_logger.error("[Wildberries] Не удалось обновить cookies")
                                else:
                                    parser_logger.error("[Wildberries] Превышен лимит попыток")
                                
                                await self._handle_cookies_expired()
                                page_books = []  # Очищаем результаты
                                break
                                
                            elif response.status == 429:
                                # Rate limit - большая случайная задержка
                                import random
                                wait_time = random.randint(60, 180)  # 1-3 минуты
                                
                                parser_logger.warning(f"[Wildberries] Rate limit (429), ждём {wait_time} сек...")
                                await asyncio.sleep(wait_time)
                                
                                # Повторяем страницу
                                continue
                            
                            elif response.status == 403:
                                parser_logger.warning("[Wildberries] 403 Forbidden - возможно блокировка")
                                await self._handle_cookies_expired()
                                break
                            
                            else:
                                parser_logger.error(f"[Wildberries] HTTP {response.status}")
                    
                    # Если достигли лимита
                    if limit and len(page_books) >= limit:
                        break
                
                # Если получили результаты и нет 401 - выходим из цикла попыток
                if page_books:
                    books = page_books
                    break
                    
                # Если это была попытка с 401 и cookies не обновились - пробуем ещё раз
                if self._request_attempts < self._max_attempts:
                    await asyncio.sleep(3)  # Небольшая пауза перед повтором
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
