from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Dict, Any
from datetime import datetime, timedelta
from database.config import get_db
from models import Book, Alert, Notification, User, ParsingLog
from services.logger import logger

router = APIRouter()

__all__ = ["router"]

@router.get("/main")
async def get_main_page_stats(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Статистика для главной страницы - оптимизированная версия"""
    
    try:
        # Основные показатели для главной страницы
        # Общее количество книг
        total_books_result = await db.execute(select(func.count(Book.id)))
        total_books = total_books_result.scalar() or 0
        
        # Активные подписки
        active_alerts_result = await db.execute(
            select(func.count(Alert.id)).where(Alert.is_active == True)
        )
        total_alerts = active_alerts_result.scalar() or 0
        
        # Средняя скидка (только для книг со скидкой)
        avg_discount_result = await db.execute(
            select(func.avg(Book.discount_percent)).where(Book.discount_percent < 0)
        )
        avg_discount = round(abs(avg_discount_result.scalar() or 0), 1)
        
        # Количество уникальных магазинов
        sources_result = await db.execute(select(func.count(func.distinct(Book.source))))
        total_sources = sources_result.scalar() or 0
        
        # Последние добавленные книги (5 штук)
        recent_books_result = await db.execute(
            select(Book)
            .order_by(Book.parsed_at.desc())
            .limit(5)
        )
        recent_books_data = recent_books_result.scalars().all()
        
        # Форматируем книги для главной страницы
        recent_books = []
        for book in recent_books_data:
            recent_books.append({
                "id": book.id,
                "title": book.title,
                "author": book.author,
                "current_price": book.current_price,
                "discount_percent": book.discount_percent,
                "source": book.source,
                "image_url": book.image_url,
                "url": book.url,
                "parsed_at": book.parsed_at.isoformat() if book.parsed_at else None
            })
        
        logger.info(f"Загружена статистика для главной страницы: {total_books} книг, {total_alerts} подписок")
        
        return {
            "total_books": total_books,
            "total_alerts": total_alerts,
            "avg_discount": avg_discount,
            "total_sources": total_sources,
            "recent_books": recent_books,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики для главной страницы: {e}")
        # Возвращаем заглушку при ошибке
        return {
            "total_books": 0,
            "total_alerts": 0,
            "avg_discount": 0,
            "total_sources": 0,
            "recent_books": [],
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/")
async def get_stats(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Получение общей статистики системы"""
    
    try:
        # Статистика по книгам
        books_result = await db.execute(
            select(func.count(Book.id)).where(Book.parsed_at >= datetime.now() - timedelta(days=30))
        )
        books_last_30_days = books_result.scalar() or 0
        
        books_result = await db.execute(select(func.count(Book.id)))
        total_books = books_result.scalar() or 0
        
        # Статистика по подпискам
        alerts_result = await db.execute(
            select(func.count(Alert.id)).where(Alert.is_active == True)
        )
        active_alerts = alerts_result.scalar() or 0
        
        alerts_result = await db.execute(select(func.count(Alert.id)))
        total_alerts = alerts_result.scalar() or 0
        
        # Статистика по уведомлениям
        notifications_result = await db.execute(
            select(func.count(Notification.id)).where(
                Notification.sent_at >= datetime.now() - timedelta(days=24)
            )
        )
        notifications_24h = notifications_result.scalar() or 0
        
        notifications_result = await db.execute(select(func.count(Notification.id)))
        total_notifications = notifications_result.scalar() or 0
        
        # Статистика по пользователям
        users_result = await db.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )
        active_users = users_result.scalar() or 0
        
        # Статистика по магазинам
        stores_result = await db.execute(
            select(Book.source, func.count(Book.id))
            .group_by(Book.source)
        )
        stores_stats = dict(stores_result.all())
        
        # Статистика по логам парсинга (отключаем, т.к. таблица не создана)
        logs_7_days = 0
        successful_parses = 0
        
        return {
            "timestamp": datetime.now().isoformat(),
            "books": {
                "total": total_books,
                "last_30_days": books_last_30_days,
                "by_store": stores_stats
            },
            "alerts": {
                "total": total_alerts,
                "active": active_alerts
            },
            "notifications": {
                "total": total_notifications,
                "last_24h": notifications_24h
            },
            "users": {
                "active": active_users
            },
            "parsing": {
                "logs_7_days": logs_7_days,
                "successful_parses": successful_parses,
                "success_rate": round((successful_parses / max(logs_7_days, 1)) * 100, 2)
            }
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения статистики")

@router.get("/books")
async def get_books_stats(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Детальная статистика по книгам"""
    
    try:
        # Книги со скидками
        discount_result = await db.execute(
            select(func.count(Book.id)).where(Book.discount_percent < 0)
        )
        books_with_discounts = discount_result.scalar() or 0
        
        # Средняя скидка
        avg_discount_result = await db.execute(
            select(func.avg(Book.discount_percent)).where(Book.discount_percent < 0)
        )
        average_discount = abs(avg_discount_result.scalar() or 0)
        
        # Ценовой диапазон
        price_result = await db.execute(
            select(func.min(Book.current_price), func.max(Book.current_price))
        )
        min_price, max_price = price_result.first()
        
        # Топ магазинов по количеству книг
        top_stores_result = await db.execute(
            select(Book.source, func.count(Book.id))
            .group_by(Book.source)
            .order_by(func.count(Book.id).desc())
            .limit(5)
        )
        top_stores = dict(top_stores_result.all())
        
        # Книги, добавленные за последние 7 дней
        recent_result = await db.execute(
            select(func.count(Book.id)).where(
                Book.parsed_at >= datetime.now() - timedelta(days=7)
            )
        )
        recent_books = recent_result.scalar() or 0
        
        # Общее количество книг
        total_books_result = await db.execute(select(func.count(Book.id)))
        total_books = total_books_result.scalar() or 0
        
        return {
            "total_books": total_books,
            "books_with_discounts": books_with_discounts,
            "average_discount": round(average_discount, 2),
            "price_range": {
                "min": round(min_price or 0, 2),
                "max": round(max_price or 0, 2)
            },
            "top_stores": top_stores,
            "recent_7_days": recent_books,
            "discount_percentage": round((books_with_discounts / max(total_books, 1)) * 100, 2)
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики книг: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения статистики книг")

@router.get("/alerts")
async def get_alerts_stats(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Детальная статистика по подпискам"""
    
    try:
        # Подписки по статусу
        active_result = await db.execute(
            select(func.count(Alert.id)).where(Alert.is_active == True)
        )
        active_alerts = active_result.scalar() or 0
        
        inactive_result = await db.execute(
            select(func.count(Alert.id)).where(Alert.is_active == False)
        )
        inactive_alerts = inactive_result.scalar() or 0
        
        # Подписки с фильтрами по цене
        price_filtered_result = await db.execute(
            select(func.count(Alert.id)).where(Alert.max_price.isnot(None))
        )
        price_filtered = price_filtered_result.scalar() or 0
        
        # Подписки с фильтрами по скидке
        discount_filtered_result = await db.execute(
            select(func.count(Alert.id)).where(Alert.min_discount.isnot(None))
        )
        discount_filtered = discount_filtered_result.scalar() or 0
        
        # Подписки, созданные за последние 7 дней
        recent_alerts_result = await db.execute(
            select(func.count(Alert.id)).where(
                Alert.created_at >= datetime.now() - timedelta(days=7)
            )
        )
        recent_alerts = recent_alerts_result.scalar() or 0
        
        return {
            "total": active_alerts + inactive_alerts,
            "active": active_alerts,
            "inactive": inactive_alerts,
            "with_price_filter": price_filtered,
            "with_discount_filter": discount_filtered,
            "recent_7_days": recent_alerts,
            "active_percentage": round((active_alerts / max(active_alerts + inactive_alerts, 1)) * 100, 2)
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики подписок: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения статистики подписок")

@router.get("/notifications")
async def get_notifications_stats(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Детальная статистика по уведомлениям"""
    
    try:
        # Общее количество
        total_result = await db.execute(select(func.count(Notification.id)))
        total_notifications = total_result.scalar() or 0
        
        # Отправленные в Telegram (используем правильное поле из базы)
        telegram_sent_result = await db.execute(
            select(func.count(Notification.id)).where(Notification.sent_telegram == True)
        )
        telegram_sent = telegram_sent_result.scalar() or 0
        
        # Добавленные в Sheets (отключаем, т.к. колонки нет)
        sheets_sent = 0
        
        # За последние 24 часа
        last_24h_result = await db.execute(
            select(func.count(Notification.id)).where(
                Notification.sent_at >= datetime.now() - timedelta(hours=24)
            )
        )
        last_24h = last_24h_result.scalar() or 0
        
        # За последние 7 дней
        last_7d_result = await db.execute(
            select(func.count(Notification.id)).where(
                Notification.sent_at >= datetime.now() - timedelta(days=7)
            )
        )
        last_7d = last_7d_result.scalar() or 0
        
        # Среднее количество в день
        avg_per_day = round(last_7d / 7, 2) if last_7d > 0 else 0
        
        return {
            "total": total_notifications,
            "telegram_sent": telegram_sent,
            "sheets_sent": sheets_sent,
            "last_24h": last_24h,
            "last_7d": last_7d,
            "average_per_day": avg_per_day,
            "telegram_sent_rate": round((telegram_sent / max(total_notifications, 1)) * 100, 2),
            "sheets_sent_rate": round((sheets_sent / max(total_notifications, 1)) * 100, 2)
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики уведомлений: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения статистики уведомлений")

@router.get("/parsing")
async def get_parsing_stats(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Статистика парсинга"""
    
    try:
        # Общее количество операций
        total_result = await db.execute(select(func.count(ParsingLog.id)))
        total_operations = total_result.scalar() or 0
        
        # По статусам
        success_result = await db.execute(
            select(func.count(ParsingLog.id)).where(ParsingLog.status == 'success')
        )
        success_count = success_result.scalar() or 0
        
        error_result = await db.execute(
            select(func.count(ParsingLog.id)).where(ParsingLog.status == 'error')
        )
        error_count = error_result.scalar() or 0
        
        warning_result = await db.execute(
            select(func.count(ParsingLog.id)).where(ParsingLog.status == 'warning')
        )
        warning_count = warning_result.scalar() or 0
        
        # По магазинам
        by_source_result = await db.execute(
            select(ParsingLog.source, func.count(ParsingLog.id))
            .group_by(ParsingLog.source)
        )
        by_source = dict(by_source_result.all())
        
        # Среднее время выполнения
        avg_time_result = await db.execute(
            select(func.avg(ParsingLog.execution_time)).where(ParsingLog.execution_time.isnot(None))
        )
        avg_execution_time = avg_time_result.scalar() or 0
        
        # Операции за последние 24 часа
        last_24h_result = await db.execute(
            select(func.count(ParsingLog.id)).where(
                ParsingLog.created_at >= datetime.now() - timedelta(hours=24)
            )
        )
        last_24h = last_24h_result.scalar() or 0
        
        return {
            "total_operations": total_operations,
            "successful": success_count,
            "errors": error_count,
            "warnings": warning_count,
            "by_source": by_source,
            "average_execution_time": round(avg_execution_time, 2),
            "last_24h": last_24h,
            "success_rate": round((success_count / max(total_operations, 1)) * 100, 2),
            "error_rate": round((error_count / max(total_operations, 1)) * 100, 2)
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики парсинга: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения статистики парсинга")
