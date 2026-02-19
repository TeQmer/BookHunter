#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API для работы с пользователями
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Optional
from pydantic import BaseModel

from database.config import get_db, get_sync_db
from models.user import User
from api.request_limits import RequestLimitChecker

router = APIRouter()


class CreateUserRequest(BaseModel):
    """Модель запроса для создания пользователя"""
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


__all__ = ["router"]


@router.post("/create")
async def create_user(
    user_data: CreateUserRequest,
    db: AsyncSession = Depends(get_db)
):
    """Создание нового пользователя"""
    try:
        # Проверяем, существует ли пользователь
        result = await db.execute(select(User).filter(User.telegram_id == user_data.telegram_id))
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            return {
                "success": True,
                "message": "Пользователь уже существует",
                "user": existing_user.to_dict()
            }
        
        # Создаем нового пользователя
        new_user = User(
            telegram_id=user_data.telegram_id,
            username=user_data.username,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        return {
            "success": True,
            "message": "Пользователь создан",
            "user": new_user.to_dict()
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка создания пользователя: {str(e)}")


@router.get("/stats")
async def get_user_stats(
    telegram_id: int = Query(..., description="ID пользователя в Telegram"),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db)
):
    """Получение статистики пользователя (задача #7)"""
    try:
        # Получаем или создаем пользователя асинхронно
        result = await db.execute(select(User).filter(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()

        if not user:
            # Автоматически создаем пользователя если его нет
            user = User(
                telegram_id=telegram_id,
                first_name=f"User {telegram_id}",
                is_active=True,
                daily_requests_used=0,
                daily_requests_limit=15,
                requests_updated_at=datetime.utcnow()
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        # Используем синхронную сессию для RequestLimitChecker
        stats = RequestLimitChecker.get_user_stats(sync_db, telegram_id)

        # Обновляем статистику информацией о пользователе
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
