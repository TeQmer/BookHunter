#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API для работы с пользователями
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from database.config import get_db
from models.user import User
from api.request_limits import RequestLimitChecker

router = APIRouter()

__all__ = ["router"]


@router.get("/stats")
async def get_user_stats(
    telegram_id: int = Query(..., description="ID пользователя в Telegram"),
    db: Session = Depends(get_db)
):
    """Получение статистики пользователя (задача #7)"""
    try:
        stats = RequestLimitChecker.get_user_stats(db, telegram_id)

        # Получаем дополнительную информацию о пользователе
        user = db.query(User).filter(User.telegram_id == telegram_id).first()

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
    db: Session = Depends(get_db)
):
    """Получение информации о пользователе"""
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()

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
