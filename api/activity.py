"""API для трекинга активности пользователей"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import uuid

from database.config import get_db
from models.user_activity import UserActivity

router = APIRouter()

# Хранилище активных сессий в памяти (для быстрого доступа)
# В продакшене лучше использовать Redis
active_sessions = {}  # {session_id: {"user_id": str, "started_at": datetime}}


class ActivityCreate(BaseModel):
    """Схема для создания записи активности"""
    user_id: str
    session_id: Optional[str] = None
    activity_type: str  # 'page_view', 'search', 'alert_created', 'alert_deleted', 'book_viewed', 'navigation'
    page: Optional[str] = None
    query: Optional[str] = None
    book_id: Optional[int] = None
    alert_id: Optional[int] = None
    duration_seconds: Optional[float] = None
    platform: Optional[str] = None


class SessionStart(BaseModel):
    """Схема для начала сессии"""
    user_id: str
    platform: Optional[str] = None


class SessionEnd(BaseModel):
    """Схема для окончания сессии"""
    user_id: str
    session_id: str
    duration_seconds: float


@router.post("/track")
async def track_activity(
    activity: ActivityCreate,
    db: AsyncSession = Depends(get_db)
):
    """Трекинг активности пользователя"""
    try:
        user_activity = UserActivity(
            user_id=activity.user_id,
            session_id=activity.session_id,
            activity_type=activity.activity_type,
            page=activity.page,
            query=activity.query,
            book_id=activity.book_id,
            alert_id=activity.alert_id,
            duration_seconds=activity.duration_seconds,
            platform=activity.platform
        )
        db.add(user_activity)
        await db.commit()
        
        return {"success": True, "activity_id": user_activity.id}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/start")
async def start_session(
    session: SessionStart,
    db: AsyncSession = Depends(get_db)
):
    """Начало сессии пользователя"""
    import uuid
    session_id = str(uuid.uuid4())
    
    user_activity = UserActivity(
        user_id=session.user_id,
        session_id=session_id,
        activity_type='session_start',
        platform=session.platform
    )
    db.add(user_activity)
    await db.commit()
    
    return {"success": True, "session_id": session_id}


@router.post("/session/end")
async def end_session(
    session: SessionEnd,
    db: AsyncSession = Depends(get_db)
):
    """Окончание сессии пользователя"""
    user_activity = UserActivity(
        user_id=session.user_id,
        session_id=session.session_id,
        activity_type='session_end',
        duration_seconds=session.duration_seconds
    )
    db.add(user_activity)
    await db.commit()
    
    return {"success": True}


@router.get("/stats")
async def get_activity_stats(
    days: int = 7,
    db: AsyncSession = Depends(get_db)
):
    """Получение статистики активности"""
    try:
        since = datetime.utcnow() - timedelta(days=days)
        
        # Всего уникальных пользователей
        unique_users = await db.execute(
            select(func.count(func.distinct(UserActivity.user_id)))
            .where(UserActivity.created_at >= since)
        )
        total_unique = unique_users.scalar() or 0
        
        # Всего сессий
        total_sessions = await db.execute(
            select(func.count(UserActivity.id))
            .where(UserActivity.created_at >= since)
        )
        total_activities = total_sessions.scalar() or 0
        
        # Средняя продолжительность сессии
        avg_duration = await db.execute(
            select(func.avg(UserActivity.duration_seconds))
            .where(
                UserActivity.created_at >= since,
                UserActivity.duration_seconds.isnot(None)
            )
        )
        avg_session_duration = avg_duration.scalar() or 0
        
        # Активность по дням
        daily_stats = await db.execute(
            select(
                func.date(UserActivity.created_at).label('date'),
                func.count(func.distinct(UserActivity.user_id)).label('unique_users'),
                func.count(UserActivity.id).label('total_activities')
            )
            .where(UserActivity.created_at >= since)
            .group_by(func.date(UserActivity.created_at))
            .order_by(desc('date'))
        )
        daily_data = [
            {
                "date": str(row.date),
                "unique_users": row.unique_users,
                "total_activities": row.total_activities
            }
            for row in daily_stats.fetchall()
        ]
        
        # Топ страниц
        top_pages = await db.execute(
            select(
                UserActivity.page,
                func.count(UserActivity.id).label('count')
            )
            .where(
                UserActivity.created_at >= since,
                UserActivity.page.isnot(None)
            )
            .group_by(UserActivity.page)
            .order_by(desc('count'))
            .limit(10)
        )
        pages_data = [
            {"page": row.page, "count": row.count}
            for row in top_pages.fetchall()
        ]
        
        return {
            "success": True,
            "stats": {
                "total_unique_users": total_unique,
                "total_activities": total_activities,
                "avg_session_duration_seconds": round(avg_session_duration, 1),
                "daily_stats": daily_data,
                "top_pages": pages_data
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== MINI APP SESSION TRACKING ==========

class MiniAppSessionStart(BaseModel):
    """Схема для начала сессии в Mini App"""
    user_id: str
    platform: Optional[str] = "telegram"


class MiniAppSessionEnd(BaseModel):
    """Схема для окончания сессии в Mini App"""
    user_id: str
    session_id: str
    duration_seconds: float


@router.post("/mini-app/session/start")
async def start_mini_app_session(
    session: MiniAppSessionStart,
    db: AsyncSession = Depends(get_db)
):
    """Начало сессии пользователя в Telegram Mini App"""
    try:
        session_id = str(uuid.uuid4())
        started_at = datetime.utcnow()
        
        # Сохраняем в памяти
        active_sessions[session_id] = {
            "user_id": session.user_id,
            "started_at": started_at,
            "platform": session.platform
        }
        
        # Записываем в БД
        user_activity = UserActivity(
            user_id=session.user_id,
            session_id=session_id,
            activity_type="mini_app_session_start",
            platform=session.platform,
            created_at=started_at
        )
        db.add(user_activity)
        await db.commit()
        
        return {
            "success": True, 
            "session_id": session_id,
            "started_at": started_at.isoformat()
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mini-app/session/end")
async def end_mini_app_session(
    session: MiniAppSessionEnd,
    db: AsyncSession = Depends(get_db)
):
    """Окончание сессии пользователя в Telegram Mini App"""
    try:
        # Удаляем из активных сессий
        session_data = active_sessions.pop(session.session_id, None)
        
        # Записываем окончание сессии в БД
        user_activity = UserActivity(
            user_id=session.user_id,
            session_id=session.session_id,
            activity_type="mini_app_session_end",
            duration_seconds=session.duration_seconds
        )
        db.add(user_activity)
        await db.commit()
        
        return {
            "success": True,
            "duration_seconds": session.duration_seconds
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mini-app/stats")
async def get_mini_app_stats(
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """Получение статистики использования Mini App"""
    try:
        since = datetime.utcnow() - timedelta(days=days)
        
        # Всего уникальных пользователей Mini App
        unique_users = await db.execute(
            select(func.count(func.distinct(UserActivity.user_id)))
            .where(
                UserActivity.activity_type.in_(["mini_app_session_start", "mini_app_session_end"]),
                UserActivity.created_at >= since
            )
        )
        total_unique = unique_users.scalar() or 0
        
        # Всего сессий
        total_sessions = await db.execute(
            select(func.count(UserActivity.id))
            .where(
                UserActivity.activity_type == "mini_app_session_end",
                UserActivity.created_at >= since
            )
        )
        sessions_count = total_sessions.scalar() or 0
        
        # Среднее время сессии
        avg_duration = await db.execute(
            select(func.avg(UserActivity.duration_seconds))
            .where(
                UserActivity.activity_type == "mini_app_session_end",
                UserActivity.created_at >= since,
                UserActivity.duration_seconds.isnot(None)
            )
        )
        avg_session_duration = avg_duration.scalar() or 0
        
        # Статистика по дням (для графиков)
        daily_stats = await db.execute(
            select(
                func.date(UserActivity.created_at).label('date'),
                func.count(func.distinct(UserActivity.user_id)).label('unique_users'),
                func.count(UserActivity.id).label('sessions'),
                func.avg(UserActivity.duration_seconds).label('avg_duration')
            )
            .where(
                UserActivity.activity_type == "mini_app_session_end",
                UserActivity.created_at >= since
            )
            .group_by(func.date(UserActivity.created_at))
            .order_by(desc('date'))
        )
        
        daily_data = []
        for row in daily_stats.fetchall():
            daily_data.append({
                "date": str(row.date) if row.date else None,
                "unique_users": row.unique_users or 0,
                "sessions": row.sessions or 0,
                "avg_duration_seconds": round(row.avg_duration or 0, 1),
                "avg_duration_minutes": round((row.avg_duration or 0) / 60, 1)
            })
        
        # Статистика по пользователям (топ по времени)
        user_stats = await db.execute(
            select(
                UserActivity.user_id,
                func.count(UserActivity.id).label('session_count'),
                func.avg(UserActivity.duration_seconds).label('avg_duration'),
                func.sum(UserActivity.duration_seconds).label('total_duration')
            )
            .where(
                UserActivity.activity_type == "mini_app_session_end",
                UserActivity.created_at >= since,
                UserActivity.duration_seconds.isnot(None)
            )
            .group_by(UserActivity.user_id)
            .order_by(desc('total_duration'))
            .limit(20)
        )
        
        top_users = []
        for row in user_stats.fetchall():
            top_users.append({
                "user_id": row.user_id,
                "session_count": row.session_count or 0,
                "avg_duration_seconds": round(row.avg_duration or 0, 1),
                "avg_duration_minutes": round((row.avg_duration or 0) / 60, 1),
                "total_duration_seconds": round(row.total_duration or 0, 1),
                "total_duration_minutes": round((row.total_duration or 0) / 60, 1)
            })
        
        return {
            "success": True,
            "stats": {
                "total_unique_users": total_unique,
                "total_sessions": sessions_count,
                "avg_session_duration_seconds": round(avg_session_duration, 1),
                "avg_session_duration_minutes": round(avg_session_duration / 60, 1),
                "daily_stats": daily_data,
                "top_users": top_users
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mini-app/user/{user_id}")
async def get_user_mini_app_stats(
    user_id: str,
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """Получение статистики Mini App для конкретного пользователя"""
    try:
        since = datetime.utcnow() - timedelta(days=days)
        
        # Количество сессий
        sessions_count = await db.execute(
            select(func.count(UserActivity.id))
            .where(
                UserActivity.user_id == str(user_id),
                UserActivity.activity_type == "mini_app_session_end",
                UserActivity.created_at >= since
            )
        )
        sessions = sessions_count.scalar() or 0
        
        # Общее время
        total_duration = await db.execute(
            select(func.sum(UserActivity.duration_seconds))
            .where(
                UserActivity.user_id == str(user_id),
                UserActivity.activity_type == "mini_app_session_end",
                UserActivity.created_at >= since,
                UserActivity.duration_seconds.isnot(None)
            )
        )
        total = total_duration.scalar() or 0
        
        # Среднее время
        avg_duration = await db.execute(
            select(func.avg(UserActivity.duration_seconds))
            .where(
                UserActivity.user_id == str(user_id),
                UserActivity.activity_type == "mini_app_session_end",
                UserActivity.created_at >= since,
                UserActivity.duration_seconds.isnot(None)
            )
        )
        avg = avg_duration.scalar() or 0
        
        return {
            "success": True,
            "user_id": user_id,
            "stats": {
                "total_sessions": sessions,
                "total_duration_seconds": round(total, 1),
                "total_duration_minutes": round(total / 60, 1),
                "avg_duration_seconds": round(avg, 1),
                "avg_duration_minutes": round(avg / 60, 1)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
