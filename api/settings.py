"""API для управления настройками системы"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from typing import Optional, Any, Dict
from datetime import datetime

from database.config import get_db
from models.settings import Settings

router = APIRouter()


class SettingUpdate(BaseModel):
    """Схема для обновления настройки"""
    key: str
    value: str
    value_type: Optional[str] = 'string'
    description: Optional[str] = None


class SettingResponse(BaseModel):
    """Схема ответа настройки"""
    key: str
    value: Any
    value_type: str
    description: Optional[str]
    category: Optional[str]


@router.get("")
async def get_settings(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Получение всех настроек или настроек определённой категории"""
    try:
        query = select(Settings)
        if category:
            query = query.where(Settings.category == category)
        query = query.order_by(Settings.category, Settings.key)
        
        result = await db.execute(query)
        settings = result.scalars().all()
        
        return {
            "success": True,
            "settings": [
                {
                    "key": s.key,
                    "value": s.get_value(),
                    "value_type": s.value_type,
                    "description": s.description,
                    "category": s.category
                }
                for s in settings
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{key}")
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db)
):
    """Получение конкретной настройки"""
    try:
        result = await db.execute(
            select(Settings).where(Settings.key == key)
        )
        setting = result.scalar_one_or_none()
        
        if not setting:
            raise HTTPException(status_code=404, detail="Настройка не найдена")
        
        return {
            "success": True,
            "setting": {
                "key": setting.key,
                "value": setting.get_value(),
                "value_type": setting.value_type,
                "description": setting.description,
                "category": setting.category
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def update_setting(
    setting: SettingUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Создание или обновление настройки"""
    try:
        # Проверяем существует ли настройка
        result = await db.execute(
            select(Settings).where(Settings.key == setting.key)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Обновляем
            existing.value = setting.value
            existing.value_type = setting.value_type
            if setting.description:
                existing.description = setting.description
            existing.updated_at = datetime.utcnow()
        else:
            # Создаём новую
            new_setting = Settings(
                key=setting.key,
                value=setting.value,
                value_type=setting.value_type,
                description=setting.description
            )
            db.add(new_setting)
        
        await db.commit()
        
        return {
            "success": True,
            "message": f"Настройка '{setting.key}' обновлена"
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{key}")
async def delete_setting(
    key: str,
    db: AsyncSession = Depends(get_db)
):
    """Удаление настройки"""
    try:
        result = await db.execute(
            select(Settings).where(Settings.key == key)
        )
        setting = result.scalar_one_or_none()
        
        if not setting:
            raise HTTPException(status_code=404, detail="Настройка не найдена")
        
        await db.delete(setting)
        await db.commit()
        
        return {
            "success": True,
            "message": f"Настройка '{key}' удалена"
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
