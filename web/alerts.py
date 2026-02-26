"""Веб-интерфейс для управления подписками"""
import os
from fastapi import APIRouter, Request, Depends, HTTPException, Form, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import List, Optional
import json
import logging
from datetime import datetime

from database.config import get_db
from models.alert import Alert
from models.book import Book
from models.user import User

logger = logging.getLogger(__name__)

# Создаем роутер
router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

# ID администратора (можно вынести в конфигурацию)
ADMIN_TELEGRAM_IDS = [int(x) for x in os.getenv("ADMIN_TELEGRAM_IDS", "123456789").split(",")]


async def get_current_user_id(request: Request, user_id: Optional[str] = Cookie(None)) -> Optional[int]:
    """
    Получает ID текущего пользователя из cookies или запроса.
    Возвращает None для неавторизованных пользователей.
    """
    # Пробуем получить из cookie
    if user_id:
        try:
            return int(user_id)
        except (ValueError, TypeError):
            pass
    
    # Пробуем получить из query параметра (для демо режима)
    try:
        demo_user_id = request.query_params.get("user_id")
        if demo_user_id:
            return int(demo_user_id)
    except (ValueError, TypeError):
        pass
    
    return None


async def require_user_or_admin(request: Request, user_id: Optional[str] = Cookie(None)) -> int:
    """
    Проверяет, что пользователь авторизован.
    Возвращает ID пользователя или выбрасывает исключение.
    """
    current_user_id = await get_current_user_id(request, user_id)
    
    if not current_user_id:
        raise HTTPException(
            status_code=401,
            detail="Требуется авторизация. Пожалуйста, войдите через Telegram."
        )
    
    return current_user_id


async def can_view_alerts(request: Request, user_id: Optional[str] = Cookie(None)) -> tuple[bool, Optional[int]]:
    """
    Проверяет, может ли текущий пользователь видеть подписки.
    Возвращает (can_view: bool, user_id: Optional[int])
    """
    current_user_id = await get_current_user_id(request, user_id)
    
    # Если пользователь не авторизован - не показываем подписки
    if not current_user_id:
        return False, None
    
    # Администратор может видеть все подписки
    if current_user_id in ADMIN_TELEGRAM_IDS:
        return True, None  # None означает "все пользователи"
    
    # Обычный пользователь видит только свои подписки
    return True, current_user_id

@router.get("/", response_class=HTMLResponse)
async def list_alerts(request: Request, db: AsyncSession = Depends(get_db), user_id: Optional[str] = Cookie(None)):
    """Список подписок (только для владельца или админа)"""
    try:
        # Проверяем права доступа
        can_view, filter_user_id = await can_view_alerts(request, user_id)
        
        if not can_view:
            return templates.TemplateResponse(
                "error.html", 
                {
                    "request": request, 
                    "title": "Доступ запрещён",
                    "error": "Для просмотра подписок необходимо войти в систему через Telegram."
                }
            )
        
        # Строим запрос с учётом прав доступа
        if filter_user_id is None:
            # Админ видит все подписки
            result = await db.execute(
                select(Alert).where(Alert.is_active == True).order_by(Alert.created_at.desc())
            )
            alerts = result.scalars().all()
            
            # Добавляем информацию о пользователе для админа
            formatted_alerts = []
            for alert in alerts:
                # Получаем информацию о пользователе
                user_result = await db.execute(select(User).where(User.id == alert.user_id))
                user = user_result.scalar_one_or_none()
                
                formatted_alert = {
                    "id": alert.id,
                    "user_id": alert.user_id,
                    "user_name": user.first_name if user else f"User {alert.user_id}",
                    "title_query": alert.book_title,
                    "author_query": alert.book_author,
                    "max_price": alert.target_price,
                    "min_discount": alert.min_discount,
                    "is_active": alert.is_active,
                    "created_at": alert.created_at,
                    "updated_at": alert.updated_at
                }
                formatted_alerts.append(formatted_alert)
        else:
            # Обычный пользователь видит только свои подписки
            result = await db.execute(
                select(Alert).where(
                    and_(Alert.user_id == filter_user_id, Alert.is_active == True)
                ).order_by(Alert.created_at.desc())
            )
            alerts = result.scalars().all()
            
            formatted_alerts = []
            for alert in alerts:
                formatted_alert = {
                    "id": alert.id,
                    "title_query": alert.book_title,
                    "author_query": alert.book_author,
                    "max_price": alert.target_price,
                    "min_discount": alert.min_discount,
                    "is_active": alert.is_active,
                    "created_at": alert.created_at,
                    "updated_at": alert.updated_at
                }
                formatted_alerts.append(formatted_alert)
        
        return templates.TemplateResponse(
            "alerts/list.html", 
            {
                "request": request, 
                "title": "Мои подписки",
                "alerts": formatted_alerts,
                "is_admin": filter_user_id is None
            }
        )
    except Exception as e:
        logger.error(f"Ошибка при получении списка подписок: {e}")
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request, 
                "title": "Ошибка",
                "error": str(e)
            }
        )

