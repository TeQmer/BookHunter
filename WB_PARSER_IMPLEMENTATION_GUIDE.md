# Инструкция по созданию парсера WB (Wildberries)

## Содержание
1. [Анализ и логика работы](#анализ-и-логика-работы)
2. [Создание парсера Wildberries](#создание-парсера-wildberries)
3. [Обновление фабрики парсеров](#обновление-фабрики-парсеров)
4. [Обновление API](#обновление-api)
5. [Обновление Mini App](#обновление-mini-app)
6. [Обновление админки](#обновление-админки)

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

## Создание парсера Wildberries

### Шаг 1: Создать файл `parsers/wildberries.py`

Создать новый файл `parsers/wildberries.py` по аналогии с `chitai_gorod.py`:

```python
# parsers/wildberries.py
from typing import List, Optional
from parsers.base import BaseParser, Book
from services.logger import parser_logger
import aiohttp
import asyncio
import re

class WildberriesParser(BaseParser):
    """Парсер для Wildberries (wb.ru)"""
    
    def __init__(self):
        # Задержки для WB - могут потребоваться корректировки
        super().__init__("wildberries", delay_min=1.0, delay_max=2.0)
        self.base_url = "https://www.wildberries.ru"
        self.api_url = "https://catalog.wb.ru"
        
    async def search_books(self, query: str) -> List[Book]:
        """
        Поиск книг на Wildberries
        
        Args:
            query: Поисковый запрос (название или автор)
            
        Returns:
            Список найденных книг
        """
        books = []
        
        try:
            # WB использует API каталога
            # Пример API: https://catalog.wb.ru/catalog/books/v2/search?query=толстой
            search_url = f"{self.api_url}/catalog/books/v2/search"
            params = {
                "query": query,
                "limit": 100,
                "offset": 0
            }
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"
            }
            
            await self._random_delay()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        products = data.get("data", {}).get("products", [])
                        
                        for product in products:
                            book = self._parse_product(product, query)
                            if book:
                                books.append(book)
                                
        except Exception as e:
            parser_logger.error(f"[Wildberries] Ошибка поиска: {e}")
            
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
                
            # Цены
            current_price = product.get("price", 0)
            original_price = product.get("original_price", 0)
            
            # Если нет текущей цены, пробуем получить из скидки
            if not current_price:
                sale_price = product.get("salePrice", 0)
                current_price = sale_price / 100 if sale_price else 0
                
            if not original_price:
                price_unit = product.get("priceU", 0)
                original_price = price_unit / 100 if price_unit else current_price
                
            # Вычисляем скидку
            discount_percent = None
            if original_price and current_price and original_price > current_price:
                discount_percent = int(((original_price - current_price) / original_price) * 100)
            
            # Артикул (может содержать информацию об авторе)
            article = product.get("article", "")
            
            # URL книги
            product_url = f"{self.base_url}/catalog/{source_id}/detail.aspx"
            
            # Изображение
            image_url = None
            images = product.get("images", [])
            if images:
                # WB использует формат: //images.wbstatic.net/...
                img_path = images[0].get("path", "")
                if img_path:
                    image_url = f"https:{img_path}"
            
            # Автор - часто в наименовании или отдельным полем
            author = product.get("brand", "")
            
            # Создаем объект книги
            book = Book(
                source="wildberries",
                source_id=source_id,
                title=title,
                author=author if author else None,
                publisher=None,  # WB не всегда предоставляет
                binding=None,    # Можно попробовать получить из характеристик
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
        try:
            # Извлекаем ID из URL
            # URL формат: https://www.wb.ru/catalog/12345678/detail.aspx
            match = re.search(r'/catalog/(\d+)', url)
            if not match:
                return None
                
            product_id = match.group(1)
            
            # Получаем данные через API
            # API детальной информации может отличаться
            detail_url = f"{self.api_url}/catalog/books/v2/product/{product_id}"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            await self._random_delay()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(detail_url, headers=headers) as response:
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
        books = []
        
        try:
            # URL акционных книг
            # WB имеет раздел "Уценка" и "Товары со скидкой"
            discount_url = f"{self.api_url}/catalog/books/v2/search"
            params = {
                "discount": "45",  # Минимальная скидка 45%
                "limit": 100,
                "sort": "popular"
            }
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            await self._random_delay()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(discount_url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        products = data.get("data", {}).get("products", [])
                        
                        for product in products:
                            book = self._parse_product(product, "")
                            if book and book.discount_percent:
                                books.append(book)
                                
        except Exception as e:
            parser_logger.error(f"[Wildberries] Ошибка сканирования скидок: {e}")
            
        return books
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
            "default_source": "chitai-gorod"
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения источников: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения источников")
```

### Шаг 5: Обновить логику парсинга для нескольких источников

В `api/parser.py` нужно обновить функцию `parse_books_from_body` чтобы принимала массив sources и парсила каждый:

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

### Шаг 6: Обновить UI в `telegram/app/js/mini-app.js`

Добавить переключатель источников в поиске. Добавить в начало файла константу:

```javascript
// Источники для парсинга
const SOURCES = {
    'chitai-gorod': 'Читай-город',
    'wildberries': 'Wildberries'
};
```

### Шаг 7: Обновить функцию поиска

В функции `searchBooks` или аналогичной добавить возможность передавать sources:

```javascript
async searchBooks(query, page = 1, sources = ['chitai-gorod', 'wildberries']) {
    // ... существующий код ...
    
    // Используем sources в запросе
    const response = await fetch(
        `${this.apiBaseUrl}/api/parser/parse-body`,
        {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                sources: sources,
                fetch_details: isDetailed,
                telegram_id: user.id
            })
        }
    );
    // ...
}
```

### Шаг 8: Добавить UI переключатель источников

В HTML шаблоне (search.html) добавить чекбоксы:

```html
<div class="source-selector">
    <label>
        <input type="checkbox" name="source" value="chitai-gorod" checked>
        Читай-город
    </label>
    <label>
        <input type="checkbox" name="source" value="wildberries" checked>
        Wildberries
    </label>
</div>
```

### Шаг 9: Обновить отображение книг

В функции `renderBooks` добавить отображение источника:

```javascript
renderBooks(books) {
    // ... существующий код ...
    
    // Для каждой книги показываем источник
    const sourceLabel = SOURCES[book.source] || book.source;
    // Добавить в карточку книги
    // <span class="book-source">${sourceLabel}</span>
}
```

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

1. **Защита WB** - WB имеет защиту от парсинга. Может потребоваться:
   - Использование FlareSolverr (как для Chitai-Gorod)
   - Более длительные задержки между запросами
   - Ротация User-Agent

2. **API WB** - структура API может меняться. Проверить актуальность эндпоинтов:
   - `https://catalog.wb.ru/catalog/books/v2/search` - поиск
   - `https://catalog.wb.ru/catalog/books/v2/product/{id}` - детали

3. **Лимиты** - добавить счетчик запросов для WB аналогично Chitai-Gorod

4. **Обновление токена** - если WB начнет требовать токен, добавить задачу в Celery (см. TOKEN_UPDATE_GUIDE.md)

---

## Следующие шаги после реализации

1. Тестирование парсера WB
2. Настройка лимитов запросов для WB
3. Добавление мониторинга (логи, ошибки)
4. Масштабирование на другие источники (Ozon, Яндекс Маркет)
