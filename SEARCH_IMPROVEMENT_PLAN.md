# 🚀 ПЛАН УЛУЧШЕНИЯ ПОИСКА BOOKHUNTER

## 🎯 ЧТО НУЖНО СДЕЛАТЬ

### 🔥 СРОЧНО (1-2 дня):
1. **Исправить сохранение в БД** - книги не сохраняются после парсинга
2. **Добавить базовое кэширование** - Redis для частых запросов  
3. **Улучшить логику поиска** - гибридная логика И/ИЛИ

### ⚡ ВАЖНО (3-5 дней):
4. **Полнотекстовый поиск** - SQLite FTS или PostgreSQL
5. **Ранжирование результатов** - скоринг релевантности
6. **Фильтры и сортировка** - цена, жанр, автор, скидка

### 💡 ПОЛЕЗНО (1-2 недели):
7. **Автодополнение** - подсказки при вводе
8. **История поиска** - сохранение популярных запросов
9. **Расширенные источники** - добавление новых сайтов

---

## 🛠 ТЕХНИЧЕСКИЕ ИЗМЕНЕНИЯ

### 1. Исправление сохранения в БД:
```python
# В файле services/celery_tasks.py
async def _save_book(db: AsyncSession, book: ParserBook):
    try:
        # Проверяем существование
        result = await db.execute(
            select(DBBook).where(
                and_(DBBook.source == book.source, 
                     DBBook.source_id == book.source_id)
            )
        )
        existing_book = result.scalar_one_or_none()
        
        if existing_book:
            # Обновляем
            existing_book.current_price = book.current_price
            existing_book.parsed_at = datetime.now()
            await db.commit()
        else:
            # Создаем новую
            db_book = DBBook(
                source=book.source,
                source_id=book.source_id,
                title=book.title,
                author=book.author,
                current_price=book.current_price,
                original_price=book.original_price,
                discount_percent=book.discount_percent,
                url=book.url,
                image_url=book.image_url,
                parsed_at=datetime.now()
            )
            db.add(db_book)
            await db.commit()
            
    except Exception as e:
        print(f"Ошибка сохранения книги: {e}")
        await db.rollback()
```

### 2. Умный поиск с кэшированием:
```python
# В файле web/books.py
import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, db=1)

@router.get("/api/smart-search")
async def smart_search_books(
    q: str = Query(..., description="Поисковый запрос"),
    db: AsyncSession = Depends(get_db)
):
    # Проверяем кэш
    cache_key = f"search:{q.lower().strip()}"
    cached_result = redis_client.get(cache_key)
    
    if cached_result:
        return JSONResponse(json.loads(cached_result))
    
    # Ищем в базе с улучшенной логикой
    search_words = q.lower().split()
    stop_words = {"и", "в", "на", "с", "от", "до", "по", "о", "об", "а", "но", "или"}
    search_words = [word for word in search_words if word.strip() and word not in stop_words]
    
    if search_words:
        # Гибридная логика: точное совпадение + частичное
        conditions = []
        
        # Точное совпадение (высший приоритет)
        exact_conditions = []
        for word in search_words:
            exact_conditions.append(
                or_(
                    func.lower(Book.title) == word,
                    func.lower(Book.author) == word
                )
            )
        conditions.append(and_(*exact_conditions))
        
        # Частичное совпадение (средний приоритет)
        partial_conditions = []
        for word in search_words:
            partial_conditions.append(
                or_(
                    func.lower(Book.title).like(f"%{word}%"),
                    func.lower(Book.author).like(f"%{word}%")
                )
            )
        conditions.append(or_(*partial_conditions))
        
        # Объединяем условия
        final_query = select(Book).where(or_(*conditions))
    else:
        final_query = select(Book)
    
    # Сортируем по релевантности и цене
    final_query = final_query.order_by(
        # Сначала точное совпадение в заголовке
        func.case(
            (func.lower(Book.title) == q.lower(), 100),
            (func.lower(Book.author) == q.lower(), 80),
            default=0
        ),
        # Потом по скидке
        Book.discount_percent.desc().nullslast(),
        # Потом по цене
        Book.current_price.asc()
    ).limit(50)
    
    result = await db.execute(final_query)
    books = result.scalars().all()
    
    # Кэшируем результат на 1 час
    response_data = {
        "success": True,
        "query": q,
        "books": [book.to_dict() for book in books],
        "found_count": len(books),
        "cached": False
    }
    
    redis_client.setex(cache_key, 3600, json.dumps(response_data, default=str))
    
    return JSONResponse(response_data)
```