@router.get("/new", response_class=HTMLResponse)
async def new_alert(request: Request):
    """Форма создания новой подписки"""
    return templates.TemplateResponse(
        "alerts/form.html", 
        {
            "request": request, 
            "title": "Новая подписка",
            "alert": None,
            "is_edit": False
        }
    )

@router.post("/")
async def create_alert_web(
    request: Request,
    title_query: str = Form(...),
    author_query: str = Form(None),
    max_price: float = Form(None),
    min_discount: int = Form(None),
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Cookie(None)
):
    """Создание новой подписки (только для авторизованных пользователей)"""
    try:
        from datetime import datetime
        
        # Проверяем авторизацию
        current_user_id = await require_user_or_admin(request, user_id)
        
        new_alert = Alert(
            user_id=current_user_id,
            book_title=title_query,
            book_author=author_query,
            book_source="chitai-gorod",
            target_price=max_price,
            min_discount=min_discount,
            is_active=True,
            notification_type="price_drop",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        db.add(new_alert)
        await db.commit()
        
        return RedirectResponse(url="/web/alerts", status_code=303)
        
    except Exception as e:
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request, 
                "title": "Ошибка",
                "error": f"Не удалось создать подписку: {str(e)}"
            }
        )

@router.get("/{alert_id}/edit", response_class=HTMLResponse)
async def edit_alert(alert_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """Редактирование подписки"""
    try:
        # Получаем подписку для редактирования
        from sqlalchemy import select
        result = await db.execute(select(Alert).where(Alert.id == alert_id))
        alert = result.scalar_one_or_none()
        if not alert:
            raise HTTPException(status_code=404, detail="Подписка не найдена")
            
        # Форматируем для совместимости с шаблоном
        formatted_alert = {
            "id": alert.id,
            "title_query": alert.book_title,
            "author_query": alert.book_author,
            "max_price": alert.target_price,
            "min_discount": alert.min_discount,
            "is_active": alert.is_active,
            "created_at": alert.created_at,
            "updated_at": alert.updated_at
        }
            
        return templates.TemplateResponse(
            "alerts/form.html", 
            {
                "request": request, 
                "title": "Редактирование подписки",
                "alert": formatted_alert,
                "is_edit": True
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request, 
                "title": "Ошибка",
                "error": str(e)
            }
        )

@router.post("/{alert_id}/edit")
async def update_alert_web(
    alert_id: int,
    request: Request,
    title_query: str = Form(...),
    author_query: str = Form(None),
    max_price: float = Form(None),
    min_discount: int = Form(None),
    is_active: bool = Form(True),
    db: AsyncSession = Depends(get_db)
):
    """Обновление подписки"""
    try:
        from datetime import datetime
        from sqlalchemy import select
        
        result = await db.execute(select(Alert).where(Alert.id == alert_id))
        alert = result.scalar_one_or_none()
        if not alert:
            raise HTTPException(status_code=404, detail="Подписка не найдена")
        
        alert.book_title = title_query
        alert.book_author = author_query
        alert.target_price = max_price
        alert.min_discount = min_discount
        alert.is_active = is_active
        alert.updated_at = datetime.utcnow()
        
        await db.commit()
        
        return RedirectResponse(url="/web/alerts", status_code=303)
        
    except HTTPException:
        raise
    except Exception as e:
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request, 
                "title": "Ошибка",
                "error": f"Не удалось обновить подписку: {str(e)}"
            }
        )

