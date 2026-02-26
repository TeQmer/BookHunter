"""API для управления шаблонами уведомлений"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from database.config import get_db
from models.notification_template import NotificationTemplate

router = APIRouter()


class TemplateCreate(BaseModel):
    """Схема для создания шаблона"""
    name: str
    title: Optional[str] = None
    message: str
    template_type: str
    description: Optional[str] = None
    placeholders: Optional[List[str]] = None


class TemplateUpdate(BaseModel):
    """Схема для обновления шаблона"""
    title: Optional[str] = None
    message: Optional[str] = None
    description: Optional[str] = None
    placeholders: Optional[List[str]] = None
    is_active: Optional[bool] = None


@router.get("")
async def get_templates(
    template_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db)
):
    """Получение списка шаблонов"""
    try:
        query = select(NotificationTemplate)
        
        if template_type:
            query = query.where(NotificationTemplate.template_type == template_type)
        if is_active is not None:
            query = query.where(NotificationTemplate.is_active == is_active)
        
        query = query.order_by(NotificationTemplate.template_type, NotificationTemplate.name)
        
        result = await db.execute(query)
        templates = result.scalars().all()
        
        return {
            "success": True,
            "templates": [
                {
                    "id": t.id,
                    "name": t.name,
                    "title": t.title,
                    "message": t.message,
                    "template_type": t.template_type,
                    "is_active": t.is_active,
                    "description": t.description,
                    "placeholders": t.get_placeholders_list()
                }
                for t in templates
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{template_id}")
async def get_template(
    template_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получение конкретного шаблона"""
    try:
        result = await db.execute(
            select(NotificationTemplate).where(NotificationTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        
        if not template:
            raise HTTPException(status_code=404, detail="Шаблон не найден")
        
        return {
            "success": True,
            "template": {
                "id": template.id,
                "name": template.name,
                "title": template.title,
                "message": template.message,
                "template_type": template.template_type,
                "is_active": template.is_active,
                "description": template.description,
                "placeholders": template.get_placeholders_list()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_template(
    template: TemplateCreate,
    db: AsyncSession = Depends(get_db)
):
    """Создание нового шаблона"""
    try:
        # Проверяем уникальность имени
        result = await db.execute(
            select(NotificationTemplate).where(NotificationTemplate.name == template.name)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(status_code=400, detail="Шаблон с таким именем уже существует")
        
        import json
        new_template = NotificationTemplate(
            name=template.name,
            title=template.title,
            message=template.message,
            template_type=template.template_type,
            description=template.description,
            placeholders=json.dumps(template.placeholders) if template.placeholders else None
        )
        db.add(new_template)
        await db.commit()
        
        return {
            "success": True,
            "message": "Шаблон создан",
            "template_id": new_template.id
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{template_id}")
async def update_template(
    template_id: int,
    template: TemplateUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Обновление шаблона"""
    try:
        result = await db.execute(
            select(NotificationTemplate).where(NotificationTemplate.id == template_id)
        )
        existing = result.scalar_one_or_none()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Шаблон не найден")
        
        if template.title is not None:
            existing.title = template.title
        if template.message is not None:
            existing.message = template.message
        if template.description is not None:
            existing.description = template.description
        if template.placeholders is not None:
            import json
            existing.placeholders = json.dumps(template.placeholders)
        if template.is_active is not None:
            existing.is_active = template.is_active
        
        existing.updated_at = datetime.utcnow()
        await db.commit()
        
        return {
            "success": True,
            "message": "Шаблон обновлён"
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Удаление шаблона"""
    try:
        result = await db.execute(
            select(NotificationTemplate).where(NotificationTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        
        if not template:
            raise HTTPException(status_code=404, detail="Шаблон не найден")
        
        await db.delete(template)
        await db.commit()
        
        return {
            "success": True,
            "message": "Шаблон удалён"
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
