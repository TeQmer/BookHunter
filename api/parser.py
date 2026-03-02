from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_
from typing import Optional, List
from celery.result import AsyncResult
import uuid
import string
import re

from database.config import get_db, get_sync_db
from services.celery_tasks import parse_books
from services.logger import logger
from api.request_limits import RequestLimitChecker
from models.book import Book
from models.user import User

router = APIRouter()

__all__ = ["router"]

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


def check_request_limit(sync_db: Session, telegram_id: int) -> tuple[bool, Optional[User], str]:
    """
    Проверяет лимит запросов пользователя.

    Returns:
        tuple: (can_parse: bool, user: Optional[User], message: str)
    """
    try:
        user = RequestLimitChecker.check_and_increment_request(sync_db, telegram_id)
        return True, user, ""
    except HTTPException as e:
        # Лимит исчерпан
        return False, None, e.detail
    except Exception as e:
        logger.error(f"Ошибка проверки лимитов: {e}")
        # При ошибке позволяем парсить (лучше разрешить, чем заблокировать)
        return True, None, ""


async def search_books_in_db(query: str, db: AsyncSession, sources: List[str] = None, limit: int = 50) -> tuple[List[dict], int]:
    """
    Ищет книги в базе данных по запросу.
    
    Args:
        query: Поисковый запрос
        db: Сессия базы данных
        sources: Список источников для фильтрации (если None - все)
        limit: Максимальное количество результатов
    
    Returns:
        tuple: (books_list: List[dict], total: int)
    """
    search_words = clean_search_words(query)
    stop_words = {"и", "в", "на", "с", "от", "до", "по", "о", "об", "а", "но", "или"}
    search_words = [word for word in search_words if word.strip() and word not in stop_words]
    
    if search_words:
        word_conditions = []
        for word in search_words:
            word_conditions.append(
                or_(
                    func.lower(Book.title).like(f"%{word}%"),
                    func.lower(Book.author).like(f"%{word}%")
                )
            )
        db_query = select(Book).where(or_(*word_conditions))
    else:
        db_query = select(Book)
            
    # Фильтр по источникам
    if sources:
        db_query = db_query.where(Book.source.in_(sources))
            
    # Подсчёт общего количества
    count_result = await db.execute(select(func.count()).select_from(db_query.subquery()))
    total = count_result.scalar() or 0
    
    # Получаем книги
    db_query = db_query.order_by(Book.current_price.asc()).limit(limit)
    result = await db.execute(db_query)
    books = result.scalars().all()
    
    books_list = []
    for book in books:
        books_dict = book.to_dict()
        books_list.append(books_dict)
    
    return books_list, total

@router.post("/parse")
async def parse_books_on_demand(
    query: str = Query(..., description="Поисковый запрос"),
    source: str = Query("chitai-gorod", description="Источник парсинга"),
    db: AsyncSession = Depends(get_db)
):
    """Запуск парсинга книг по запросу в реальном времени"""
    
    try:
        # Запускаем фоновую задачу парсинга
        task = parse_books.delay(query, source)
        
        logger.info(f"Запущен парсинг для запроса: '{query}' (task_id: {task.id})")
        
        return {
            "task_id": task.id,
            "status": "started",
            "message": f"Парсинг запущен для запроса: '{query}'",
            "query": query,
            "source": source
        }
        
    except Exception as e:
        logger.error(f"Ошибка запуска парсинга: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка запуска парсинга: {str(e)}")

