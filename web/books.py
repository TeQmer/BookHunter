"""Веб-интерфейс каталога книг"""
from fastapi import APIRouter, Request, Depends, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from typing import List
import json
import logging
import string
import re

from database.config import get_db
from models.book import Book

logger = logging.getLogger(__name__)

def clean_search_words(text: str) -> List[str]:
    """
    Очищает текст от знаков пунктуации и разбивает на слова.
    """
    # Заменяем запятые, точки и другие разделители на пробелы
    text = re.sub(r'[,\.\!\?\:\;\-\—\(\)\[\]\{\}<>]', ' ', text)
    # Разбиваем на слова и очищаем каждый
    words = text.lower().split()
    # Удаляем оставшиеся знаки пунктуации из слов
    cleaned_words = [word.strip(string.punctuation) for word in words]
    # Убираем пустые строки
    return [word for word in cleaned_words if word.strip()]

# Создаем роутер
router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

@router.get("/", response_class=HTMLResponse)
async def list_books(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    source: str = Query(None),
    min_discount: str = Query(None),
    max_price: str = Query(None),
    search: str = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Список книг с фильтрацией и пагинацией"""
    try:
        # Преобразуем строковые параметры в числа, если они не пустые
        min_discount_int = None
        max_price_float = None
        
        if min_discount and min_discount.strip():
            try:
                min_discount_int = int(min_discount.strip())
                if not (0 <= min_discount_int <= 100):
                    min_discount_int = None
            except ValueError:
                min_discount_int = None
                
        if max_price and max_price.strip():
            try:
                max_price_float = float(max_price.strip())
                if max_price_float <= 0:
                    max_price_float = None
            except ValueError:
                max_price_float = None
        
        # Базовый запрос
        query = select(Book)
        
        # Применяем фильтры
        if source:
            query = query.where(Book.source == source)
        
        if min_discount_int is not None:
            query = query.where(Book.discount_percent >= min_discount_int)
        
        if max_price_float is not None:
            query = query.where(Book.current_price <= max_price_float)
        
        if search:
            # Улучшенный поиск: разбиваем запрос на слова и очищаем от пунктуации
            search_words = clean_search_words(search)
            
            # Фильтруем предлоги и союзы
            stop_words = {"и", "в", "на", "с", "от", "до", "по", "о", "об", "а", "но", "или"}
            search_words = [word for word in search_words if word.strip() and word not in stop_words]
            
            if search_words:
                # Создаем условия для каждого слова
                word_conditions = []
                for word in search_words:
                    word_conditions.append(
                        or_(
                            func.lower(Book.title).like(f"%{word}%"),
                            func.lower(Book.author).like(f"%{word}%")
                        )
                    )
                
                # Применяем логику ИЛИ - слово найдено в любом поле
                if word_conditions:
                    query = query.where(or_(*word_conditions))
        
        # Подсчет общего количества
        count_result = await db.execute(select(func.count()).select_from(query.subquery()))
        total = count_result.scalar() or 0
        
        # Пагинация
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page).order_by(Book.parsed_at.desc())
        
        # Выполняем запрос
        result = await db.execute(query)
        books = result.scalars().all()
        
        # Получаем статистику для фильтров
        sources = await db.execute(select(Book.source).distinct())
        available_sources = [row[0] for row in sources.fetchall()]
        
        # Вычисляем общее количество страниц
        total_pages = (total + per_page - 1) // per_page
        
        return templates.TemplateResponse(
            "books/list.html", 
            {
                "request": request, 
                "title": "Каталог книг",
                "books": books,
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "sources": available_sources,
                "filters": {
                    "source": source,
                    "min_discount": min_discount_int if min_discount_int is not None else "",
                    "max_price": max_price_float if max_price_float is not None else "",
                    "search": search
                }
            }
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request, 
                "title": "Ошибка",
                "error": f"Не удалось загрузить каталог: {str(e)}"
            }
        )

@router.get("/search", response_class=HTMLResponse)
async def search_books(
    request: Request,
    q: str = Query(None, description="Поисковый запрос"),
    source: str = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Поиск книг с автоматическим запуском парсинга если книги не найдены"""
    try:
        # Используем параметр q для поиска
        query_param = q
        
        # Базовый запрос
        search_query = select(Book)
        
        # Применяем фильтр по поисковому запросу - ищем в названии И авторе
        if query_param:
            # Улучшенный поиск: разбиваем запрос на слова и очищаем от пунктуации
            search_words = clean_search_words(query_param)
            
            # Фильтруем предлоги и союзы
            stop_words = {"и", "в", "на", "с", "от", "до", "по", "о", "об", "а", "но", "или"}
            search_words = [word for word in search_words if word.strip() and word not in stop_words]
            
            if search_words:
                # Создаем условия для каждого слова
                word_conditions = []
                for word in search_words:
                    word_conditions.append(
                        or_(
                            func.lower(Book.title).like(f"%{word}%"),
                            func.lower(Book.author).like(f"%{word}%")
                        )
                    )
                
                # Применяем логику ИЛИ - слово найдено в любом поле
                if word_conditions:
                    search_query = search_query.where(or_(*word_conditions))
        
        if source:
            search_query = search_query.where(Book.source == source)
        
        # Подсчет общего количества
        count_result = await db.execute(select(func.count()).select_from(search_query.subquery()))
        total = count_result.scalar() or 0
        
        # Пагинация
        offset = (page - 1) * per_page
        search_query = search_query.offset(offset).limit(per_page).order_by(Book.parsed_at.desc())
        
        # Выполняем запрос
        result = await db.execute(search_query)
        books = result.scalars().all()
        
        # Получаем статистику для фильтров
        sources = await db.execute(select(Book.source).distinct())
        available_sources = [row[0] for row in sources.fetchall()]
        
        # Вычисляем общее количество страниц
        total_pages = (total + per_page - 1) // per_page
        
        # Детальное логирование для отладки
        logger.info(f"🔍 Поиск по запросу '{query_param}': найдено {total} книг")
        if books:
            logger.info(f"📚 Примеры найденных книг: {[book.title[:50] + '...' if len(book.title) > 50 else book.title for book in books[:3]]}")
        
        return templates.TemplateResponse(
            "books/search.html", 
            {
                "request": request, 
                "title": f"Поиск книг: {query_param}" if query_param else "Поиск книг",
                "books": books,
                "query": query_param or "",
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "sources": available_sources,
                "auto_parse": True,  # Всегда автоматический режим
                "filters": {
                    "source": source
                }
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка поиска книг: {e}")
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request, 
                "title": "Ошибка",
                "error": f"Не удалось выполнить поиск: {str(e)}"
            }
        )

@router.get("/{book_id}", response_class=HTMLResponse)
async def book_detail(book_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """Детальная информация о книге"""
    try:
        book = await db.get(Book, book_id)
        if not book:
            raise HTTPException(status_code=404, detail="Книга не найдена")
            
        return templates.TemplateResponse(
            "books/detail.html", 
            {
                "request": request, 
                "title": book.title,
                "book": book
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request, 
                "title": "Ошибка",
                "error": f"Не удалось загрузить информацию о книге: {str(e)}"
            }
        )

# @router.get("/stats", response_class=HTMLResponse)
# async def books_stats(request: Request):
#     """Статистика по книгам - временно отключена"""
#     return templates.TemplateResponse(
#         "error.html", 
#         {
#             "request": request, 
#             "title": "Статистика временно недоступна",
#             "error": "Статистика временно недоступна. Вернется в следующем обновлении."
#         }
#     )

# ========== НОВЫЕ API ENDPOINTS ДЛЯ УМНОГО ПОИСКА ==========

@router.get("/api/all")
async def get_all_books(
    source: str = Query(None),
    min_discount: str = Query(None),
    max_price: str = Query(None),
    limit: int = Query(None),
    offset: int = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Получить все книги из базы данных для JavaScript фильтрации"""
    try:
        # Преобразуем строковые параметры в числа, если они не пустые
        min_discount_int = None
        max_price_float = None

        if min_discount and min_discount.strip():
            try:
                min_discount_int = int(min_discount.strip())
                if not (0 <= min_discount_int <= 100):
                    min_discount_int = None
            except ValueError:
                min_discount_int = None

        if max_price and max_price.strip():
            try:
                max_price_float = float(max_price.strip())
                if max_price_float <= 0:
                    max_price_float = None
            except ValueError:
                max_price_float = None

        # Базовый запрос
        query = select(Book)

        # Применяем фильтры
        if source:
            query = query.where(Book.source == source)

        if min_discount_int is not None:
            query = query.where(Book.discount_percent >= min_discount_int)

        if max_price_float is not None:
            query = query.where(Book.current_price <= max_price_float)

        # Подсчет общего количества
        count_result = await db.execute(select(func.count()).select_from(query.subquery()))
        total = count_result.scalar() or 0

        # Пагинация
        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)

        query = query.order_by(Book.parsed_at.desc())
        result = await db.execute(query)
        books = result.scalars().all()
        
        # Преобразуем в словари используя метод to_dict()
        books_list = []
        for book in books:
            books_list.append(book.to_dict())
        
        logger.info(f"Загружено {len(books_list)} книг для каталога (всего: {total})")

        return JSONResponse({
            "success": True,
            "books": books_list,
            "total": total
        })
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке всех книг: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "books": []
        })

@router.get("/api/search")
async def search_books_api(
    q: str = Query(..., description="Поисковый запрос"),
    source: str = Query(None, description="Фильтр по источнику"),
    min_discount: str = Query(None, description="Минимальная скидка"),
    max_price: str = Query(None, description="Максимальная цена"),
    limit: int = Query(None, description="Лимит результатов"),
    offset: int = Query(None, description="Смещение для пагинации"),
    db: AsyncSession = Depends(get_db)
):
    """Поиск книг по названию или автору с фильтрацией"""
    try:
        # Преобразуем строковые параметры в числа, если они не пустые
        min_discount_int = None
        max_price_float = None

        if min_discount and min_discount.strip():
            try:
                min_discount_int = int(min_discount.strip())
                if not (0 <= min_discount_int <= 100):
                    min_discount_int = None
            except ValueError:
                min_discount_int = None

        if max_price and max_price.strip():
            try:
                max_price_float = float(max_price.strip())
                if max_price_float <= 0:
                    max_price_float = None
            except ValueError:
                max_price_float = None

        # Ищем в базе данных по названию ИЛИ автору
        # Улучшенный поиск: разбиваем запрос на слова и очищаем от пунктуации
        search_words = clean_search_words(q)
        
        # Фильтруем предлоги и союзы
        stop_words = {"и", "в", "на", "с", "от", "до", "по", "о", "об", "а", "но", "или"}
        search_words = [word for word in search_words if word.strip() and word not in stop_words]
        
        if search_words:
            # Создаем условия для каждого слова
            word_conditions = []
            for word in search_words:
                word_conditions.append(
                    or_(
                        func.lower(Book.title).like(f"%{word}%"),
                        func.lower(Book.author).like(f"%{word}%")
                    )
                )
            
            # Применяем логику ИЛИ - слово найдено в любом поле
            query = select(Book).where(or_(*word_conditions))
        else:
            query = select(Book)
            
        # Применяем фильтры
        if source:
            query = query.where(Book.source == source)

        if min_discount_int is not None:
            query = query.where(Book.discount_percent >= min_discount_int)

        if max_price_float is not None:
            query = query.where(Book.current_price <= max_price_float)

        # Подсчет общего количества
        count_result = await db.execute(select(func.count()).select_from(query.subquery()))
        total = count_result.scalar() or 0

        # Пагинация
        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)

        query = query.order_by(Book.current_price.asc())
        
        result = await db.execute(query)
        books = result.scalars().all()
        
        # Преобразуем в словари используя метод to_dict()
        books_list = []
        for book in books:
            books_list.append(book.to_dict())
        
        logger.info(f"Поиск '{q}' (филтры: source={source}, min_discount={min_discount_int}, max_price={max_price_float}): найдено {len(books_list)} книг (всего: {total})")

        return JSONResponse({
            "success": True,
            "query": q,
            "books": books_list,
            "total": total,
            "found_count": len(books_list)
        })
        
    except Exception as e:
        logger.error(f"Ошибка при поиске книг: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "books": [],
            "total": 0,
            "found_count": 0
        })

@router.get("/api/smart-search")
async def smart_search_books(
    q: str = Query(..., description="Поисковый запрос"),
    source: str = Query("chitai-gorod", description="Источник парсинга"),
    db: AsyncSession = Depends(get_db)
):
    """Умный поиск книг: показываем ВСЕ книги из БД, сортируем по релевантности"""
    try:
        # Импортируем логику умного поиска
        from services.search_utils import is_book_similar, is_exact_match
        
        # Сначала ищем в базе данных (широкий поиск)
        search_words = clean_search_words(q)
        
        # Фильтруем предлоги и союзы
        stop_words = {"и", "в", "на", "с", "от", "до", "по", "о", "об", "а", "но", "или"}
        search_words = [word for word in search_words if word.strip() and word not in stop_words]
        
        if search_words:
            # Создаем условия для каждого слова
            word_conditions = []
            for word in search_words:
                word_conditions.append(
                    or_(
                        func.lower(Book.title).like(f"%{word}%"),
                        func.lower(Book.author).like(f"%{word}%")
                    )
                )
            
            # Применяем логику ИЛИ - слово найдено в любом поле
            search_query = select(Book).where(or_(*word_conditions))
        else:
            search_query = select(Book)
            
        search_query = search_query.order_by(Book.parsed_at.desc()).limit(50)
        
        result = await db.execute(search_query)
        db_books = result.scalars().all()
        
        # Проверяем релевантность каждой книги и сортируем
        exact_matches = []  # Точные совпадения
        partial_matches = []  # Частичные совпадения
        
        for book in db_books:
            is_similar, reason = is_book_similar(q, book.title, book.author)
            book_dict = book.to_dict()
            book_dict['relevance'] = reason
            
            if is_similar:
                exact_matches.append(book_dict)
                logger.info(f"Точное совпадение: '{book.title}' ({reason})")
            else:
                # Добавляем даже нерелевантные, но помечаем
                partial_matches.append(book_dict)
        
        # Объединяем: точные первыми, потом частичные
        all_relevant_books = exact_matches + partial_matches
        
        logger.info(f"Smart search '{q}': найдено {len(db_books)} в базе, точных: {len(exact_matches)}, частичных: {len(partial_matches)}")
        
        # ВСЕГДА возвращаем книги из базы (даже частично релевантные)
        if all_relevant_books:
            status = "found_exact" if exact_matches else "found_partial"
            message = f"Найдено {len(exact_matches)} точных и {len(partial_matches)} частичных совпадений"
            
            return JSONResponse({
                "success": True,
                "query": q,
                "source": source,
                "books": all_relevant_books,
                "found_count": len(all_relevant_books),
                "exact_match_count": len(exact_matches),
                "status": status,
                "message": message
            })
        
        # Только если совсем ничего нет - запускаем парсинг
        logger.info(f"Книги не найдены в базе для '{q}', запускаем парсинг")
        
        # Запускаем парсинг в фоне
        from services.celery_tasks import parse_books
        task = parse_books.delay(q, source)
        
        return JSONResponse({
            "success": True,
            "query": q,
            "source": source,
            "books": [],
            "found_count": 0,
            "status": "parsing_started",
            "task_id": task.id,
            "message": f"Книги по запросу '{q}' не найдены в каталоге. Запущен поиск новых книг..."
        })
        
    except Exception as e:
        logger.error(f"Ошибка умного поиска книг: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "books": [],
            "found_count": 0,
            "status": "error"
        })

@router.get("/api/check-database")
async def check_database_for_books(
    q: str = Query(..., description="Поисковый запрос"),
    db: AsyncSession = Depends(get_db)
):
    """Проверка наличия книг в базе данных"""
    try:
        # Улучшенный поиск: разбиваем запрос на слова и очищаем от пунктуации
        search_words = clean_search_words(q)
        
        # Фильтруем предлоги и союзы
        stop_words = {"и", "в", "на", "с", "от", "до", "по", "о", "об", "а", "но", "или"}
        search_words = [word for word in search_words if word.strip() and word not in stop_words]
        
        if search_words:
            # Создаем условия для каждого слова
            word_conditions = []
            for word in search_words:
                word_conditions.append(
                    or_(
                        func.lower(Book.title).like(f"%{word}%"),
                        func.lower(Book.author).like(f"%{word}%")
                    )
                )
            
            # Применяем логику ИЛИ - слово найдено в любом поле
            search_query = select(Book).where(or_(*word_conditions))
        else:
            search_query = select(Book)
            
        search_query = search_query.order_by(Book.parsed_at.desc()).limit(50)
        
        result = await db.execute(search_query)
        books = result.scalars().all()
        
        books_list = []
        for book in books:
            books_list.append(book.to_dict())
        
        logger.info(f"Database check for '{q}': найдено {len(books_list)} книг")
        
        return JSONResponse({
            "success": True,
            "query": q,
            "books": books_list,
            "booksFound": len(books_list)
        })
        
    except Exception as e:
        logger.error(f"Ошибка проверки базы данных: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "books": [],
            "booksFound": 0
        })
