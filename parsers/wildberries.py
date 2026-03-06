# parsers/wildberries.py
from typing import List, Optional, Dict
from parsers.base import BaseParser, Book
from services.logger import parser_logger
import aiohttp
import asyncio
import re
import time
import random
import requests


class WildberriesParser(BaseParser):
    """Парсер для Wildberries (wb.ru)"""
    
    def __init__(self):
        # Задержки для WB - побольше чем для Chitai-Gorod
        super().__init__("wildberries", delay_min=2.0, delay_max=5.0)
        self.base_url = "https://www.wildberries.ru"
        
        # Мобильный API (работает в антидетекте!)
        self.mobile_api = "https://m.wildberries.ru"
        
        # Мобильный API endpoints
        self.mobile_search_url = "https://m.wildberries.ru/api/v1/search"
        
        # Пул мобильных прокси
        self.proxies = [
            "http://ykUV2B:SAaAg6Ah4Eb8@mproxy.site:13602",
            "http://yMKAw7:yr3yt8aryC7G@fproxy.site:14388",
        ]
        self._current_proxy_index = 0
        
        # Счетчик попыток
        self._request_attempts = 0
        self._max_attempts = 3
        
        # Использовать прокси или нет
        self._use_proxy = True
    
    @property
    def proxy(self) -> str:
        return self.proxies[self._current_proxy_index]
    
    def _rotate_proxy(self):
        """Ротирует прокси при бане"""
        self._current_proxy_index = (self._current_proxy_index + 1) % len(self.proxies)
        parser_logger.info(f"[Wildberries] Сменили прокси на: {self.proxy}")
        
        # Счетчик попыток
        self._request_attempts = 0
        self._max_attempts = 3
        
        # Shard для разных категории
        self._shards = [
            "kniggy/catalog",   # популярный для книг
            "books/catalog",    
            "book/catalog", 
            "ebook/catalog",    # электронные книги
            "product/catalog",    # общий
        ]
        self._current_shard = 0
    
        # Попробуем сначала без прокси
        self._use_proxy = True
    
        # Попробуем найти правильный shard
        self._init_shard()
    
    def _get_headers(self) -> Dict[str, str]:
        """Простой заголовок как в рабочем парсере"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0)"
        }
        return headers
    
    def _find_book_shard(self, catalog, depth=0):
        """Рекурсивный поиск shard для книг"""
        if depth > 3:  # ограничиваем глубину
            return None
    
        if isinstance(catalog, list):
            for item in catalog:
                result = self._find_book_shard(item, depth)
                if result:
                    return result
        elif isinstance(catalog, dict):
            name = catalog.get('name', '').lower()
            # Ищем "Книги" или "Электронные книги"
            if 'книг' in name and 'подарочн' not in name:
                shard = catalog.get('shard')
                if shard:
                    return shard
            # Ищем в дочерних
            if 'childs' in catalog:
                return self._find_book_shard(catalog['childs'], depth + 1)
        return None
    
    def _init_shard(self):
        """Получение правильного shard для книг из каталога WB"""
        try:
            url = 'https://static-basket-01.wbbasket.ru/vol0/data/main-menu-ru-ru-v3.json'
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0)"}
            
            proxies = None
            if self._use_proxy:
                proxies = {"http": self.proxy, "https": self.proxy}
            
            r = requests.get(url, headers=headers, proxies=proxies, timeout=10)
            if r.status_code == 200:
                catalog = r.json()
                # Ищем раздел "Книги" рекурсивно
                shard = self._find_book_shard(catalog)
                if shard:
                    self._shards.insert(0, shard)
                    parser_logger.info(f"[Wildberries] Найден shard для книг: {shard}")
                else:
                    parser_logger.warning(f"[Wildberries] Не найден shard для книг в каталоге")
        except Exception as e:
            parser_logger.warning(f"[Wildberries] Не удалось получить shard: {e}")
    
    def _get_catalog_url(self) -> str:
        """Формирование URL для поиска по книгам"""
        # Используем каталожный API как в рабочем примере
        return f"{self.catalog_url}/{self._shards[self._current_shard]}"
    
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
        # Используем оригинальный запрос
        search_query = query
        await self.log_operation("search", "info", f"Поиск книг по запросу: {query}")
        
        search_start = time.time()
        books = []
        
        self._request_attempts = 0
        self._current_shard = 0  # сбрасываем shard для каждого нового поиска
        
        # Цикл с повторами
        while self._request_attempts < self._max_attempts:
            self._request_attempts += 1
            attempt_info = f"Попытка {self._request_attempts}/{self._max_attempts}"
            parser_logger.info(f"[Wildberries] {attempt_info}: поиск '{query}'")
            
            try:
                page_books = []
                
                for page in range(1, max_pages + 1):
                    # Пробуем search.wb.ru/exactmatch - как в работающих парсерах
                    search_url = "https://search.wb.ru/exactmatch/ru/common/v4/search"
                    
                    # Параметры
                    params = {
                        "appType": 1,
                        "curr": "rub",
                        "dest": "-1257786",
                        "locale": "ru",
                        "page": page,
                        "query": search_query,
                        "resultset": "catalog",
                        "sort": "popular",
                        "spp": 30
                    }
            
                    headers = self._get_headers()
                    
                    # Задержка перед запросом
                    await asyncio.sleep(random.uniform(1, 2))
                    
                    # Используем requests
                    proxies = None
                    if self._use_proxy:
                        proxies = {"http": self.proxy, "https": self.proxy}
                    
                    try:
                        r = requests.get(
                            search_url, 
                            params=params, 
                            headers=headers,
                            proxies=proxies,
                            timeout=10
                        )
                        parser_logger.info(f"[Wildberries] HTTP status: {r.status_code}")
                        
                        if r.status_code == 200:
                            data = r.json()
                            
                            # Пробуем разные пути
                            products = data.get("data", {}).get("products", [])
                            if not products:
                                products = data.get("products", [])
                            
                            # ОТЛАДКА: посмотрим структуру первого продукта
                            if products and page == 1:
                                first_prod = products[0]
                                parser_logger.info(f"[Wildberries] Первый продукт ключи: {list(first_prod.keys())}")
                                # Пробуем найти изображения
                                if "images" in first_prod:
                                    parser_logger.info(f"[Wildberries] images: {first_prod['images']}")
                                if "media" in first_prod:
                                    parser_logger.info(f"[Wildberries] media: {first_prod['media']}")
                                if "image" in first_prod:
                                    parser_logger.info(f"[Wildberries] image: {first_prod['image']}")
                            
                            parser_logger.info(f"[Wildberries] Страница {page}: найдено {len(products)} товаров")
                            
                            for product in products:
                                # Фильтр - только книги
                                name = product.get("name", "").lower()
                                entity = product.get("entity", "").lower()
                                
                                # Исключаем канцелярию и не-товары
                                excluded_words = [
                                    "закладка", "канцеляр", "тетрад", "ручка", 
                                    "карандаш", "маркер", "стикер", "пенал",
                                    "набор канцеляр", "альбом для",
                                    "развивашка", "головоломк",  # это для детей, не книги
                                    "раскраск", "пропись", "азбука"
                                ]
                                is_excluded = any(word in name for word in excluded_words)
                                
                                # Проверяем что это книга
                                is_book = ("книг" in name or "книжк" in name or 
                                          "книга" in name or "книжечк" in name or
                                          entity == "книги" or "book" in name)
                                
                                if is_excluded or not is_book:
                                    continue
                                
                                book = self._parse_product(product, query)
                                if book:
                                    page_books.append(book)
                            
                        elif r.status_code == 429:
                            # Пробуем ротировать прокси
                            if self._use_proxy and len(self.proxies) > 1:
                                self._rotate_proxy()
                                parser_logger.warning(f"[Wildberries] 429, меняем прокси")
                                await asyncio.sleep(3)
                                continue
                            wait_time = random.randint(30, 60)
                            parser_logger.warning(f"[Wildberries] Rate limit (429), ждём {wait_time} сек...")
                            await asyncio.sleep(wait_time)
                            continue
                        
                        elif r.status_code == 403:
                            parser_logger.warning("[Wildberries] 403 Forbidden")
                            break
                        
                        elif r.status_code == 404:
                            # Ротируем прокси
                            if self._use_proxy and len(self.proxies) > 1:
                                self._rotate_proxy()
                                parser_logger.warning(f"[Wildberries] 404, меняем прокси")
                                continue
                            # Пробуем следующий shard
                            self._current_shard = (self._current_shard + 1) % len(self._shards)
                            parser_logger.warning(f"[Wildberries] 404, пробуем shard #{self._current_shard}")
                            if page == 1:  # только на первой странице
                                break
                        
                        else:
                            parser_logger.error(f"[Wildberries] HTTP {r.status_code}")
                            
                    except Exception as e:
                        # Проверяем, что ошибка связана с прокси
                        error_str = str(e).lower()
                        if "proxy" in error_str or "connection" in error_str:
                            if self._use_proxy and len(self.proxies) > 1:
                                self._rotate_proxy()
                                parser_logger.warning(f"[Wildberries] Ошибка прокси, меняем")
                                continue
                            # Все прокси не работают - пробуем без прокси
                            if self._use_proxy:
                                self._use_proxy = False
                                parser_logger.warning(f"[Wildberries] Прокси недоступны, пробуем без прокси")
                                continue
                        parser_logger.error(f"[Wildberries] Ошибка запроса: {e}")
                    
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
        
        # Дедупликация: оставляем только книги с минимальной ценой для каждого названия
        if books:
            unique_books = {}
            for book in books:
                # Нормализуем название - убираем лишнее
                normalized_title = book.title.lower().strip()
                
                if normalized_title not in unique_books:
                    unique_books[normalized_title] = book
                else:
                    # Если уже есть, оставляем с меньшей ценой
                    if book.current_price < unique_books[normalized_title].current_price:
                        unique_books[normalized_title] = book
            
            books = list(unique_books.values())
            # Сортируем по цене (по возрастанию)
            books.sort(key=lambda x: x.current_price)
        
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
                
            # Цены - структура изменилась
            # Цена в sizes[0].price.product (копейки)
            sizes = product.get("sizes", [])
            if sizes and len(sizes) > 0:
                price_data = sizes[0].get("price", {})
                current_price = price_data.get("product", 0) / 100 if price_data.get("product") else 0
                original_price = price_data.get("basic", 0) / 100 if price_data.get("basic") else current_price
            else:
                current_price = 0
                original_price = 0
            
            # Вычисляем скидку
            discount_percent = None
            if original_price and current_price and original_price > current_price:
                discount_percent = int(((original_price - current_price) / original_price) * 100)
            
            # URL книги
            product_url = f"{self.base_url}/catalog/{source_id}/detail.aspx"
            
            # Изображение - формируем URL по ID товара
            # Используем rst-basket-cdn-XX.geobasket.ru (рабочий формат)
            image_url = None
            if source_id:
                try:
                    id_str = str(source_id)
                    parser_logger.info(f"[Wildberries] Формирование image_url для source_id={id_str}")
                    
                    # Формула из StackOverflow:
                    # vol = nm / 100000, part = nm / 1000
                    # basket-N определяется по диапазону vol
                    nm_id = int(id_str)
                    vol = nm_id // 100000
                    part = nm_id // 1000
                    
                    # Определяем номер бакета по диапазону vol
                    if vol <= 143:
                        basket_num = "01"
                    elif vol <= 287:
                        basket_num = "02"
                    elif vol <= 431:
                        basket_num = "03"
                    elif vol <= 719:
                        basket_num = "04"
                    elif vol <= 1007:
                        basket_num = "05"
                    elif vol <= 1061:
                        basket_num = "06"
                    elif vol <= 1115:
                        basket_num = "07"
                    elif vol <= 1169:
                        basket_num = "08"
                    elif vol <= 1313:
                        basket_num = "09"
                    elif vol <= 1601:
                        basket_num = "10"
                    elif vol <= 1655:
                        basket_num = "11"
                    elif vol <= 1919:
                        basket_num = "12"
                    elif vol <= 2045:
                        basket_num = "13"
                    elif vol <= 2189:
                        basket_num = "14"
                    elif vol <= 2405:
                        basket_num = "15"
                    elif vol <= 2621:
                        basket_num = "16"
                    elif vol <= 2837:
                        basket_num = "17"
                    else:
                        basket_num = "18"
                    
                    image_url = f"https://basket-{basket_num}.wbbasket.ru/vol{vol}/part{part}/{id_str}/images/big/1.webp"
                    parser_logger.info(f"[Wildberries] Сформированный URL: {image_url}")
                    parser_logger.info(f"[Wildberries] Сформированный URL: {image_url}")
                except Exception as e:
                    parser_logger.warning(f"[Wildberries] Не удалось сформировать URL фото: {e}")
            
            # Также проверяем есть ли поле pics (количество изображений)
            pics_count = product.get("pics", 0)
            if pics_count > 0 and not image_url:
                # Если есть картинки, формируем URL по формуле
                id_str = str(source_id)
                nm_id = int(id_str)
                vol = nm_id // 100000
                part = nm_id // 1000
                
                # Определяем номер бакета
                if vol <= 143:
                    basket_num = "01"
                elif vol <= 287:
                    basket_num = "02"
                elif vol <= 431:
                    basket_num = "03"
                elif vol <= 719:
                    basket_num = "04"
                elif vol <= 1007:
                    basket_num = "05"
                elif vol <= 1061:
                    basket_num = "06"
                elif vol <= 1115:
                    basket_num = "07"
                elif vol <= 1169:
                    basket_num = "08"
                elif vol <= 1313:
                    basket_num = "09"
                elif vol <= 1601:
                    basket_num = "10"
                elif vol <= 1655:
                    basket_num = "11"
                elif vol <= 1919:
                    basket_num = "12"
                elif vol <= 2045:
                    basket_num = "13"
                elif vol <= 2189:
                    basket_num = "14"
                elif vol <= 2405:
                    basket_num = "15"
                elif vol <= 2621:
                    basket_num = "16"
                elif vol <= 2837:
                    basket_num = "17"
                else:
                    basket_num = "18"
                
                image_url = f"https://basket-{basket_num}.wbbasket.ru/vol{vol}/part{part}/{id_str}/images/big/1.webp"
            
            # Из extended_data получаем дополнительную инфу
            extended = product.get("extended", {})
            
            # Издательство (из supplier)
            publisher = None
            supplier = None
            if extended:
                supplier = extended.get("supplier", "")
                if not supplier:
                    # Пробуем из seller
                    seller = extended.get("seller", {})
                    if seller:
                        supplier = seller.get("name", "")
                        publisher = supplier
            
            # ФИЛЬТРАЦИЯ РЕСЕЙЛЕРОВ!
            # Если supplier не "Wildberries" и не пустой - это ресейлер, пропускаем
            if supplier and supplier != "Wildberries" and "wildberries" not in supplier.lower():
                parser_logger.info(f"[Wildberries] Пропускаем ресейлера: {supplier}")
                return None
                
            # Автор - для WB это сложно, часто автор не указан отдельно
            # Пробуем взять из названия (обычно формат "Название | Автор")
            author = None
            if "|" in title:
                parts = title.split("|")
                if len(parts) > 1:
                    potential_author = parts[-1].strip()
                    # Если не слишком длинное - скорее всего автор
                    if len(potential_author) < 50:
                        author = potential_author
            
            # Если не нашли автора в названии - оставляем None (не издательство!)
            if not author:
                # Для WB author часто = publisher/brand, лучше оставить пустым
                author = None
            
            # Жанры (категории) - пробуем разные источники
            genres = None
            
            # 1. Из categories
            if extended:
                categories = extended.get("categories", [])
                if categories:
                    cat_names = [c.get("name", "") for c in categories if c.get("name")]
                    if cat_names:
                        genres = ", ".join(cat_names)
            
            # 2. Если нет категорий - пробуем извлечь из названия
            if not genres:
                # Часто название содержит жанр: "Книга. Детектив" или "Роман. Фэнтези"
                title_lower = title.lower()
                genre_keywords = [
                    "детектив", "роман", "фэнтези", "фантастика", "приключения",
                    "история", "биография", "научная", "учебник", "самоучитель",
                    "поэзия", "проза", "сказка", "детск", "молодёжн",
                    "триллер", "ужасы", "комедия", "драма", "боевик",
                    "психолог", "философ", "эзотерик", "религи", "справочник"
                ]
                found_genres = [g for g in genre_keywords if g in title_lower]
                if found_genres:
                    genres = ", ".join(found_genres)
            
            # Рейтинг
            rating = extended.get("rating", 0) if extended else 0
            
            # Создаем объект книги
            book = Book(
                source="wildberries",
                source_id=source_id,
                title=title,
                author=author if author else None,
                publisher=publisher,
                binding=None,
                current_price=current_price,
                original_price=original_price if original_price != current_price else None,
                discount_percent=discount_percent,
                url=product_url,
                image_url=image_url,
                genres=genres,
                isbn=None
            )
            
            parser_logger.info(f"[Wildberries] Создана книга: {title[:30]}... image_url={image_url}")
            
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
            detail_url = f"https://search.wb.ru/exactmatch/ru/common/v4/product/{product_id}"
            
            headers = self._get_headers()
            
            await self._random_delay()
            
            # Используем requests
            proxies = None
            if self._use_proxy:
                proxies = {"http": self.proxy, "https": self.proxy}
            
            try:
                r = requests.get(
                    detail_url, 
                    headers=headers,
                    proxies=proxies,
                    timeout=10
                )
                if r.status_code == 200:
                    data = r.json()
                    return self._parse_product(data, "")
            except Exception as e:
                parser_logger.error(f"[Wildberries] Ошибка получения деталей: {e}")
                        
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
            # Используем search.wb.ru
            discount_url = "https://search.wb.ru/exactmatch/ru/common/v4/search"
            params = {
                "appType": 1,
                "curr": "rub",
                "dest": "-1257786",
                "locale": "ru",
                "page": 1,
                "query": "книги",
                "resultset": "catalog",
                "sort": "popular",
                "spp": 30
            }
            
            headers = self._get_headers()
            
            await self._random_delay()
            
            proxies = None
            if self._use_proxy:
                proxies = {"http": self.proxy, "https": self.proxy}
            
            try:
                r = requests.get(
                    discount_url, 
                    params=params,
                    headers=headers,
                    proxies=proxies,
                    timeout=10
                )
                if r.status_code == 200:
                    data = r.json()
                    products = data.get("data", {}).get("products", [])
                    
                    for product in products:
                        book = self._parse_product(product, "")
                        if book and book.discount_percent and book.discount_percent >= 15:
                            books.append(book)
            except Exception as e:
                parser_logger.error(f"[Wildberries] Ошибка сканирования: {e}")
            
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
