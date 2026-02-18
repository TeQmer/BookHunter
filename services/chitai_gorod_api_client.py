"""
API клиент для Читай-город с защитой от блокировок

Включает:
- Rate limiting (задержки между запросами)
- Retry mechanism (повторные попытки при ошибках)
- Реалистичные заголовки
- Логирование всех операций
"""

import os
import time
import random
import asyncio
import aiohttp
from typing import List, Dict, Optional
from datetime import datetime
import logging
from pydantic import BaseModel
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

logger = logging.getLogger(__name__)


class ChitaiGorodBook(BaseModel):
    """Модель книги из API Читай-города"""
    source_id: str
    title: str
    author: Optional[str] = None
    publisher: Optional[str] = None
    binding: Optional[str] = None
    current_price: float
    original_price: Optional[float] = None
    discount_percent: Optional[int] = None
    url: str
    image_url: Optional[str] = None
    genres: Optional[List[str]] = None
    quantity: Optional[int] = None
    status: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    parsed_at: datetime = None


class ChitaiGorodAPIClient:
    """API клиент для Читай-города с защитой от блокировок"""
    
    def __init__(
        self,
        api_url: str = None,
        bearer_token: str = None,
        user_id: str = None,
        city_id: int = 39,
        delay_min: float = 1.0,
        delay_max: float = 3.0,
        max_retries: int = 3,
        timeout: int = 30
    ):
        """
        Инициализация API клиента
        
        Args:
            api_url: URL API (по умолчанию из env)
            bearer_token: Bearer токен авторизации (по умолчанию из env или Redis)
            user_id: ID пользователя (по умолчанию из env)
            city_id: ID города (по умолчанию 39 - Москва)
            delay_min: Минимальная задержка между запросами (сек)
            delay_max: Максимальная задержка между запросами (сек)
            max_retries: Максимальное количество попыток при ошибке
            timeout: Таймаут запроса (сек)
        """
        self.api_url = api_url or os.getenv("CHITAI_GOROD_API_URL", "https://web-agr.chitai-gorod.ru/web/api/v2")

        # Токен: сначала переданный, затем из Redis/env через TokenManager
        if bearer_token:
            self.bearer_token = bearer_token
        else:
            # Пробуем получить токен через TokenManager
            try:
                from services.token_manager import get_token_manager
                token_manager = get_token_manager()
                self.bearer_token = token_manager.get_chitai_gorod_token_fallback()
            except Exception as e:
                logger.warning(f"[ChitaiGorodAPI] Не удалось использовать TokenManager: {e}")
                self.bearer_token = os.getenv("CHITAI_GOROD_BEARER_TOKEN")

        self.user_id = user_id or os.getenv("CHITAI_GOROD_USER_ID")
        self.city_id = city_id or int(os.getenv("CHITAI_GOROD_CITY_ID", "39"))

        # Настройки rate limiting
        self.delay_min = delay_min
        self.delay_max = delay_max

        # Настройки retry
        self.max_retries = max_retries
        self.timeout = timeout

        # Статистика
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.last_request_time = None

        # Флаг для отслеживания обновления токена
        self._token_update_triggered = False

        # Проверка конфигурации
        if not self.bearer_token:
            logger.warning("[ChitaiGorodAPI] Bearer token не задан! API может не работать.")
        if not self.user_id:
            logger.warning("[ChitaiGorodAPI] User ID не задан!")

        logger.info(f"[ChitaiGorodAPI] Инициализирован: {self.api_url}, city_id={self.city_id}")
    
    def _get_headers(self) -> Dict[str, str]:
        """Получение заголовков запроса"""
        return {
            "accept": "*/*",
            "accept-language": "ru,en;q=0.9",
            "authorization": self.bearer_token,
            "initial-feature": "index",
            "platform": "desktop",
            "shop-brand": "chitaiGorod",
            "user-id": self.user_id,
            "sec-ch-ua": '"Chromium";v="142", "YaBrowser";v="25.12", "Not_A Brand";v="99", "Yowser";v="2.5"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
        }
    
    async def _random_delay(self):
        """Случайная задержка между запросами"""
        delay = random.uniform(self.delay_min, self.delay_max)
        logger.debug(f"[ChitaiGorodAPI] Задержка: {delay:.2f} сек")
        await asyncio.sleep(delay)
    
    async def _make_request(
        self,
        url: str,
        params: Dict = None,
        method: str = "GET"
    ) -> Optional[Dict]:
        """
        Выполнение HTTP запроса с retry mechanism
        
        Args:
            url: URL для запроса
            params: Параметры запроса
            method: HTTP метод (GET/POST)
            
        Returns:
            JSON ответ или None при ошибке
        """
        headers = self._get_headers()
        
        for attempt in range(self.max_retries):
            try:
                # Rate limiting
                await self._random_delay()
                
                # Логируем запрос
                self.request_count += 1
                logger.info(f"[ChitaiGorodAPI] Запрос #{self.request_count}: {method} {url}")
                if params:
                    logger.debug(f"[ChitaiGorodAPI] Параметры: {params}")
                
                # Выполняем запрос
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as session:
                    async with session.request(
                        method,
                        url,
                        params={k: v for k, v in (params or {}).items() if v is not None},
                        headers=headers
                    ) as response:
                        self.last_request_time = datetime.now()
                        
                        # Обрабатываем ответ
                        if response.status == 200:
                            self.success_count += 1
                            data = await response.json()
                            logger.info(f"[ChitaiGorodAPI] Успех: {response.status}")
                            return data
                        
                        elif response.status == 401:
                            self.error_count += 1
                            logger.error(f"[ChitaiGorodAPI] Ошибка авторизации (401)! Токен недействителен.")

                            # Триггерим обновление токена (только один раз)
                            if not self._token_update_triggered:
                                logger.info("[ChitaiGorodAPI] Триггер обновления токена...")
                                await self._handle_token_expired()
                                self._token_update_triggered = True

                                # Ждем обновления токена (до 60 секунд)
                                await self._wait_for_token_update()

                                # Обновляем токен в текущем экземпляре
                                await self._refresh_token()

                                # Повторяем запрос с новым токеном
                                logger.info("[ChitaiGorodAPI] Повторяем запрос с новым токеном...")
                                headers = self._get_headers()  # Обновляем заголовки
                                continue  # Повторяем попытку

                            return None
                        
                        elif response.status == 429:
                            self.error_count += 1
                            retry_after = int(response.headers.get('Retry-After', 10))
                            logger.warning(
                                f"[ChitaiGorodAPI] Rate limit (429). "
                                f"Ждем {retry_after} сек перед попыткой {attempt + 1}/{self.max_retries}"
                            )
                            await asyncio.sleep(retry_after)
                            continue
                        
                        else:
                            self.error_count += 1
                            error_text = await response.text()
                            logger.error(
                                f"[ChitaiGorodAPI] HTTP {response.status}: {error_text[:200]}"
                            )
                            return None
                
            except asyncio.TimeoutError:
                self.error_count += 1
                logger.warning(
                    f"[ChitaiGorodAPI] Timeout (попытка {attempt + 1}/{self.max_retries})"
                )
                
                # Экспоненциальная задержка
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                
            except aiohttp.ClientError as e:
                self.error_count += 1
                logger.error(
                    f"[ChitaiGorodAPI] Ошибка соединения: {e} (попытка {attempt + 1}/{self.max_retries})"
                )
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                
            except Exception as e:
                self.error_count += 1
                logger.error(
                    f"[ChitaiGorodAPI] Неожиданная ошибка: {e} (попытка {attempt + 1}/{self.max_retries})"
                )
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
        
        logger.error(f"[ChitaiGorodAPI] Не удалось выполнить запрос после {self.max_retries} попыток")
        return None
    
    async def _handle_token_expired(self):
        """Обработка истекшего токена - триггер обновления"""
        try:
            from services.token_manager import get_token_manager
            token_manager = get_token_manager()
            token_manager.trigger_token_update()
        except Exception as e:
            logger.error(f"[ChitaiGorodAPI] Ошибка триггера обновления токена: {e}")

    async def _wait_for_token_update(self, max_wait: int = 60, check_interval: int = 2):
        """Ожидание обновления токена в Redis"""
        try:
            from services.token_manager import get_token_manager
            token_manager = get_token_manager()

            waited = 0
            while waited < max_wait:
                token = token_manager.get_chitai_gorod_token()
                if token and token != self.bearer_token:
                    logger.info(f"[ChitaiGorodAPI] Токен обновлен в Redis!")
                    return

                await asyncio.sleep(check_interval)
                waited += check_interval

            logger.warning(f"[ChitaiGorodAPI] Токен не обновлен за {max_wait} сек")

        except Exception as e:
            logger.error(f"[ChitaiGorodAPI] Ошибка ожидания обновления токена: {e}")

    async def _refresh_token(self):
        """Обновление токена в текущем экземпляре клиента"""
        try:
            from services.token_manager import get_token_manager
            token_manager = get_token_manager()

            new_token = token_manager.get_chitai_gorod_token_fallback()
            if new_token:
                self.bearer_token = new_token
                logger.info(f"[ChitaiGorodAPI] Токен обновлен: {new_token[:20]}...")
            else:
                logger.warning("[ChitaiGorodAPI] Не удалось получить новый токен")

        except Exception as e:
            logger.error(f"[ChitaiGorodAPI] Ошибка обновления токена: {e}")
    
    async def search_products(
        self,
        phrase: str,
        page: int = 1,
        per_page: int = 60
    ) -> List[ChitaiGorodBook]:
        """
        Поиск товаров (книг)
        
        Args:
            phrase: Поисковый запрос
            page: Номер страницы
            per_page: Количество товаров на странице
            
        Returns:
            Список найденных книг
        """
        url = f"{self.api_url}/search/product"
        params = {
            "customerCityId": self.city_id,
            "products[page]": page,
            "products[per-page]": per_page,
            "phrase": phrase
        }
        
        data = await self._make_request(url, params=params)
        
        if not data:
            logger.warning(f"[ChitaiGorodAPI] Не удалось получить результаты поиска для: {phrase}")
            return []
        
        # Парсим ответ в формате JSON API
        products = self._parse_search_response(data)
        
        logger.info(f"[ChitaiGorodAPI] Найдено {len(products)} товаров по запросу: {phrase}")
        return products
    
    def _parse_search_response(self, response: Dict) -> List[ChitaiGorodBook]:
        """
        Парсит ответ поиска в формате JSON API
        
        Args:
            response: Ответ от API
            
        Returns:
            Список товаров
        """
        # Получаем список товаров из included
        included = response.get('included', [])
        
        # Фильтруем только товары
        product_items = [item for item in included if item.get('type') == 'product']
        
        # Преобразуем в модель книги
        books = []
        for item in product_items:
            try:
                book = self._parse_product_item(item)
                if book:
                    books.append(book)
            except Exception as e:
                logger.warning(f"[ChitaiGorodAPI] Ошибка парсинга товара: {e}")
                continue
        
        return books
    
    def _parse_product_item(self, item: Dict) -> Optional[ChitaiGorodBook]:
        """
        Парсит элемент товара из API
        
        Args:
            item: Элемент товара из API
            
        Returns:
            Модель книги или None
        """
        try:
            attrs = item.get('attributes', {})
            
            # Получаем автора
            authors = attrs.get('authors', [])
            author_name = None
            if authors:
                author = authors[0]
                parts = [author.get('firstName', ''), author.get('lastName', '')]
                author_name = ' '.join(filter(None, parts)).strip()
            
            # Получаем цену
            price = float(attrs.get('price', 0))
            old_price = float(attrs.get('oldPrice', 0)) if attrs.get('oldPrice') else None
            discount = int(attrs.get('discount', 0)) if attrs.get('discount') else None
            
            # Получаем жанры
            genres = []
            category = attrs.get('category')
            if category:
                genres.append(category.get('title', ''))
            
            category_chain = attrs.get('categoryChain', [])
            if len(category_chain) > 1:
                genres.extend(category_chain[1:])
            
            # Убираем дубликаты
            genres = list(dict.fromkeys(genres))
            
            # Получаем рейтинг
            rating_data = attrs.get('rating', {})
            rating = float(rating_data.get('count', 0)) if rating_data.get('count') else None
            reviews = rating_data.get('reviews')
            
            # Формируем URL
            product_url = attrs.get('url', '')
            full_url = f"https://www.chitai-gorod.ru/{product_url}"
            
            # Формируем URL изображения
            image_url = None
            picture = attrs.get('picture')
            if picture and not picture.startswith('http'):
                image_url = f"https://content.img-gorod.ru{picture}"
            
            # Создаем модель книги
            book = ChitaiGorodBook(
                source_id=item.get('id', ''),
                title=attrs.get('title', ''),
                author=author_name,
                publisher=attrs.get('publisher', {}).get('title') if attrs.get('publisher') else None,
                binding=attrs.get('binding'),
                current_price=price,
                original_price=old_price,
                discount_percent=discount,
                url=full_url,
                image_url=image_url,
                genres=genres if genres else None,
                quantity=attrs.get('quantity'),
                status=attrs.get('status'),
                rating=rating,
                reviews=reviews,
                parsed_at=datetime.now()
            )
            
            return book
            
        except Exception as e:
            logger.warning(f"[ChitaiGorodAPI] Ошибка при создании модели книги: {e}")
            return None
    
    async def get_facets(self, phrase: str) -> Dict:
        """
        Получение фильтров и категорий для поиска
        
        Args:
            phrase: Поисковый запрос
            
        Returns:
            Словарь с фильтрами
        """
        url = f"{self.api_url}/search/facet-search"
        params = {
            "customerCityId": self.city_id,
            "phrase": phrase
        }
        
        data = await self._make_request(url, params=params)
        
        if data:
            logger.info(f"[ChitaiGorodAPI] Получены фильтры для: {phrase}")
        else:
            logger.warning(f"[ChitaiGorodAPI] Не удалось получить фильтры для: {phrase}")
        
        return data or {}
    
    def get_stats(self) -> Dict:
        """Получение статистики запросов"""
        return {
            "total_requests": self.request_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": f"{(self.success_count / self.request_count * 100):.1f}%" if self.request_count > 0 else "0%",
            "last_request": self.last_request_time
        }
    
    def __str__(self) -> str:
        return f"ChitaiGorodAPIClient(requests={self.request_count}, success={self.success_count}, errors={self.error_count})"