@router.post("/{alert_id}/delete")
async def delete_alert_web(
    alert_id: int, 
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Cookie(None)
):
    """Удаление подписки (только владелец или админ)"""
    try:
        from sqlalchemy import select
        
        # Получаем подписку
        result = await db.execute(select(Alert).where(Alert.id == alert_id))
        alert = result.scalar_one_or_none()
        if not alert:
            raise HTTPException(status_code=404, detail="Подписка не найдена")
        
        # Проверяем права доступа
        current_user_id = await get_current_user_id(request, user_id)
        
        if current_user_id is None:
            raise HTTPException(status_code=401, detail="Требуется авторизация")
        
        # Админ может удалять любые подписки
        is_admin = current_user_id in ADMIN_TELEGRAM_IDS
        
        # Проверяем, что пользователь - владелец подписки или админ
        if not is_admin and alert.user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Нет доступа к этой подписке")
        
        await db.delete(alert)
        await db.commit()
        
        return RedirectResponse(url="/web/alerts", status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка удаления: {str(e)}")

# ========== НОВЫЙ ENDPOINT ДЛЯ СОЗДАНИЯ ПОДПИСКИ ИЗ КНИГИ ==========

@router.post("/create-from-book")
async def create_alert_from_book(
    data: dict,
    db: AsyncSession = Depends(get_db)
):
    """Создание подписки из карточки книги"""
    try:
        book_id = data.get('book_id')
        target_price = data.get('target_price')
        min_discount = data.get('min_discount')
        book_url = data.get('book_url', '')
        
        if not book_id or not target_price:
            return JSONResponse({
                "success": False,
                "detail": "Необходимо указать ID книги и целевую цену"
            }, status_code=400)
        
        # Получаем информацию о книге
        result = await db.execute(select(Book).where(Book.id == book_id))
        book = result.scalar_one_or_none()
        
        if not book:
            return JSONResponse({
                "success": False,
                "detail": "Книга не найдена"
            }, status_code=404)
        
        # Проверяем, существует ли уже подписка на эту книгу
        existing_alert = await db.execute(
            select(Alert).where(
                Alert.book_id == book_id,
                Alert.is_active == True
            )
        )
        
        if existing_alert.scalar_one_or_none():
            return JSONResponse({
                "success": False,
                "detail": "Подписка на эту книгу уже существует"
            }, status_code=400)
        
        # Создаем новую подписку
        new_alert = Alert(
            user_id=1,  # Пример пользователя
            book_id=book_id,
            book_title=book.title,
            book_author=book.author,
            target_price=target_price,
            min_discount=min_discount,
            book_url=book_url,
            is_active=True,
            notification_type='price_drop',
            book_source='chitai-gorod',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            search_query=f"{book.title} {book.author or ''}".strip()
        )
        
        db.add(new_alert)
        await db.commit()
        
        logger.info(f"Создана подписка на книгу '{book.title}' с целевой ценой {target_price}₽")
        
        return JSONResponse({
            "success": True,
            "message": "Подписка создана успешно",
            "alert_id": new_alert.id,
            "book_title": book.title,
            "target_price": target_price
        })
        
    except Exception as e:
        logger.error(f"Ошибка создания подписки из книги: {e}")
        return JSONResponse({
            "success": False,
            "detail": f"Ошибка создания подписки: {str(e)}"
        }, status_code=500)