@router.post("/parse-body")
async def parse_books_from_body(
    data: dict,
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db)
):
    """Запуск парсинга книг по запросу в реальном времени (через тело запроса)

    Параметры запроса:
    - query: Поисковый запрос (обязательно)
    - source: Источник парсинга (по умолчанию chitai-gorod)
    - fetch_details: Загружать ли детальную страницу для извлечения характеристик (издательство, переплёт, жанры) - по умолчанию False
    - telegram_id: ID пользователя в Telegram (для проверки лимитов)
    """

    try:
        query = data.get("query")
        
        # Поддержка как строки, так и массива источников
        sources_param = data.get("sources", ["chitai-gorod", "wildberries"])
        if isinstance(sources_param, str):
            sources = [sources_param]
        else:
            sources = sources_param
        
        fetch_details = data.get("fetch_details", False)
        telegram_id = data.get("telegram_id")
        
        if not query:
            raise HTTPException(status_code=400, detail="Поле 'query' обязательно")
        
        # Проверяем лимиты запросов пользователя
        if telegram_id:
            can_parse, user, error_message = check_request_limit(sync_db, telegram_id)
            
            if not can_parse:
                # Лимит исчерпан - ищем только в базе данных
                logger.info(f"Лимит исчерпан для пользователя {telegram_id}. Ищем только в базе данных.")
                
                books_list, total = await search_books_in_db(query, db, sources=sources)
                
                return {
                    "status": "limit_exceeded",
                    "message": error_message,
                    "query": query,
                    "sources": sources,
                    "books": books_list,
                    "total": total,
                    "found_in_db": True,
                    "parsed": False,
                    "limit_exceeded": True
                }
            
            logger.info(f"Пользователь {telegram_id} использует запрос ({user.daily_requests_used}/{user.daily_requests_limit})")

        # Сначала ищем в базе данных
        books_list, total = await search_books_in_db(query, db, sources=sources)
        
        # Запускаем парсинг ТОЛЬКО если книги НЕ найдены в базе
        should_parse = total == 0
        
        if should_parse:
            # Проверяем, не запущен ли уже парсинг для этого запроса (дедупликация)
            import redis
            import os
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            redis_password = os.getenv("REDIS_PASSWORD")
            
            parse_already_running = False
            if redis_url and redis_password:
                try:
                    import re
                    redis_pattern = r'redis://:(?P<password>[^@]+)@(?P<host>[^:]+):(?P<port>\d+)/\d+'
                    match = re.match(redis_pattern, redis_url)
                    if not match:
                        host = redis_url.split("://")[1].split(":")[0]
                        port = redis_url.split(":")[-1].split("/")[0]
                        redis_url = f"redis://:{redis_password}@{host}:{port}/0"
                    
                    redis_client = redis.from_url(redis_url, decode_responses=True)
                    parse_lock_key = f"parse_lock:{query.lower().strip()}"
                    
                    if redis_client.exists(parse_lock_key):
                        parse_already_running = True
                        logger.info(f"Парсинг для '{query}' уже запущен, пропускаем")
                    else:
                        redis_client.setex(parse_lock_key, 300, "1")
                    
                    redis_client.close()
                except Exception as e:
                    logger.warning(f"Ошибка проверки Redis: {e}")
            
            if not parse_already_running:
                # Запускаем фоновую задачу парсинга для каждого источника
                # max_pages=1 означает парсить только первую страницу (25 книг)
                task_ids = []
                for src in sources:
                    task = parse_books.delay(query=query, source=src, fetch_details=fetch_details, max_pages=1)
                    task_ids.append({"source": src, "task_id": task.id})
                    logger.info(f"Запущен парсинг для '{query}' из '{src}' (task_id: {task.id})")
                
                return {
                    "tasks": task_ids,
                    "status": "started",
                    "message": f"Книги не найдены в базе. Парсинг запущен для источников: {', '.join(sources)}",
                    "query": query,
                    "sources": sources,
                    "fetch_details": fetch_details,
                    "books": books_list,
                    "total": total,
                    "found_in_db": True,
                    "parsed": True
                }
        
        # Книги уже есть в базе - не запускаем парсинг
        logger.info(f"Книги уже есть в базе ({total} шт.). Парсинг не требуется.")
        
        return {
            "task_id": None,
            "status": "found_in_db",
            "message": f"Найдено {total} книг в базе данных",
            "query": query,
            "sources": sources,
            "books": books_list,
            "total": total,
            "found_in_db": True,
            "parsed": False
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка запуска парсинга: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка запуска парсинга: {str(e)}")

@router.get("/parse/{task_id}")
async def get_parse_status(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Проверка статуса задачи парсинга"""
    
    try:
        task = AsyncResult(task_id)
        
        if task.state == 'PENDING':
            return {
                "task_id": task_id,
                "status": "pending",
                "message": "🔄 Задача поставлена в очередь на выполнение..."
            }
        elif task.state == 'STARTED':
            return {
                "task_id": task_id,
                "status": "running",
                "message": "🔍 Ищем книги на сайте, проверяем цены и скидки..."
            }
        elif task.state == 'SUCCESS':
            result = task.result
            if isinstance(result, dict):
                books_found = result.get('books_found', 0)
                books_added = result.get('books_added', 0)
                message = result.get('message', f'Парсинг завершен. Найдено книг: {books_found}')
                return {
                    "task_id": task_id,
                    "status": "completed",
                    "message": f"✅ Парсинг завершен! Найдено {books_found} книг, сохранено {books_added}",
                    "books_found": books_found,
                    "books_added": books_added,
                    "result": result
                }
            else:
                # Старый формат ответа
                return {
                    "task_id": task_id,
                    "status": "completed",
                    "message": f"✅ Парсинг завершен! Найдено книг: {result}",
                    "books_found": result
                }
        else:
            return {
                "task_id": task_id,
                "status": task.state,
                "message": f"❌ Ошибка выполнения задачи: {task.info}"
            }
            
    except Exception as e:
        logger.error(f"Ошибка проверки статуса задачи: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка проверки статуса: {str(e)}")

@router.post("/search")
async def search_books_with_parsing(
    query: str = Query(..., description="Поисковый запрос"),
    source: str = Query("chitai-gorod", description="Источник парсинга"),
    max_wait: int = Query(10, description="Максимальное время ожидания (секунды)"),
    db: AsyncSession = Depends(get_db)
):
    """Поиск книг с автоматическим парсингом новых результатов"""
    
    try:
        # Сначала ищем в базе данных
        from sqlalchemy import select, func, and_, or_
        from models import Book
        
        # Улучшенный поиск: разбиваем запрос на слова и очищаем от пунктуации
        search_words = clean_search_words(query)
        
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
            db_query = select(Book).where(or_(*word_conditions))
        else:
            db_query = select(Book)
            
        db_query = db_query.order_by(Book.parsed_at.desc()).limit(20)
        
        db_result = await db.execute(db_query)
        db_books = db_result.scalars().all()
        
        # Запускаем парсинг в фоне с использованием ключевых слов
        parse_task = parse_books.delay(query=query, source=source)
        
        logger.info(f"Запущен поиск с парсингом для: '{query}' (task_id: {parse_task.id})")
        
        # Возвращаем результат с информацией о фоновом парсинге
        return {
            "query": query,
            "source": source,
            "db_books": [
                {
                    "id": book.id,
                    "title": book.title,
                    "author": book.author,
                    "current_price": book.current_price,
                    "original_price": book.original_price,
                    "discount_percent": book.discount_percent,
                    "url": book.url,
                    "image_url": book.image_url,
                    "source": book.source,
                    "parsed_at": book.parsed_at.isoformat() if book.parsed_at else None
                }
                for book in db_books
            ],
            "parse_task_id": parse_task.id,
            "parse_status": "started",
            "message": f"Найдено {len(db_books)} книг в базе. Запущен поиск новых книг...",
            "total_db_books": len(db_books)
        }
        
    except Exception as e:
        logger.error(f"Ошибка поиска с парсингом: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка поиска: {str(e)}")

@router.get("/books/{query}")
async def get_books_by_query(
    query: str,
    source: str = Query("chitai-gorod", description="Источник парсинга"),
    db: AsyncSession = Depends(get_db)
):
    """Получение книг по конкретному поисковому запросу для динамического добавления"""
    
    try:
        from sqlalchemy import select, func, or_
        from models.book import Book
        
        # Декодируем URL-кодированный запрос
        import urllib.parse
        decoded_query = urllib.parse.unquote(query)
        
        logger.info(f"Searching for books with query: '{decoded_query}' (original: '{query}')")
        
        # Улучшенный поиск: ищем по всем словам из запроса и очищаем от пунктуации
        search_terms = clean_search_words(decoded_query)
        
        # Создаем условия поиска для каждого слова
        search_conditions = []
        for term in search_terms:
            if term.strip():  # Игнорируем пустые слова
                search_conditions.extend([
                    func.lower(Book.title).like(f"%{term.strip()}%"),
                    func.lower(Book.author).like(f"%{term.strip()}%")
                ])
        
        # Если есть условия поиска, применяем их
        if search_conditions:
            search_query = select(Book).where(
                or_(*search_conditions)
            ).order_by(Book.parsed_at.desc()).limit(50)
        else:
            # Если запрос пустой, возвращаем последние книги
            search_query = select(Book).order_by(Book.parsed_at.desc()).limit(50)
        
        result = await db.execute(search_query)
        books = result.scalars().all()
        
        # Преобразуем в словари используя метод to_dict()
        books_list = []
        for book in books:
            books_dict = book.to_dict()
            # Декодируем строки для правильного отображения
            if books_dict.get('title'):
                books_dict['title'] = urllib.parse.unquote(str(books_dict['title']))
            if books_dict.get('author'):
                books_dict['author'] = urllib.parse.unquote(str(books_dict['author']))
            books_list.append(books_dict)
        
        logger.info(f"Found {len(books_list)} books for query: '{decoded_query}'")
        
        return {
            "success": True,
            "query": decoded_query,
            "source": source,
            "books": books_list,
            "total": len(books_list),
            "message": f"Найдено {len(books_list)} книг по запросу '{decoded_query}'"
        }
        
    except Exception as e:
        logger.error(f"Error getting books for query '{query}': {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка получения книг: {str(e)}")

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

@router.get("/book/{book_id}")
async def get_book_by_id(
    book_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получение книги по ID для детального просмотра"""
    
    try:
        from sqlalchemy import select
        from models.book import Book
        
        result = await db.execute(select(Book).where(Book.id == book_id))
        book = result.scalar_one_or_none()
        
        if not book:
            raise HTTPException(status_code=404, detail="Книга не найдена")
        
        return {
            "success": True,
            "book": book.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения книги {book_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения книги: {str(e)}")
