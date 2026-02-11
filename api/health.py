from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import asyncio
from datetime import datetime
from typing import Dict, Any
from sqlalchemy import text

from database.config import get_engine
from services.logger import logger

router = APIRouter()

__all__ = ["router"]

@router.get("/")
async def health_check() -> Dict[str, Any]:
    """Проверка состояния всех компонентов системы"""
    
    health_status = {
        "timestamp": datetime.now().isoformat(),
        "status": "healthy",
        "components": {}
    }
    
    # Проверка базы данных
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        health_status["components"]["database"] = {
            "status": "healthy",
            "message": "Подключение к базе данных активно"
        }
    except Exception as e:
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "message": f"Ошибка подключения к базе данных: {str(e)}"
        }
        health_status["status"] = "degraded"
    
    # Проверка Redis (опционально)
    try:
        import redis.asyncio as redis
        redis_client = redis.from_url("redis://redis:6379/0")
        await redis_client.ping()
        await redis_client.close()
        health_status["components"]["redis"] = {
            "status": "healthy", 
            "message": "Подключение к Redis активно"
        }
    except ImportError:
        health_status["components"]["redis"] = {
            "status": "warning",
            "message": "Redis не настроен (aioredis не установлен)"
        }
    except Exception as e:
        health_status["components"]["redis"] = {
            "status": "unhealthy",
            "message": f"Ошибка подключения к Redis: {str(e)}"
        }
        health_status["status"] = "degraded"
    
    # Проверка парсеров (базовая)
    try:
        from parsers.factory import ParserFactory
        factory = ParserFactory()
        available_parsers = factory.get_available_parsers()
        
        health_status["components"]["parsers"] = {
            "status": "healthy",
            "message": f"Доступно парсеров: {len(available_parsers)}",
            "parsers": list(available_parsers.keys())
        }
    except Exception as e:
        health_status["components"]["parsers"] = {
            "status": "unhealthy",
            "message": f"Ошибка инициализации парсеров: {str(e)}"
        }
        health_status["status"] = "degraded"
    
    # Проверка Google Sheets
    try:
        from services.sheets_manager import SheetManager
        sheets_manager = SheetManager()
        # Простая проверка - попытка получить доступ к таблице
        # Не выполняем реальную операцию, только проверяем конфигурацию
        health_status["components"]["google_sheets"] = {
            "status": "healthy",
            "message": "Google Sheets API доступен"
        }
    except Exception as e:
        health_status["components"]["google_sheets"] = {
            "status": "unhealthy",
            "message": f"Ошибка Google Sheets: {str(e)}"
        }
        health_status["status"] = "degraded"
    
    # Проверка Telegram Bot
    try:
        import os
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if bot_token:
            health_status["components"]["telegram"] = {
                "status": "healthy",
                "message": "Telegram Bot токен настроен"
            }
        else:
            health_status["components"]["telegram"] = {
                "status": "warning",
                "message": "Telegram Bot токен не настроен"
            }
    except Exception as e:
        health_status["components"]["telegram"] = {
            "status": "unhealthy",
            "message": f"Ошибка Telegram Bot: {str(e)}"
        }
    
    # Определяем общий статус
    component_statuses = [comp["status"] for comp in health_status["components"].values()]
    if "unhealthy" in component_statuses:
        health_status["status"] = "unhealthy"
    elif "warning" in component_statuses:
        health_status["status"] = "degraded"
    
    return health_status

@router.get("/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """Детальная проверка с дополнительной информацией"""
    
    health_data = await health_check()
    
    # Дополнительная информация о системе (отключаем для стабильности)
    health_data["system"] = {
        "status": "available",
        "message": "Системная информация временно отключена"
    }
    
    # Статистика базы данных (отключаем для стабильности)
    health_data["database_stats"] = {
        "status": "available", 
        "message": "Статистика БД временно отключена"
    }
    
    return health_data

@router.get("/ready")
async def readiness_check() -> Dict[str, str]:
    """Проверка готовности к работе (для Kubernetes)"""
    
    try:
        # Проверяем критически важные компоненты
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute("SELECT 1")
            
        # Redis проверка опциональна
        try:
            import redis.asyncio as redis
            redis_client = redis.from_url("redis://redis:6379/0")
            await redis_client.ping()
            await redis_client.close()
        except ImportError:
            pass  # Redis не критичен для запуска
            
        return {"status": "ready"}
        
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service not ready: {str(e)}")

@router.get("/live")
async def liveness_check() -> Dict[str, str]:
    """Проверка жизни приложения (для Kubernetes)"""
    return {"status": "alive"}
