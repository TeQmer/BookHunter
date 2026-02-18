#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API для работы с пользователями
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from database.config import get_db, get_session_factory
from models.user import User
from api.request_limits import RequestLimitChecker

router = APIRouter()

__all__ = ["router"]


@router.get("/stats")
async def get_user_stats(
    telegram_id: int = Query(..., description="ID пользователя в Telegram"),
    db: AsyncSession = Depends(get_db)
):
    """Получение статистики пользователя (задача #7)"""
    try:
        # Используем синхронную сессию для RequestLimitChecker
        SessionLocal = get_session_factory()
        sync_db = SessionLocal()

        try:
            stats = RequestLimitChecker.get_user_stats(sync_db, telegram_id)
        finally:
            sync_db.close()

        # Получаем дополнительную информацию о пользователе асинхронно
        result = await db.execute(select(User).filter(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()

        if user:
            stats.update({
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "display_name": user.display_name,
                "total_alerts": user.total_alerts,
                "notifications_sent": user.notifications_sent,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None
            })

        return {
            "success": True,
            "stats": stats
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики: {str(e)}")


@router.get("/info")
async def get_user_info(
    telegram_id: int = Query(..., description="ID пользователя в Telegram"),
    db: AsyncSession = Depends(get_db)
):
    """Получение информации о пользователе"""
    try:
        result = await db.execute(select(User).filter(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        return {
            "success": True,
            "user": user.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения информации о пользователе: {str(e)}")
