"""Веб-интерфейс системы мониторинга скидок на книги"""
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from database.config import get_db
from models.book import Book
from models.alert import Alert
import os
import logging
import string
import re
from typing import List

# Импорт админ-панели
from web import admin

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

# Настройка шаблонов
templates = Jinja2Templates(directory="web/templates")
static_dir = os.path.join(os.path.dirname(__file__), "static")

@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Главная страница с реальной статистикой из базы данных"""
    
    # Получаем статистику из базы данных
    try:
        # Общее количество книг
        books_count = await db.execute(select(func.count(Book.id)))
        total_books = books_count.scalar() or 0
        
        # Общее количество активных подписок
        alerts_count = await db.execute(
            select(func.count(Alert.id)).where(Alert.is_active == True)
        )
        total_alerts = alerts_count.scalar() or 0
        
        # Средняя скидка по всем книгам со скидкой больше 0
        avg_discount_query = await db.execute(
            select(func.avg(Book.discount_percent)).where(Book.discount_percent > 0)
        )
        avg_discount = round(avg_discount_query.scalar() or 0)
        
        # Количество уникальных источников
        sources_count = await db.execute(
            select(func.count(func.distinct(Book.source))).where(Book.source.is_not(None))
        )
        total_sources = sources_count.scalar() or 0
        
        # Последние добавленные книги (последние 6)
        recent_books_query = await db.execute(
            select(Book).order_by(Book.parsed_at.desc()).limit(6)
        )
        recent_books = recent_books_query.scalars().all()
        
        logger.info(f"Главная страница: {total_books} книг, {total_alerts} подписок, средняя скидка {avg_discount}%")
        
        return templates.TemplateResponse("index.html", {
            "request": request,
            "title": "BookHunter - Мониторинг скидок на книги",
            "total_books": total_books,
            "total_alerts": total_alerts,
            "avg_discount": avg_discount,
            "total_sources": total_sources,
            "recent_books": recent_books
        })
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке главной страницы: {e}")
        # В случае ошибки показываем заглушки
        return templates.TemplateResponse("index.html", {
            "request": request,
            "title": "BookHunter - Мониторинг скидок на книги",
            "total_books": 0,
            "total_alerts": 0,
            "avg_discount": 0,
            "total_sources": 0,
            "recent_books": []
        })

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Панель управления"""
    return templates.TemplateResponse(
        "dashboard.html", 
        {"request": request, "title": "Панель управления"}
    )

@router.get("/health", response_class=HTMLResponse)
async def web_health(request: Request):
    """Страница состояния системы"""
    return templates.TemplateResponse(
        "health.html", 
        {"request": request, "title": "Состояние системы"}
    )

@router.get("/search", response_class=HTMLResponse)
async def search_books(
    request: Request,
    q: str = Query(..., description="Поисковый запрос"),
    db: AsyncSession = Depends(get_db)
):
    """Поиск книг по названию"""
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
            query = select(Book).where(or_(*word_conditions))
        else:
            query = select(Book)
            
        query = query.order_by(Book.parsed_at.desc()).limit(50)
        
        result = await db.execute(query)
        books = result.scalars().all()
        
        return templates.TemplateResponse(
            "books/search.html", 
            {
                "request": request, 
                "title": f"Поиск: {q}",
                "query": q,
                "books": books,
                "count": len(books)
            }
        )
        
    except Exception as e:
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request, 
                "title": "Ошибка поиска",
                "error": f"Не удалось выполнить поиск: {str(e)}"
            }
        )

# Подключаем роутер админ-панели
router.include_router(admin.router, prefix="/admin", tags=["admin"])

@router.get("/test-api", response_class=HTMLResponse)
async def test_api(request: Request):
    """Тестовая страница для проверки API"""
    return templates.TemplateResponse("test_api.html", {"request": request, "title": "Тест API"})