### 3. Полнотекстовый поиск:
```sql
-- Добавить FTS таблицу
CREATE VIRTUAL TABLE books_fts USING fts5(
    title, author, content=books, content_rowid=id
);

-- Триггер для автообновления
CREATE TRIGGER books_fts_update AFTER INSERT ON books
BEGIN
    INSERT INTO books_fts(rowid, title, author) 
    VALUES (NEW.id, NEW.title, NEW.author);
END;
```

### 4. API для фильтров:
```python
@router.get("/api/search/filters")
async def search_with_filters(
    q: str = Query(None, description="Поисковый запрос"),
    min_price: float = Query(None, ge=0, description="Минимальная цена"),
    max_price: float = Query(None, ge=0, description="Максимальная цена"),
    min_discount: int = Query(None, ge=0, le=100, description="Минимальная скидка"),
    sort_by: str = Query("relevance", description="Сортировка: price_asc, price_desc, discount, relevance"),
    page: int = Query(1, ge=1, description="Страница"),
    limit: int = Query(20, ge=1, le=100, description="Количество на страницу"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Book)
    
    # Поисковый запрос
    if q:
        # Используем FTS если доступен
        try:
            fts_query = select(Book).where(
                Book.id.in_(
                    select(books_fts.rowid).where(
                        books_fts.match(q)
                    )
                )
            )
            query = fts_query
        except:
            # Fallback на обычный поиск
            search_words = q.lower().split()
            conditions = []
            for word in search_words:
                conditions.append(
                    or_(
                        func.lower(Book.title).like(f"%{word}%"),
                        func.lower(Book.author).like(f"%{word}%")
                    )
                )
            query = query.where(or_(*conditions))
    
    # Фильтры по цене
    if min_price is not None:
        query = query.where(Book.current_price >= min_price)
    if max_price is not None:
        query = query.where(Book.current_price <= max_price)
    
    # Фильтр по скидке
    if min_discount is not None:
        query = query.where(Book.discount_percent >= min_discount)
    
    # Сортировка
    if sort_by == "price_asc":
        query = query.order_by(Book.current_price.asc())
    elif sort_by == "price_desc":
        query = query.order_by(Book.current_price.desc())
    elif sort_by == "discount":
        query = query.order_by(Book.discount_percent.desc().nullslast())
    else:  # relevance
        query = query.order_by(
            func.case(
                (func.lower(Book.title).like(f"%{q.lower()}%"), 100),
                (func.lower(Book.author).like(f"%{q.lower()}%"), 80),
                default=0
            ),
            Book.discount_percent.desc().nullslast(),
            Book.current_price.asc()
        )
    
    # Пагинация
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)
    
    result = await db.execute(query)
    books = result.scalars().all()
    
    return JSONResponse({
        "success": True,
        "query": q,
        "filters": {
            "min_price": min_price,
            "max_price": max_price,
            "min_discount": min_discount,
            "sort_by": sort_by
        },
        "pagination": {
            "page": page,
            "limit": limit,
            "total": len(books)
        },
        "books": [book.to_dict() for book in books]
    })
```

---

## 📊 ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ

### До улучшений:
- Время поиска: 4+ секунд
- Точность: 50% (много пропусков)
- База данных: пустая
- UX: плохой

### После улучшений:
- Время поиска: 0.1-0.5 секунд (кэш)
- Точность: 85%+ (полнотекстовый поиск)
- База данных: заполнена + актуальна
- UX: отличный (фильтры, автодополнение)

---

## 🎯 ПРИОРИТЕТЫ ДЛЯ РЕАЛИЗАЦИИ

### Неделя 1: Основы
1. ✅ Исправить сохранение в БД
2. ✅ Добавить кэширование
3. ✅ Улучшить логику поиска

### Неделя 2: Продвинутые функции
4. ✅ Полнотекстовый поиск
5. ✅ Ранжирование результатов  
6. ✅ Фильтры и сортировка

### Неделя 3: UX улучшения
7. ✅ Автодополнение
8. ✅ История поиска
9. ✅ Расширенные источники

---

*Готов приступить к реализации! Какой этап начинаем первым?*
