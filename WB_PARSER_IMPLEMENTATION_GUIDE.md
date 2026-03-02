# Инструкция по созданию парсера WB (Wildberries)

## Содержание
1. [Анализ и логика работы](#анализ-и-логика-работы)
2. [Система cookies и токенов WB](#система-cookies-и-токенов-wb)
3. [Создание парсера Wildberries](#создание-парсера-wildberries)
4. [Обновление TokenManager для WB](#обновление-tokenmanager-для-wb)
5. [Обновление фабрики парсеров](#обновление-фабрики-парсеров)
6. [Обновление API](#обновление-api)
7. [Обновление Mini App](#обновление-mini-app)
8. [Обновление админки](#обновление-админки)
9. [Настройка Celery задачи](#настройка-celery-задачи)

---

## Анализ и логика работы

### Основные принципы
1. **Объединение результатов** — при поиске парсим все выбранные источники и объединяем результаты
2. **Без дедупликации** — даже если книга одинаковая на разных источниках, показываем её дважды (от каждого источника отдельно)
3. **Выбор источников** — пользователь выбирает: все источники или конкретные
4. **Хранение** — книги хранятся в базе с полем `source`, поэтому мы всегда знаем откуда книга

### Пример работы
```
Пользователь вводит "Майк Омер"
→ Если выбраны [Читай-город, WB]:
    → Парсим Читай-город → получаем 15 книг
    → Парсим WB → получаем 25 книг
    → Показываем ВСЕ 40 книг (без объединения)
    → Каждая книга показывает свой источник
    
→ Если выбран только [WB]:
    → Парсим только WB → получаем 25 книг
```

### Текущая архитектура (что есть сейчас)
- `parsers/base.py` — абстрактный класс BaseParser с моделью Book
- `parsers/chitai_gorod.py` — парсер Читай-города (использует API)
- `parsers/factory.py` — фабрика для создания парсеров
- `api/parser.py` — API эндпоинты для парсинга
- `services/celery_tasks.py` — Celery задачи для фонового парсинга

---

## Система cookies и токенов WB

### Зачем нужны cookies

WB, в отличие от открытых API, требует cookies для:
- **Идентификации сессии** — без cookies WB может показывать "левый трафик" (нерелевантные результаты)
- **Геолокации** — правильные цены и наличие для вашего региона
- **Антифрод-защиты** — снижает риск блокировки и 429 ошибок

### Получение x_wbaas_token

Токен `x_wbaas_token` можно получить из браузера без регистрации:

1. Откройте `https://www.wildberries.ru`
2. Откройте DevTools (F12) → вкладка Application → Cookies
3. Найдите cookie с именем `x_wbaas_token`
4. Скопируйте её значение

**Примечание:** Токен без регистрации работает, но:
- Может истекать быстрее (периодически обновляйте)
- Лимиты запросов жёстче, чем для авторизованных пользователей

### Структура cookies WB

```python
# Пример структуры cookies для WB
wb_cookies = {
    "x_wbaas_token": "1.1000.abc123...",  # Основной токен сессии
    # Другие cookies могут добавляться автоматически
}
```

### Механизм обновления cookies

Аналогично Читай-городу, используем:
1. **Redis** — хранение cookies с TTL
2. **Celery задача** — периодическое обновление
3. **Fallback** — если Redis пустой, используем из .env

---

## Создание парсера Wildberries

### Шаг 1: Создать файл `parsers/wildberries.py`

Создать новый файл `parsers/wildberries.py` по аналогии с `chitai_gorod.py`:

```python
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
                wb_cookies = token_manager.get_wildberries_cookies()
                if wb_cookies and 'x_wbaas_token' in wb_cookies:
                    headers["x-wbaas-token"] = wb_cookies['x_wbaas_token']
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
                            parser_logger.warning("[Wildberries] Rate limit (429)")
                            await asyncio.sleep(10)
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
```

### Шаг 2: Проверить модель Book в base.py

Убедиться, что все необходимые поля есть:

```python
class Book(BaseModel):
    source: str                    # "chitai-gorod" или "wildberries"
    source_id: str                 # ID в магазине
    title: str
    author: Optional[str]
    publisher: Optional[str]
    binding: Optional[str]
    current_price: float
    original_price: Optional[float]
    discount_percent: Optional[int]
    url: str
    image_url: Optional[str]
    genres: Optional[List[str]]
    isbn: Optional[str]
    parsed_at: datetime
```

---

## Обновление TokenManager для WB

### Шаг 2.1: Добавить методы для WB в `services/token_manager.py`

Добавить следующие методы в класс `TokenManager`:

```python
def get_wildberries_cookies(self) -> Optional[Dict[str, str]]:
    """
    Получение cookies Wildberries из Redis

    Returns:
        Словарь cookies или None
    """
    try:
        redis_client = self._get_redis_client()
        cookies_json = redis_client.get("wildberries_cookies")

        if cookies_json:
            import json
            cookies = json.loads(cookies_json)
            logger.info(f"WB Cookies получены из Redis: {len(cookies)} cookies")
            return cookies
        else:
            logger.warning("WB Cookies не найдены в Redis")
            return None

    except Exception as e:
        logger.error(f"Ошибка получения WB cookies: {e}")
        return None

def save_wildberries_cookies(self, cookies: Dict[str, str], ttl: int = 43200) -> bool:
    """
    Сохранение cookies Wildberries в Redis

    Args:
        cookies: Словарь cookies
        ttl: Время жизни в секундах (по умолчанию 12 часов)

    Returns:
        True при успехе, False при ошибке
    """
    try:
        redis_client = self._get_redis_client()
        import json
        cookies_json = json.dumps(cookies)
        redis_client.setex("wildberries_cookies", ttl, cookies_json)
        logger.info(f"WB Cookies сохранены в Redis (TTL: {ttl} сек)")
        return True

    except Exception as e:
        logger.error(f"Ошибка сохранения WB cookies: {e}")
        return False

def get_wildberries_token_fallback(self) -> Optional[str]:
    """
    Получение токена WB с fallback на env

    Returns:
        Токен или None
    """
    # Сначала пробуем из cookies
    cookies = self.get_wildberries_cookies()
    if cookies and 'x_wbaas_token' in cookies:
        return cookies['x_wbaas_token']
    
    # Fallback на env
    return os.getenv("WB_X_WBAAS_TOKEN")

def trigger_wildberries_cookies_update(self) -> bool:
    """
    Триггер Celery задачи для обновления cookies WB

    Returns:
        True при успехе, False при ошибке
    """
    try:
        from services.celery_app import celery_app
        result = celery_app.send_task(
            "services.celery_tasks.update_wildberries_cookies",
            countdown=5
        )
        logger.info(f"Задача обновления WB cookies отправлена: {result.id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка триггера обновления WB cookies: {e}")
        return False
```

### Шаг 2.2: Добавить переменные окружения

В `.env` добавить:

```env
# Wildberries
WB_X_WBAAS_TOKEN=1.1000.4f24e55cd04c43edadfb7da1d20e4ed3...
WB_COOKIES_TTL=43200
```

---

## Обновление фабрики парсеров

### Шаг 3: Обновить `parsers/factory.py`

Добавить импорт и регистрацию WB парсера:

```python
from typing import Dict, Type
from parsers.base import BaseParser
from services.logger import parser_logger

# Импортируем парсеры
try:
    from parsers.chitai_gorod import ChitaiGorodParser
    from parsers.wildberries import WildberriesParser
    PARSERS_AVAILABLE = True
except ImportError as e:
    parser_logger.warning(f"Не удалось загрузить парсеры: {e}")
    PARSERS_AVAILABLE = False
    ChitaiGorodParser = None
    WildberriesParser = None

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
        
        # Регистрируем парсер "Wildberries"
        if WildberriesParser:
            self._parsers["wildberries"] = WildberriesParser
            parser_logger.info("Парсер 'Wildberries' загружен")
    
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
```

---

## Обновление API

### Шаг 4: Обновить эндпоинт источников в `api/parser.py`

Найти функцию `get_available_sources` и обновить:

```python
@router.get("/sources")
async def get_available_sources():
    """Получение списка доступных источников для парсинга"""
    
    try:
        sources = {
            "chitai-gorod": "Читай-город",
            "wildberries": "Wildberries"
        }
        
        return {
            "sources": sources,
            "default_sources": ["chitai-gorod", "wildberries"]  # По умолчанию оба
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения источников: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения источников")
```

### Шаг 5: Обновить логику парсинга для нескольких источников

В `api/parser.py` нужно обновить функцию `parse_books_from_body` чтобы:
- По умолчанию использовались **оба** источника
- Поддерживался выбор одного источника

```python
@router.post("/parse-body")
async def parse_books_from_body(
    data: dict,
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db)
):
    """
    Запуск парсинга книг по запросу
    
    Параметры:
    - query: Поисковый запрос (обязательно)
    - sources: Список источников (по умолчанию ["chitai-gorod", "wildberries"])
    - fetch_details: Загружать детальную информацию
    - telegram_id: ID пользователя для проверки лимитов
    """
    
    try:
        query = data.get("query")
        
        # По умолчанию ОБА источника!
        sources_param = data.get("sources", ["chitai-gorod", "wildberries"])
        if isinstance(sources_param, str):
            sources = [sources_param]
        else:
            sources = sources_param
            
        fetch_details = data.get("fetch_details", False)
        telegram_id = data.get("telegram_id")
        
        if not query:
            raise HTTPException(status_code=400, detail="Поле 'query' обязательно")
        
        # Проверяем лимиты
        if telegram_id:
            can_parse, user, error_message = check_request_limit(sync_db, telegram_id)
            if not can_parse:
                # Ищем только в базе
                books_list, total = await search_books_in_db(query, db, sources)
                return {
                    "status": "limit_exceeded",
                    "message": error_message,
                    "query": query,
                    "sources": sources,
                    "books": books_list,
                    "total": total
                }
        
        # Ищем в базе (по выбранным источникам)
        books_list, total = await search_books_in_db(query, db, sources)
        
        # Запускаем парсинг для каждого источника
        tasks = []
        task_ids = []
        
        for source in sources:
            task = parse_books.delay(
                query=query, 
                source=source, 
                fetch_details=fetch_details,
                max_pages=1
            )
            tasks.append(task)
            task_ids.append({"source": source, "task_id": task.id})
            
        return {
            "task_ids": task_ids,
            "status": "started",
            "message": f"Парсинг запущен для источников: {', '.join(sources)}",
            "query": query,
            "sources": sources,
            "books": books_list,
            "total": total
        }
        
    except Exception as e:
        logger.error(f"Ошибка парсинга: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### Шаг 5.1: Добавить smart-search endpoint

Добавить новый endpoint для умного поиска (сначала база, потом парсинг):

```python
@router.get("/web/books/api/smart-search")
async def smart_search(
    q: str,
    sources: str = "chitai-gorod,wildberries",  # По умолчанию оба
    min_discount: int = None,
    max_price: int = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Умный поиск: сначала база, потом парсинг если нет результатов
    
    Параметры:
    - q: Поисковый запрос
    - sources: Список источников через запятую (по умолчанию оба)
    - min_discount: Минимальная скидка
    - max_price: Максимальная цена
    """
    
    # Парсим источники
    sources_list = [s.strip() for s in sources.split(',') if s.strip()]
    if not sources_list:
        sources_list = ["chitai-gorod", "wildberries"]
    
    logger.info(f"[smart-search] Запрос: {q}, источники: {sources_list}")
    
    # Ищем в базе
    books_list, total = await search_books_in_db(q, db, sources_list)
    
    # Применяем фильтры
    if min_discount:
        books_list = [b for b in books_list if (b.get('discount_percent') or 0) >= min_discount]
    if max_price:
        books_list = [b for b in books_list if (b.get('current_price') or float('inf')) <= max_price]
    
    logger.info(f"[smart-search] Найдено в базе: {len(books_list)}")
    
    return {
        "success": True,
        "books": books_list,
        "total": len(books_list),
        "sources": sources_list,
        "from_cache": total > 0
    }
```

### Шаг 5.2: Обновить search_books_in_db для фильтрации по источникам

```python
async def search_books_in_db(query: str, db: AsyncSession, sources: List[str] = None):
    """
    Поиск книг в базе данных
    
    Args:
        query: Поисковый запрос
        db: Сессия базы данных
        sources: Список источников для поиска (если None - все)
    
    Returns:
        Список книг и общее количество
    """
    
    try:
        # Базовый запрос
        stmt = select(Book).where(
            or_(
                Book.title.ilike(f"%{query}%"),
                Book.author.ilike(f"%{query}%")
            )
        )
        
        # Фильтр по источникам
        if sources:
            stmt = stmt.where(Book.source.in_(sources))
        
        stmt = stmt.order_by(Book.parsed_at.desc())
        
        result = await db.execute(stmt)
        books = result.scalars().all()
        
        # Преобразуем в dict
        books_list = []
        for book in books:
            books_list.append({
                "id": book.id,
                "source": book.source,
                "source_id": book.source_id,
                "title": book.title,
                "author": book.author,
                "publisher": book.publisher,
                "binding": book.binding,
                "current_price": book.current_price,
                "original_price": book.original_price,
                "discount_percent": book.discount_percent,
                "url": book.url,
                "image_url": book.image_url,
                "genres": book.genres,
                "isbn": book.isbn,
                "parsed_at": book.parsed_at.isoformat() if book.parsed_at else None
            })
        
        return books_list, len(books_list)
        
    except Exception as e:
        logger.error(f"Ошибка поиска в базе: {e}")
        return [], 0
```

```python
@router.post("/parse-body")
async def parse_books_from_body(
    data: dict,
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db)
):
    """
    Запуск парсинга книг по запросу
    
    Параметры:
    - query: Поисковый запрос (обязательно)
    - sources: Список источников (по умолчанию ["chitai-gorod"])
    - fetch_details: Загружать детальную информацию
    - telegram_id: ID пользователя для проверки лимитов
    """
    
    try:
        query = data.get("query")
        # Поддержка как строки, так и массива
        sources_param = data.get("sources", ["chitai-gorod"])
        if isinstance(sources_param, str):
            sources = [sources_param]
        else:
            sources = sources_param
            
        fetch_details = data.get("fetch_details", False)
        telegram_id = data.get("telegram_id")
        
        if not query:
            raise HTTPException(status_code=400, detail="Поле 'query' обязательно")
        
        # Проверяем лимиты
        if telegram_id:
            can_parse, user, error_message = check_request_limit(sync_db, telegram_id)
            if not can_parse:
                # Ищем только в базе
                books_list, total = await search_books_in_db(query, db)
                return {
                    "status": "limit_exceeded",
                    "message": error_message,
                    "query": query,
                    "sources": sources,
                    "books": books_list,
                    "total": total
                }
        
        # Ищем в базе (по всем источникам)
        books_list, total = await search_books_in_db(query, db)
        
        # Запускаем парсинг для каждого источника
        tasks = []
        task_ids = []
        
        for source in sources:
            # Проверяем лимиты для каждого источника
            should_parse = True  # Логика проверки
            
            if should_parse:
                task = parse_books.delay(
                    query=query, 
                    source=source, 
                    fetch_details=fetch_details,
                    max_pages=1
                )
                tasks.append(task)
                task_ids.append({"source": source, "task_id": task.id})
        
        return {
            "task_ids": task_ids,
            "status": "started",
            "message": f"Парсинг запущен для источников: {', '.join(sources)}",
            "query": query,
            "sources": sources,
            "books": books_list,
            "total": total
        }
        
    except Exception as e:
        logger.error(f"Ошибка парсинга: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Обновление Mini App

### Шаг 6: Обновить константы источников в `telegram/app/js/mini-app.js`

Добавить в начало файла (после объявления класса или в начало файла):

```javascript
// Источники для парсинга (добавить в начало файла)
const SOURCES = {
    'chitai-gorod': 'Читай-город',
    'wildberries': 'Wildberries'
};
```

### Шаг 7: Обновить фильтр источников в HTML

В `telegram/app/index.html` обновить селект источников:

```html
<div class="form-group">
    <label class="form-label">Источник</label>
    <select class="form-select" id="filter-source">
        <option value="">Все источники</option>
        <option value="chitai-gorod">Читай-город</option>
        <option value="wildberries">Wildberries</option>
    </select>
</div>
```

### Шаг 8: Добавить функции поиска в mini-app.js

Добавить в класс `BookHunterApp` две новые функции:

```javascript
/**
 * Обычный поиск (сначала база, потом парсинг)
 * По умолчанию ищет по всем источникам
 */
async searchBooks(query) {
    if (!query || !query.trim()) {
        this.showError('Введите запрос для поиска');
        return;
    }

    console.log('[searchBooks] Обычный поиск:', query);
    
    const container = document.getElementById('books-container');
    container.innerHTML = '<div class="loading"><div class="loading__spinner"></div><div class="loading__text">Поиск...</div></div>';
    
    // Получаем выбранный источник из фильтра
    const sourceSelect = document.getElementById('filter-source');
    const selectedSource = sourceSelect?.value;
    
    // По умолчанию оба источника, если не выбран конкретный
    const sources = selectedSource ? [selectedSource] : ['chitai-gorod', 'wildberries'];
    
    console.log('[searchBooks] Источники:', sources);
    
    // Показываем индикатор загрузки
    const resultsInfo = document.getElementById('results-info');
    if (resultsInfo) {
        resultsInfo.style.display = 'block';
        document.getElementById('results-count').textContent = '...';
    }
    
    try {
        // Используем smart-search API (сначала база, потом парсинг если нет результатов)
        const url = `${this.apiBaseUrl}/web/books/api/smart-search?q=${encodeURIComponent(query)}&sources=${sources.join(',')}`;
        
        const response = await fetch(url);
        
        if (!response.ok) throw new Error('Ошибка поиска');
        
        const data = await response.json();
        const books = data.books || [];
        
        console.log('[searchBooks] Найдено в базе:', books.length);
        
        // Если книг нет - запускаем подробный поиск
        if (books.length === 0) {
            console.log('[searchBooks] Книг в базе нет, запускаем подробный поиск...');
            await this.searchBooksDeep(query, sources);
            return;
        }
        
        // Показываем результаты
        this.data.books = books;
        this.catalogBooksTotal = books.length;
        this.renderBooks(books, true);
        
        // Обновляем счетчик
        const resultsCount = document.getElementById('results-count');
        if (resultsCount) resultsCount.textContent = books.length;
        
    } catch (error) {
        console.error('[searchBooks] Ошибка:', error);
        this.showError('Не удалось выполнить поиск');
    }
}

/**
 * Подробный поиск (всегда парсит сайты)
 * По умолчанию ищет по всем источникам
 */
async searchBooksDeep(query, sources = null) {
    if (!query || !query.trim()) {
        this.showError('Введите запрос для поиска');
        return;
    }

    console.log('[searchBooksDeep] Подробный поиск:', query);
    
    const container = document.getElementById('books-container');
    container.innerHTML = '<div class="loading"><div class="loading__spinner"></div><div class="loading__text">Ищем на сайтах магазинов...</div></div>';
    
    // Получаем выбранный источник из фильтра
    if (!sources) {
        const sourceSelect = document.getElementById('filter-source');
        const selectedSource = sourceSelect?.value;
        
        // По умолчанию оба источника, если не выбран конкретный
        sources = selectedSource ? [selectedSource] : ['chitai-gorod', 'wildberries'];
    }
    
    console.log('[searchBooksDeep] Источники:', sources);
    
    // Получаем telegram_id для проверки лимитов
    let telegramId = null;
    try {
        telegramId = window.tg.getChatId() || window.tg.getUser()?.id;
    } catch (e) {
        console.warn('[searchBooksDeep] Не удалось получить telegram_id');
    }
    
    // Показываем индикатор
    const resultsInfo = document.getElementById('results-info');
    if (resultsInfo) {
        resultsInfo.style.display = 'block';
        document.getElementById('results-count').textContent = '...';
    }
    
    try {
        const response = await fetch(`${this.apiBaseUrl}/api/parser/parse-body`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                sources: sources,
                fetch_details: false,  // Для подробного поиска не загружаем детали сразу
                telegram_id: telegramId
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Ошибка поиска');
        }
        
        const data = await response.json();
        console.log('[searchBooksDeep] Ответ:', data);
        
        if (data.task_id) {
            // Показываем статус задачи
            this.showParsingStatus(data.task_id, query);
        } else if (data.books && data.books.length > 0) {
            // Если результаты вернулись сразу
            this.data.books = data.books;
            this.catalogBooksTotal = data.total || data.books.length;
            this.renderBooks(data.books, true);
            
            const resultsCount = document.getElementById('results-count');
            if (resultsCount) resultsCount.textContent = data.books.length;
        } else {
            container.innerHTML = this.getEmptyState('Ничего не найдено', 'Попробуйте изменить запрос');
        }
        
    } catch (error) {
        console.error('[searchBooksDeep] Ошибка:', error);
        this.showError(error.message || 'Не удалось выполнить поиск');
    }
}

/**
 * Показать статус парсинга
 */
async showParsingStatus(taskId, query) {
    const container = document.getElementById('books-container');
    
    container.innerHTML = `
        <div class="card" style="text-align: center; padding: 24px;">
            <div class="loading__spinner" style="margin: 0 auto 16px;"></div>
            <h3>Идёт поиск...</h3>
            <p style="color: var(--text-secondary); margin-top: 8px;">
                Мы ищем книги по запросу "${query}" на сайтах магазинов
            </p>
            <p style="color: var(--text-muted); font-size: 0.85rem; margin-top: 16px;">
                Это может занять несколько минут
            </p>
        </div>
    `;
    
    // Опрос статуса задачи
    let attempts = 0;
    const maxAttempts = 60; // 60 попыток = ~5 минут
    
    const checkStatus = async () => {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/parser/task/${taskId}`);
            const data = await response.json();
            
            if (data.status === 'completed') {
                console.log('[showParsingStatus] Задача завершена:', data);
                
                if (data.books && data.books.length > 0) {
                    this.data.books = data.books;
                    this.catalogBooksTotal = data.total || data.books.length;
                    this.renderBooks(data.books, true);
                    
                    const resultsCount = document.getElementById('results-count');
                    if (resultsCount) resultsCount.textContent = data.books.length;
                } else {
                    container.innerHTML = this.getEmptyState('Ничего не найдено', 'Попробуйте изменить запрос');
                }
                return;
            } else if (data.status === 'failed') {
                this.showError(data.error || 'Ошибка поиска');
                return;
            }
            
            attempts++;
            if (attempts < maxAttempts) {
                setTimeout(checkStatus, 5000); // Проверяем каждые 5 секунд
            } else {
                this.showError('Превышено время ожидания');
            }
            
        } catch (error) {
            console.error('[showParsingStatus] Ошибка:', error);
            attempts++;
            if (attempts < maxAttempts) {
                setTimeout(checkStatus, 5000);
            }
        }
    };
    
    // Начинаем опрос
    setTimeout(checkStatus, 2000);
}
```

### Шаг 9: Обновить отображение книг (показать источник)

В функции `renderBooks` добавить отображение источника. Найти функцию `createBookCard` или `renderBooks` и добавить:

```javascript
createBookCard(book) {
    // ... существующий код ...
    
    // Добавляем источник
    const sourceLabel = SOURCES[book.source] || book.source;
    const sourceIcon = book.source === 'chitai-gorod' ? '📚' : '🛒';
    
    // Добавить в HTML карточки (после цены или в заголовок)
    // <div class="book-source">${sourceIcon} ${sourceLabel}</div>
    
    // ...
}
```

### Шаг 10: Убедиться что кнопки вызывают правильные функции

В `telegram/app/index.html` кнопки должны вызывать:

```html
<!-- Подробный поиск - всегда парсит сайты -->
<button class="btn" onclick="app.searchBooksDeep(document.getElementById('search-input').value)">
    <i class="fas fa-broadcast-tower"></i> Подробный поиск
</button>

<!-- Обычный поиск - сначала база, потом парсинг если нет -->
<button class="btn" onclick="app.searchBooks(document.getElementById('search-input').value)">
    <i class="fas fa-search"></i> Поиск
</button>
```

### Как это работает:

1. **Обычный поиск** (`searchBooks`):
   - Сначала ищет в базе данных
   - Если книг нет → автоматически запускает подробный поиск
   - По умолчанию ищет по всем источникам (chitai-gorod + wildberries)
   - Если пользователь выбрал источник в фильтре → ищет только по выбранному

2. **Подробный поиск** (`searchBooksDeep`):
   - Всегда парсит сайты магазинов
   - Показывает индикатор загрузки
   - Опросит статус задачи каждые 5 секунд
   - По умолчанию ищет по всем источникам

3. **Выбор источника**:
   - Пользователь может выбрать источник в фильтре "Источник"
   - Если не выбрано → используются оба источника
   - Если выбрано → используется только выбранный

---

## Обновление админки

### Шаг 10: Обновить отображение источников

В админке (если есть управление парсерами) добавить WB:

```python
# В модели Book или в admin.py
source = models.CharField(max_length=50, choices=[
    ('chitai-gorod', 'Читай-город'),
    ('wildberries', 'Wildberries'),
])
```

### Шаг 11: Добавить фильтр по источнику в админке

```python
@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_filter = ('source', 'parsed_at', 'discount_percent')
    list_display = ('title', 'author', 'source', 'current_price', 'discount_percent')
```

---

## Тестирование

### Проверка парсера
```bash
# Тестирование через Python
python -c "
import asyncio
from parsers.wildberries import WildberriesParser

async def test():
    parser = WildberriesParser()
    books = await parser.search_books('Майк Омер')
    print(f'Найдено книг: {len(books)}')
    for b in books[:3]:
        print(f'{b.title} - {b.current_price}₽ ({b.source})')

asyncio.run(test())
"
```

### Проверка API
```bash
# Тест с несколькими источниками
curl -X POST "https://mybook-hunter.ru/api/parser/parse-body" \
  -H "Content-Type: application/json" \
  -d '{"query": "Майк Омер", "sources": ["chitai-gorod", "wildberries"]}'
```

---

## Важные замечания

1. **Защита WB с cookies** - используем x_wbaas_token из браузера:
   - Получить токен можно из DevTools (F12) → Application → Cookies → x_wbaas_token
   - Токен без регистрации работает, но может истекать быстрее
   - Рекомендуется обновлять каждые 12 часов через Celery

2. **API WB** - структура API может меняться. Актуальные эндпоинты:
   - `https://search.wb.ru/exactmatch/ru/common/v18/search` - поиск (используется в коде)
   - `https://search.wb.ru/exactmatch/ru/common/v18/product/{id}` - детали

3. **"Левый трафик"** - без корректных cookies WB может показывать нерелевантные результаты. Всегда используйте cookies!

4. **Лимиты** - добавить счетчик запросов для WB аналогично Chitai-Gorod

5. **Город (dest)** - параметр `dest` в API определяет регион. Значения:
   - `-1257786` - Москва
   - Другие ID можно посмотреть в API WB или через DevTools

---

## Настройка Celery задачи

### Шаг 12: Добавить задачу обновления cookies WB

В `services/celery_tasks.py` добавить:

```python
@celery_app.task(name="services.celery_tasks.update_wildberries_cookies")
def update_wildberries_cookies():
    """
    Обновление cookies Wildberries
    
    Запускается периодически (каждые 12 часов) или по триггеру
    """
    import requests
    from services.token_manager import get_token_manager
    
    logger = logging.getLogger(__name__)
    logger.info("Начало обновления cookies Wildberries")
    
    try:
        token_manager = get_token_manager()
        
        # Пробуем получить новые cookies
        # Вариант 1: Использовать браузерный метод (Selenium/Playwright)
        # Вариант 2: Использовать существующий токен из env
        
        wb_token = os.getenv("WB_X_WBAAS_TOKEN")
        
        if wb_token:
            cookies = {"x_wbaas_token": wb_token}
            ttl = int(os.getenv("WB_COOKIES_TTL", "43200"))
            
            success = token_manager.save_wildberries_cookies(cookies, ttl)
            
            if success:
                logger.info("Cookies WB успешно обновлены")
                token_manager.send_token_notification(
                    "success",
                    "Cookies Wildberries обновлены",
                    f"TTL: {ttl} сек"
                )
            else:
                logger.error("Не удалось сохранить cookies WB")
                token_manager.send_token_notification(
                    "error",
                    "Ошибка обновления cookies Wildberries",
                    "Не удалось сохранить в Redis"
                )
        else:
            logger.warning("WB_X_WBAAS_TOKEN не найден в env")
            token_manager.send_token_notification(
                "warning",
                "Токен WB не найден",
                "Используйте x_wbaas_token из браузера"
            )
            
    except Exception as e:
        logger.error(f"Ошибка обновления cookies WB: {e}")
        try:
            token_manager = get_token_manager()
            token_manager.send_token_notification(
                "error",
                "Ошибка обновления cookies WB",
                str(e)
            )
        except:
            pass
    
    return "completed"
```

### Шаг 13: Настроить периодическую задачу

В `celery_config.py` или `celery.py`:

```python
from celery.schedules import crontab

# Периодическое обновление cookies WB каждые 12 часов
CELERY_BEAT_SCHEDULE = {
    "update-wildberries-cookies": {
        "task": "services.celery_tasks.update_wildberries_cookies",
        "schedule": crontab(hour="*/12"),  # Каждые 12 часов
    },
}
```

---

## Следующие шаги после реализации

1. Тестирование парсера WB
2. Настройка лимитов запросов для WB
3. Добавление мониторинга (логи, ошибки)
4. Масштабирование на другие источники (Ozon, Яндекс Маркет)
