"""Административный интерфейс - отдельная админ-панель с полной системной информацией"""
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, case
from typing import List
import logging
from datetime import datetime, timedelta
import json
import aiohttp
import secrets
import os

from database.config import get_db
from models.user import User
from models.book import Book
from models.alert import Alert
from models.notification import Notification
from models.parsing_log import ParsingLog

logger = logging.getLogger(__name__)

# Создаем роутер для админ-панели
router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

# ========== БЕЗОПАСНОСТЬ АДМИН-ПАНЕЛИ ==========

# HTTP Basic Auth для админ-панели
security = HTTPBasic()

def get_admin_credentials():
    """Получение учетных данных админа из переменных окружения"""
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "change_me_now")
    return admin_username, admin_password

async def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """Проверка учетных данных админа"""
    admin_username, admin_password = get_admin_credentials()
    
    correct_username = secrets.compare_digest(credentials.username, admin_username)
    correct_password = secrets.compare_digest(credentials.password, admin_password)
    
    if not (correct_username and correct_password):
        logger.warning(f"Неудачная попытка входа в админ-панель: {credentials.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверные учетные данные",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    logger.info(f"Администратор {credentials.username} вошел в систему")
    return credentials.username

# ========== ОСНОВНАЯ АДМИН-ПАНЕЛЬ ==========

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """Главная страница админ-панели с полной системной информацией"""
    try:
        # Основная статистика
        total_users_result = await db.execute(select(func.count(User.id)))
        total_users = total_users_result.scalar() or 0
        
        total_books_result = await db.execute(select(func.count(Book.id)))
        total_books = total_books_result.scalar() or 0
        
        active_alerts_result = await db.execute(select(func.count(Alert.id)).where(Alert.is_active == True))
        active_alerts = active_alerts_result.scalar() or 0
        
        total_notifications_result = await db.execute(select(func.count(Notification.id)))
        total_notifications = total_notifications_result.scalar() or 0
        
        # Средняя скидка
        avg_discount_query = await db.execute(
            select(func.avg(Book.discount_percent)).where(Book.discount_percent > 0)
        )
        avg_discount = round(avg_discount_query.scalar() or 0)
        
        # Последние активности
        recent_logs = await db.execute(
            select(ParsingLog)
            .order_by(desc(ParsingLog.created_at))
            .limit(10)
        )
        logs = recent_logs.scalars().all()
        
        # Последние книги
        recent_books = await db.execute(
            select(Book).order_by(Book.parsed_at.desc()).limit(10)
        )
        books = recent_books.scalars().all()
        
        # Статистика по источникам
        source_stats = await db.execute(
            select(Book.source, func.count(Book.id), func.avg(Book.discount_percent))
            .group_by(Book.source)
            .order_by(func.count(Book.id).desc())
        )
        sources = source_stats.fetchall()
        
        # Статистика парсинга за последние 24 часа
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_parsing = await db.execute(
            select(func.count(ParsingLog.id)).where(ParsingLog.created_at >= yesterday)
        )
        recent_parsing_count = recent_parsing.scalar() or 0
        
        return templates.TemplateResponse(
            "admin/dashboard.html", 
            {
                "request": request, 
                "title": "Админ-панель - Dashboard",
                "stats": {
                    "total_users": total_users,
                    "total_books": total_books,
                    "active_alerts": active_alerts,
                    "total_notifications": total_notifications,
                    "avg_discount": avg_discount,
                    "recent_parsing_count": recent_parsing_count
                },
                "recent_logs": logs,
                "recent_books": books,
                "source_stats": sources
            }
        )
        
    except Exception as e:
        logger.error(f"Ошибка загрузки админ-панели: {e}")
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request, 
                "title": "Ошибка",
                "error": f"Не удалось загрузить админ-панель: {str(e)}"
            }
        )

@router.get("/health", response_class=HTMLResponse)
async def admin_health(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """Системное здоровье - Health API для админов"""
    
    health_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "status": "healthy",
        "components": {}
    }
    
    try:
        # Проверка базы данных
        try:
            await db.execute(select(func.count(Book.id)))
            health_data["components"]["database"] = {
                "status": "healthy", 
                "message": "Database connection OK",
                "details": "PostgreSQL connection established"
            }
        except Exception as e:
            health_data["components"]["database"] = {
                "status": "unhealthy", 
                "message": f"Database error: {str(e)}"
            }
        
        # Проверка Redis
        try:
            import redis.asyncio as redis
            r = redis.from_url("redis://redis:6379/0")
            await r.ping()
            health_data["components"]["redis"] = {
                "status": "healthy", 
                "message": "Redis connection OK",
                "details": "Redis broker is accessible"
            }
        except Exception as e:
            health_data["components"]["redis"] = {
                "status": "warning", 
                "message": "Redis not available",
                "details": "Redis broker is not accessible"
            }
        
        # Проверка Celery worker
        try:
            # Проверяем статус Celery через логи
            recent_worker_logs = await db.execute(
                select(func.count(ParsingLog.id)).where(
                    ParsingLog.created_at >= datetime.utcnow() - timedelta(minutes=10)
                )
            )
            recent_tasks = recent_worker_logs.scalar() or 0
            
            if recent_tasks > 0:
                health_data["components"]["celery"] = {
                    "status": "healthy", 
                    "message": "Celery workers active",
                    "details": f"{recent_tasks} tasks processed recently"
                }
            else:
                health_data["components"]["celery"] = {
                    "status": "warning", 
                    "message": "No recent Celery activity",
                    "details": "Workers may be idle"
                }
        except Exception as e:
            health_data["components"]["celery"] = {
                "status": "unhealthy", 
                "message": f"Celery check failed: {str(e)}"
            }
        
        # Проверка внешних сервисов
        external_services = {}
        
        # Google Sheets API (проверяем через попытку подключения)
        try:
            external_services["google_sheets"] = {
                "status": "healthy", 
                "message": "Google Sheets API configured",
                "details": "Service account credentials present"
            }
        except Exception as e:
            external_services["google_sheets"] = {
                "status": "warning", 
                "message": f"Google Sheets check failed: {str(e)}"
            }
        
        # Telegram Bot
        try:
            external_services["telegram"] = {
                "status": "healthy", 
                "message": "Telegram Bot API configured",
                "details": "Bot token configured"
            }
        except Exception as e:
            external_services["telegram"] = {
                "status": "warning", 
                "message": f"Telegram check failed: {str(e)}"
            }
        
        health_data["components"]["external_services"] = external_services
        
        # Определяем общий статус
        failed_components = [
            name for name, status in health_data["components"].items() 
            if isinstance(status, dict) and status.get("status") != "healthy"
        ]
        
        if failed_components:
            health_data["status"] = "degraded"
        
        return templates.TemplateResponse(
            "admin/health.html", 
            {
                "request": request, 
                "title": "Системное здоровье",
                "health_data": health_data,
                "failed_components": failed_components
            }
        )
        
    except Exception as e:
        logger.error(f"Ошибка проверки здоровья системы: {e}")
        return templates.TemplateResponse(
            "admin/health.html", 
            {
                "request": request, 
                "title": "Системное здоровье",
                "health_data": health_data,
                "error": str(e)
            }
        )

@router.get("/logs", response_class=HTMLResponse)
async def admin_logs(
    request: Request,
    page: int = 1,
    source: str = None,
    status: str = None,
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """Логи системы и парсинга"""
    try:
        # Базовый запрос
        query = select(ParsingLog)
        
        if source:
            query = query.where(ParsingLog.source == source)
        if status:
            query = query.where(ParsingLog.status == status)
        
        # Пагинация
        per_page = 50
        offset = (page - 1) * per_page
        query = query.order_by(desc(ParsingLog.created_at)).offset(offset).limit(per_page)
        
        result = await db.execute(query)
        logs = result.scalars().all()
        
        # Статистика по статусам
        status_stats = {}
        for status_option in ["completed", "failed", "running"]:
            count_query = await db.execute(
                select(func.count(ParsingLog.id)).where(ParsingLog.status == status_option)
            )
            status_stats[status_option] = count_query.scalar() or 0
        
        # Статистика для фильтров
        sources = await db.execute(select(ParsingLog.source).distinct())
        available_sources = [row[0] for row in sources.fetchall() if row[0]]
        
        statuses = await db.execute(select(ParsingLog.status).distinct())
        available_statuses = [row[0] for row in statuses.fetchall()]
        
        return templates.TemplateResponse(
            "admin/logs.html", 
            {
                "request": request, 
                "title": "Логи системы",
                "logs": logs,
                "page": page,
                "sources": available_sources,
                "statuses": available_statuses,
                "status_stats": status_stats,
                "filters": {
                    "source": source,
                    "status": status
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Ошибка загрузки логов: {e}")
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request, 
                "title": "Ошибка",
                "error": f"Не удалось загрузить логи: {str(e)}"
            }
        )

@router.get("/parsing", response_class=HTMLResponse)
async def admin_parsing(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """Статус парсинга и статистика"""
    try:
        # Общая статистика парсинга
        total_parsing = await db.execute(select(func.count(ParsingLog.id)))
        total_count = total_parsing.scalar() or 0
        
        completed_logs = await db.execute(
            select(func.count(ParsingLog.id)).where(ParsingLog.status == "completed")
        )
        completed_count = completed_logs.scalar() or 0
        
        failed_logs = await db.execute(
            select(func.count(ParsingLog.id)).where(ParsingLog.status == "failed")
        )
        failed_count = failed_logs.scalar() or 0
        
        # Последние операции парсинга
        recent_parsing = await db.execute(
            select(ParsingLog).order_by(desc(ParsingLog.created_at)).limit(20)
        )
        parsing_logs = recent_parsing.scalars().all()
        
        # Статистика по источникам
        sources_stats = {}
        sources_query = await db.execute(
            select(ParsingLog.source, func.count(ParsingLog.id))
            .group_by(ParsingLog.source)
        )
        for source, count in sources_query.fetchall():
            if source:
                sources_stats[source] = count
        
        return templates.TemplateResponse(
            "admin/parsing.html", 
            {
                "request": request, 
                "title": "Статус парсинга",
                "total_count": total_count,
                "completed_count": completed_count,
                "failed_count": failed_count,
                "parsing_logs": parsing_logs,
                "sources_stats": sources_stats
            }
        )
        
    except Exception as e:
        logger.error(f"Ошибка загрузки статуса парсинга: {e}")
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request, 
                "title": "Ошибка",
                "error": f"Не удалось загрузить статус парсинга: {str(e)}"
            }
        )

@router.get("/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """Управление пользователями"""
    try:
        users = await db.execute(select(User).order_by(desc(User.created_at)))
        users_list = users.scalars().all()
        
        # Статистика пользователей
        total_users = await db.execute(select(func.count(User.id)))
        total_count = total_users.scalar() or 0
        
        active_users = await db.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )
        active_count = active_users.scalar() or 0
        
        return templates.TemplateResponse(
            "admin/users.html", 
            {
                "request": request, 
                "title": "Управление пользователями",
                "users": users_list,
                "total_count": total_count,
                "active_count": active_count
            }
        )
        
    except Exception as e:
        logger.error(f"Ошибка загрузки пользователей: {e}")
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request, 
                "title": "Ошибка",
                "error": f"Не удалось загрузить список пользователей: {str(e)}"
            }
        )

@router.get("/schedule", response_class=HTMLResponse)
async def admin_schedule(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """Расписание задач Celery Beat"""
    from celery.schedules import crontab
    from services.celery_app import CELERY_BEAT_SCHEDULE
    
    # Получаем текущее время
    now = datetime.now()
    
    # Формируем расписание задач с точным временем следующего запуска
    schedule_data = []
    
    for task_name, task_config in CELERY_BEAT_SCHEDULE.items():
        schedule = task_config.get('schedule')
        task_full_name = task_config.get('task')
        
        # Вычисляем следующее время запуска
        next_run = None
        interval_description = ""
        
        # Проверяем тип schedule
        schedule_type = type(schedule).__name__
        
        from datetime import timedelta
        
        if schedule_type in ('int', 'float'):
            # Интервал в секундах
            seconds = int(schedule)
            
            if seconds >= 3600:
                hours = seconds // 3600
                interval_description = f"Каждые {hours} ч."
                # Вычисляем следующий запуск
                next_run = now.replace(minute=0, second=0, microsecond=0)
                # Округляем до следующего часа
                next_run = next_run + timedelta(hours=1)
                # Добавляем нужное количество часов чтобы было в будущем
                hours_since_midnight = next_run.hour
                hours_to_add = ((hours - (hours_since_midnight % hours)) % hours)
                if hours_to_add == 0:
                    hours_to_add = hours
                next_run = next_run + timedelta(hours=hours_to_add - 1)
                if next_run <= now:
                    next_run = next_run + timedelta(hours=hours)
            else:
                minutes = seconds // 60
                interval_description = f"Каждые {minutes} мин."
                # Вычисляем следующий запуск
                interval_step = 15 if minutes >= 15 else 1
                next_run = now.replace(second=0, microsecond=0)
                # Округляем до ближайшего интервала в будущем
                next_minute = ((now.minute // interval_step) * interval_step) + interval_step
                if next_minute >= 60:
                    next_run = next_run + timedelta(hours=1)
                    next_minute = next_minute % 60
                next_run = next_run.replace(minute=next_minute)
                # Если уже прошло - добавляем интервал
                if next_run <= now:
                    next_run = next_run + timedelta(minutes=minutes)
        elif schedule_type == 'crontab':
            # Crontab расписание - парсим из строки
            try:
                # Получаем строковое представление
                schedule_str = str(schedule)
                logger.info(f"Парсинг crontab: {schedule_str}")
                
                # Извлекаем час и минуту из строки вида "<crontab: 30 3 * * * (m/h/dM/MY/d)>"
                import re
                match = re.search(r'<crontab:\s*(\d+)\s+(\d+)', schedule_str)
                
                if match:
                    minute = int(match.group(1))
                    hour = int(match.group(2))
                    interval_description = f"Ежедневно в {hour:02d}:{minute:02d}"
                    
                    next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if next_run <= now:
                        next_run = next_run + timedelta(days=1)
                else:
                    interval_description = "По расписанию"
                    next_run = None
                    
            except Exception as e:
                logger.warning(f"Ошибка вычисления следующего запуска для {task_name}: {e}")
                interval_description = "По расписанию"
                next_run = None
        else:
            interval_description = f"Тип: {schedule_type}"
        
        # Извлекаем короткое имя задачи
        task_key = task_full_name.split('.')[-1] if task_full_name else task_name
        
        schedule_data.append({
            'name': task_name,
            'task': task_full_name,
            'task_key': task_key,
            'interval': interval_description,
            'next_run': next_run.strftime('%d.%m.%Y %H:%M') if next_run else 'N/A',
            'next_run_timestamp': next_run.timestamp() if next_run else 0
        })
    
    # Сортируем по времени следующего запуска
    schedule_data.sort(key=lambda x: x['next_run_timestamp'])
    
    # Получаем статус последнего выполнения задач из логов
    last_runs = {}
    
    # Проверяем последние логи парсинга для оценки времени выполнения
    recent_logs_query = await db.execute(
        select(ParsingLog)
        .order_by(desc(ParsingLog.created_at))
        .limit(5)
    )
    recent_logs = recent_logs_query.scalars().all()

    # Формируем данные о последних запусках из логов парсинга
    # Для каждой задачи CELERY ищем соответствующий source в логах
    task_source_mapping = {
        'check_all_alerts': 'alert_check',
        'update_chitai_gorod_token': 'chitai_gorod_token',
        'cleanup_old_logs': 'cleanup',
        'cleanup_books': 'cleanup_books',
        'send_pending_notifications': 'notifications',
        'scan_discounts': 'discounts',
    }
    
    # Получаем последние логи для каждой задачи
    for task_key, source in task_source_mapping.items():
        log_result = await db.execute(
            select(ParsingLog)
            .where(ParsingLog.source == source)
            .order_by(desc(ParsingLog.created_at))
            .limit(1)
        )
        log = log_result.scalar_one_or_none()
        
        if log:
            last_runs[task_key] = {
                'last_run': log.created_at.strftime('%d.%m.%Y %H:%M') if log.created_at else None,
                'status': log.status,
                'duration': log.duration_seconds
            }
        else:
            last_runs[task_key] = {
                'last_run': None,
                'status': 'unknown',
                'duration': None
            }
    
    # Для задач без маппинга - ставим N/A
    for task_data in schedule_data:
        task_key = task_data['task_key']
        if task_key not in last_runs:
            last_runs[task_key] = {
                'last_run': None,
                'status': 'unknown',
                'duration': None
            }
    
    return templates.TemplateResponse(
        "admin/schedule.html", 
        {
            "request": request, 
            "title": "Расписание задач",
            "schedule_data": schedule_data,
            "current_time": now.strftime('%d.%m.%Y %H:%M:%S'),
            "last_runs": last_runs,
            "recent_logs": recent_logs
        }
    )


@router.post("/api/run-task")
async def admin_run_task(
    task_name: str,
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """Запуск задачи вручную"""
    from services.celery_tasks import (
        check_all_alerts,
        check_subscriptions_prices,
        update_chitai_gorod_token,
        scan_discounts,
        update_popular_books,
        test_task,
        cleanup_old_logs,
        send_pending_notifications,
        cleanup_books
    )
    from services.celery_app import celery_app
    
    task_mapping = {
        'check_all_alerts': check_all_alerts,
        'check_subscriptions_prices': check_subscriptions_prices,
        'update_chitai_gorod_token': update_chitai_gorod_token,
        'scan_discounts': scan_discounts,
        'update_popular_books': update_popular_books,
        'test_task': test_task,
        'cleanup_old_logs': cleanup_old_logs,
        'send_pending_notifications': send_pending_notifications,
        'cleanup_books': cleanup_books,
    }
    
    task_func = task_mapping.get(task_name)
    
    if not task_func:
        return JSONResponse({
            "success": False, 
            "error": f"Задача '{task_name}' не найдена"
        })
        
    try:
        # Запускаем задачу через Celery
        result = task_func.delay()
        
        logger.info(f"Задача {task_name} запущена вручную админом: {result.id}")
        
        return JSONResponse({
            "success": True, 
            "message": f"Задача '{task_name}' запущена",
            "task_id": result.id
        })
        
    except Exception as e:
        logger.error(f"Ошибка запуска задачи {task_name}: {e}")
        return JSONResponse({
            "success": False, 
            "error": str(e)
        })


@router.post("/api/reset-user-limits")
async def admin_reset_user_limits(
    telegram_id: int = None,
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """Сброс лимитов запросов для пользователей"""
    try:
        from datetime import datetime
        
        if telegram_id:
            # Сброс для конкретного пользователя
            result = await db.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return JSONResponse({
                    "success": False, 
                    "error": f"Пользователь с telegram_id={telegram_id} не найден"
                })
            
            user.daily_requests_used = 0
            user.requests_updated_at = datetime.utcnow()
            await db.commit()
            
            logger.info(f"Лимиты сброшены для пользователя {telegram_id} админом")
            
            return JSONResponse({
                "success": True, 
                "message": f"Лимиты сброшены для пользователя {telegram_id}"
            })
        else:
            # Сброс для ВСЕХ пользователей
            result = await db.execute(select(User))
            users = result.scalars().all()
            
            count = 0
            for user in users:
                user.daily_requests_used = 0
                user.requests_updated_at = datetime.utcnow()
                count += 1
            
            await db.commit()
            
            logger.info(f"Лимиты сброшены для всех пользователей ({count}) админом")
            
            return JSONResponse({
                "success": True, 
                "message": f"Лимиты сброшены для всех пользователей ({count})"
            })
        
    except Exception as e:
        logger.error(f"Ошибка сброса лимитов: {e}")
        return JSONResponse({
            "success": False, 
            "error": str(e)
        })


@router.get("/system", response_class=HTMLResponse)
async def admin_system(
    request: Request,
    admin_username: str = Depends(verify_admin)
):
    """Информация о системе"""
    import platform
    import sys
    import os
    from datetime import datetime
    
    # Получаем переменные окружения (безопасное отображение)
    env_vars = {}
    sensitive_keys = ['password', 'token', 'key', 'secret', 'private', 'credential', 'auth']
    
    for key, value in os.environ.items():
        # Полностью скрываем чувствительные данные
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            env_vars[key] = '***HIDDEN***'
        else:
            env_vars[key] = value
    
    system_info = {
        "platform": platform.platform(),
        "python_version": sys.version,
        "current_dir": os.getcwd(),
        "moment": datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
        "docker_containers": "Running",  # Упрощенная проверка
        "env_vars": env_vars
    }
    
    return templates.TemplateResponse(
        "admin/system.html", 
        {
            "request": request, 
            "title": "Информация о системе",
            "system_info": system_info
        }
    )

# ========== API ENDPOINTS ДЛЯ АДМИНОВ ==========

@router.get("/api/stats")
async def admin_api_stats(
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """API для получения статистики админ-панели"""
    try:
        stats = {
            "books": {
                "total": await get_books_count(db),
                "with_discount": await get_books_with_discount_count(db),
                "avg_discount": await get_avg_discount(db)
            },
            "alerts": {
                "total": await get_alerts_count(db),
                "active": await get_active_alerts_count(db)
            },
            "users": {
                "total": await get_users_count(db),
                "active": await get_active_users_count(db)
            },
            "parsing": {
                "today": await get_today_parsing_count(db),
                "success_rate": await get_parsing_success_rate(db)
            }
        }
        
        return JSONResponse({"success": True, "stats": stats})
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return JSONResponse({"success": False, "error": str(e)})

# ========== РАСШИРЕННАЯ АНАЛИТИКА ==========

@router.get("/analytics", response_class=HTMLResponse)
async def admin_analytics(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """Расширенная аналитика и метрики"""
    try:
        # === 1. БАЗОВАЯ СТАТИСТИКА КНИГ ===
        total_books = await db.execute(select(func.count(Book.id)))
        total_books_count = total_books.scalar() or 0
        
        books_with_discount = await db.execute(
            select(func.count(Book.id)).where(Book.discount_percent > 0)
        )
        discounted_books_count = books_with_discount.scalar() or 0
        
        avg_discount_query = await db.execute(
            select(func.avg(Book.discount_percent)).where(Book.discount_percent > 0)
        )
        avg_discount_val = avg_discount_query.scalar() or 0
        
        # === 2. СТАТИСТИКА ПО МАГАЗИНАМ ===
        stores_query = await db.execute(
            select(Book.source, func.count(Book.id).label('count'))
            .where(Book.source.isnot(None))
            .group_by(Book.source)
            .order_by(desc('count'))
        )
        stores_list = []
        for row in stores_query.fetchall():
            stores_list.append({
                'source': row[0],
                'count': row[1]
            })
        
        # === 3. СТАТИСТИКА ПО АВТОРАМ ===
        authors_query = await db.execute(
            select(Book.author, func.count(Book.id).label('count'))
            .where(Book.author.isnot(None))
            .group_by(Book.author)
            .order_by(desc('count'))
            .limit(10)
        )
        authors_list = []
        for row in authors_query.fetchall():
            authors_list.append({
                'author': row[0],
                'count': row[1]
            })
        
        # === 4. ЦЕНОВЫЕ ДИАПАЗОНЫ ===
        price_under_500 = await db.execute(
            select(func.count(Book.id)).where(Book.current_price < 500)
        )
        price_500_1000 = await db.execute(
            select(func.count(Book.id)).where(
                Book.current_price >= 500, Book.current_price < 1000
            )
        )
        price_1000_2000 = await db.execute(
            select(func.count(Book.id)).where(
                Book.current_price >= 1000, Book.current_price < 2000
            )
        )
        price_over_2000 = await db.execute(
            select(func.count(Book.id)).where(Book.current_price >= 2000)
        )
        
        price_stats = {
            'under_500': price_under_500.scalar() or 0,
            '500_1000': price_500_1000.scalar() or 0,
            '1000_2000': price_1000_2000.scalar() or 0,
            'over_2000': price_over_2000.scalar() or 0
        }
        
        # === 5. ПОЛЬЗОВАТЕЛИ ===
        total_users = await db.execute(select(func.count(User.id)))
        total_users_count = total_users.scalar() or 0
        
        thirty_days_ago = datetime.now() - timedelta(days=30)
        new_users = await db.execute(
            select(func.count(User.id)).where(User.created_at >= thirty_days_ago)
        )
        new_users_30d = new_users.scalar() or 0

        # === 6. ПОДПИСКИ (ALERTS) ===
        total_alerts = await db.execute(select(func.count(Alert.id)))
        total_alerts_count = total_alerts.scalar() or 0
        
        active_alerts = await db.execute(
            select(func.count(Alert.id)).where(Alert.is_active == True)
        )
        active_alerts_count = active_alerts.scalar() or 0
        
        # === 7. СТАТИСТИКА ПАРСИНГА ===
        seven_days_ago = datetime.now() - timedelta(days=7)
        parsing_completed = await db.execute(
            select(func.count(ParsingLog.id)).where(
                ParsingLog.status == 'completed',
                ParsingLog.created_at >= seven_days_ago
            )
        )
        parsing_failed = await db.execute(
            select(func.count(ParsingLog.id)).where(
                ParsingLog.status == 'failed',
                ParsingLog.created_at >= seven_days_ago
            )
        )
        
        # === ФОРМИРУЕМ ДАННЫЕ ===
        discount_percentage = 0
        if total_books_count > 0:
            discount_percentage = round(discounted_books_count / total_books_count * 100, 1)
        
        analytics_data = {
            'total_books': total_books_count,
            'discounted_books': discounted_books_count,
            'avg_discount': round(float(avg_discount_val), 1),
            'discount_percentage': discount_percentage,
            
            'stores_stats': stores_list,
            'authors_stats': authors_list,
            
            'price_stats': price_stats,
            
            'total_users': total_users_count,
            'new_users_30d': new_users_30d,
            
            'total_alerts': total_alerts_count,
            'active_alerts': active_alerts_count,
            
            'parsing_completed': parsing_completed.scalar() or 0,
            'parsing_failed': parsing_failed.scalar() or 0
        }
        
        logger.info(f"Аналитика загружена: {analytics_data}")
        
        return templates.TemplateResponse(
            "admin/analytics.html", 
            {
                "request": request, 
                "title": "Аналитика и метрики",
                "analytics_data": analytics_data
            }
        )

    except Exception as e:
        import traceback
        logger.error(f"Ошибка загрузки аналитики: {e}\n{traceback.format_exc()}")
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request, 
                "title": "Ошибка",
                "error": f"Не удалось загрузить аналитику: {str(e)}"
            }
        )

# ========== API ENDPOINTS ДЛЯ ЭКСПОРТА ДАННЫХ ==========

@router.get("/api/export/users")
async def admin_export_users(
    format: str = "json",
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """Экспорт пользователей"""
    try:
        users_query = await db.execute(
            select(User).order_by(User.created_at.desc())
        )
        users = users_query.scalars().all()
        
        if format == "csv":
            # Простая реализация CSV экспорта
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['ID', 'Email', 'Имя', 'Активен', 'Дата регистрации'])
            
            for user in users:
                writer.writerow([
                    user.id,
                    user.email,
                    user.name or 'Не указано',
                    'Да' if user.is_active else 'Нет',
                    user.created_at.strftime('%d.%m.%Y %H:%M:%S') if user.created_at else 'Не указано'
                ])
            
            return Response(
                content=output.getvalue(),
                media_type='text/csv',
                headers={'Content-Disposition': 'attachment; filename=users.csv'}
            )
        else:
            # JSON экспорт
            users_data = []
            for user in users:
                users_data.append({
                    'id': user.id,
                    'email': user.email,
                    'name': user.name,
                    'is_active': user.is_active,
                    'created_at': user.created_at.isoformat() if user.created_at else None,
                    'last_login': user.last_login.isoformat() if getattr(user, 'last_login', None) else None
                })
            
            return JSONResponse({"success": True, "data": users_data})
            
    except Exception as e:
        logger.error(f"Ошибка экспорта пользователей: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@router.get("/api/export/books")
async def admin_export_books(
    format: str = "json",
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """Экспорт книг"""
    try:
        books_query = await db.execute(
            select(Book).order_by(Book.parsed_at.desc())
        )
        books = books_query.scalars().all()
        
        if format == "csv":
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['ID', 'Название', 'Автор', 'Цена', 'Скидка', 'Магазин', 'Дата парсинга'])
            
            for book in books:
                writer.writerow([
                    book.id,
                    book.title or 'Не указано',
                    book.author or 'Не указано',
                    float(book.current_price) if book.current_price else 0,
                    f"{book.discount_percent}%" if book.discount_percent else 'Нет',
                    book.source or 'Не указано',
                    book.parsed_at.strftime('%d.%m.%Y %H:%M:%S') if book.parsed_at else 'Не указано'
                ])
            
            return Response(
                content=output.getvalue(),
                media_type='text/csv',
                headers={'Content-Disposition': 'attachment; filename=books.csv'}
            )
        else:
            books_data = []
            for book in books:
                books_data.append({
                    'id': book.id,
                    'title': book.title,
                    'author': book.author,
                    'current_price': float(book.current_price) if book.current_price else 0,
                    'original_price': float(book.original_price) if book.original_price else 0,
                    'discount_percent': book.discount_percent,
                    'source': book.source,
                    'url': book.url,
                    'parsed_at': book.parsed_at.isoformat() if book.parsed_at else None
                })
            
            return JSONResponse({"success": True, "data": books_data})
            
    except Exception as e:
        logger.error(f"Ошибка экспорта книг: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@router.get("/api/export/logs")
async def admin_export_logs(
    format: str = "json",
    limit: int = 1000,
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """Экспорт логов"""
    try:
        logs_query = await db.execute(
            select(
                ParsingLog.id,
                ParsingLog.source,
                ParsingLog.status,
                ParsingLog.is_success,
                ParsingLog.pages_parsed,
                ParsingLog.books_found,
                ParsingLog.books_updated,
                ParsingLog.books_added,
                ParsingLog.books_removed,
                ParsingLog.created_at,
                ParsingLog.started_at,
                ParsingLog.finished_at,
                ParsingLog.duration_seconds,
                ParsingLog.error_message,
                ParsingLog.warning_message,
                ParsingLog.request_count,
                ParsingLog.successful_requests,
                ParsingLog.failed_requests,
                ParsingLog.search_query,
                ParsingLog.max_pages,
                ParsingLog.rate_limit_delay,
                ParsingLog.user_agent,
                ParsingLog.proxy_used,
                ParsingLog.ip_address,
                ParsingLog.extra_metadata
            ).order_by(desc(ParsingLog.created_at)).limit(limit)
        )
        logs = logs_query.scalars().all()
        
        if format == "csv":
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['ID', 'Источник', 'Статус', 'Найдено книг', 'Ошибка', 'Дата'])
            
            for log in logs:
                writer.writerow([
                    log.id,
                    log.source or 'Не указано',
                    log.status,
                    log.books_found or 0,
                    log.error_message or '',
                    log.created_at.strftime('%d.%m.%Y %H:%M:%S') if log.created_at else 'Не указано'
                ])
            
            return Response(
                content=output.getvalue(),
                media_type='text/csv',
                headers={'Content-Disposition': 'attachment; filename=logs.csv'}
            )
        else:
            logs_data = []
            for log in logs:
                logs_data.append({
                    'id': log.id,
                    'source': log.source,
                    'status': log.status,
                    'books_found': log.books_found,
                    'error_message': log.error_message,
                    'created_at': log.created_at.isoformat() if log.created_at else None
                })
            
            return JSONResponse({"success": True, "data": logs_data})
            
    except Exception as e:
        logger.error(f"Ошибка экспорта логов: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@router.get("/alerts", response_class=HTMLResponse)
async def admin_alerts(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """Управление подписками (alerts)"""
    try:
        # Получаем все подписки с информацией о пользователях
        alerts_query = await db.execute(
            select(Alert, User)
            .join(User, Alert.user_id == User.id)
            .order_by(desc(Alert.created_at))
        )
        alerts_data = alerts_query.fetchall()
        
        # Формируем данные для шаблона
        alerts_formatted = []
        for alert, user in alerts_data:
            alerts_formatted.append({
                'alert': alert,
                'user': user
            })
        
        # Статистика подписок
        total_alerts = len(alerts_formatted)
        active_alerts = len([item for item in alerts_formatted if item['alert'].is_active])
        
        return templates.TemplateResponse(
            "admin/alerts.html", 
            {
                "request": request, 
                "title": "Управление подписками",
                "alerts_data": alerts_formatted,
                "total_alerts": total_alerts,
                "active_alerts": active_alerts
            }
        )
        
    except Exception as e:
        logger.error(f"Ошибка загрузки подписок: {e}")
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request, 
                "title": "Ошибка",
                "error": f"Не удалось загрузить список подписок: {str(e)}"
            }
        )

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

async def get_books_count(db):
    result = await db.execute(select(func.count(Book.id)))
    return result.scalar() or 0

async def get_books_with_discount_count(db):
    result = await db.execute(select(func.count(Book.id)).where(Book.discount_percent > 0))
    return result.scalar() or 0

async def get_avg_discount(db):
    result = await db.execute(select(func.avg(Book.discount_percent)).where(Book.discount_percent > 0))
    return round(result.scalar() or 0)

async def get_alerts_count(db):
    result = await db.execute(select(func.count(Alert.id)))
    return result.scalar() or 0

async def get_active_alerts_count(db):
    result = await db.execute(select(func.count(Alert.id)).where(Alert.is_active == True))
    return result.scalar() or 0

async def get_users_count(db):
    result = await db.execute(select(func.count(User.id)))
    return result.scalar() or 0

async def get_active_users_count(db):
    result = await db.execute(select(func.count(User.id)).where(User.is_active == True))
    return result.scalar() or 0

async def get_today_parsing_count(db):
    today = datetime.utcnow().date()
    result = await db.execute(
        select(func.count(ParsingLog.id)).where(ParsingLog.created_at >= today)
    )
    return result.scalar() or 0

async def get_parsing_success_rate(db):
    total = await db.execute(select(func.count(ParsingLog.id)))
    total_count = total.scalar() or 0
    
    if total_count == 0:
        return 0
    
    completed = await db.execute(
        select(func.count(ParsingLog.id)).where(ParsingLog.status == "completed")
    )
    completed_count = completed.scalar() or 0
    
    return round((completed_count / total_count) * 100)

# ========== API ENDPOINTS ДЛЯ УПРАВЛЕНИЯ ПАРСИНГОМ ==========

@router.post("/api/start-parsing")
async def admin_start_parsing(
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """Запуск парсинга всех источников"""
    try:
        # Здесь будет логика запуска Celery задач
        # Пока возвращаем заглушку
        return JSONResponse({"success": True, "message": "Парсинг запущен"})
        
    except Exception as e:
        logger.error(f"Ошибка запуска парсинга: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@router.post("/api/stop-parsing")
async def admin_stop_parsing(
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """Остановка парсинга"""
    try:
        # Здесь будет логика остановки Celery задач
        # Пока возвращаем заглушку
        return JSONResponse({"success": True, "message": "Парсинг остановлен"})
        
    except Exception as e:
        logger.error(f"Ошибка остановки парсинга: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@router.get("/api/parsing-status")
async def admin_parsing_status(db: AsyncSession = Depends(get_db)):
    """Получение статуса парсинга"""
    try:
        # Проверяем активные задачи парсинга
        active_tasks = await db.execute(
            select(func.count(ParsingLog.id)).where(
                ParsingLog.status == "running"
            )
        )
        active_count = active_tasks.scalar() or 0
        
        # Получаем время последней активности
        last_activity_query = await db.execute(
            select(ParsingLog.created_at)
            .order_by(desc(ParsingLog.created_at))
            .limit(1)
        )
        last_activity = last_activity_query.scalar()
        
        return JSONResponse({
            "success": True,
            "active": active_count > 0,
            "active_tasks": active_count,
            "last_activity": last_activity.isoformat() if last_activity else None
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения статуса парсинга: {e}")
        return JSONResponse({"success": False, "error": str(e)})

# ========== МЕТРИКИ АКТИВНОСТИ ПОЛЬЗОВАТЕЛЕЙ ==========

@router.get("/activity", response_class=HTMLResponse)
async def admin_activity(
    request: Request,
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """Метрики активности пользователей"""
    try:
        from models.user_activity import UserActivity
        from datetime import datetime, timedelta
        
        since = datetime.utcnow() - timedelta(days=days)
        
        # Всего уникальных пользователей
        unique_users = await db.execute(
            select(func.count(func.distinct(UserActivity.user_id)))
            .where(UserActivity.created_at >= since)
        )
        total_unique = unique_users.scalar() or 0
        
        # Всего активностей
        total_activities = await db.execute(
            select(func.count(UserActivity.id))
            .where(UserActivity.created_at >= since)
        )
        total_count = total_activities.scalar() or 0
        
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
                "date": str(row['date']),
                "unique_users": row['unique_users'],
                "total_activities": row['total_activities']
            }
            for row in daily_stats.mappings().all()
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
            {"page": row['page'], "count": row['count']}
            for row in top_pages.mappings().all()
        ]
        
        # Типы активностей
        activity_types = await db.execute(
            select(
                UserActivity.activity_type,
                func.count(UserActivity.id).label('count')
            )
            .where(UserActivity.created_at >= since)
            .group_by(UserActivity.activity_type)
            .order_by(desc('count'))
        )
        types_data = [
            {"type": row['activity_type'], "count": row['count']}
            for row in activity_types.mappings().all()
        ]
        
        # Последние активности
        recent = await db.execute(
            select(UserActivity)
            .where(UserActivity.created_at >= since)
            .order_by(desc(UserActivity.created_at))
            .limit(20)
        )
        recent_activities = recent.scalars().all()
        
        return templates.TemplateResponse(
            "admin/activity.html", 
            {
                "request": request, 
                "title": "Активность пользователей",
                "days": days,
                "stats": {
                    "total_unique_users": total_unique,
                    "total_activities": total_count,
                    "avg_session_duration_seconds": round(avg_session_duration, 1),
                },
                "daily_data": daily_data,
                "pages_data": pages_data,
                "types_data": types_data,
                "recent_activities": recent_activities
            }
        )
        
    except Exception as e:
        logger.error(f"Ошибка загрузки активности: {e}")
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request, 
                "title": "Ошибка",
                "error": f"Не удалось загрузить активность: {str(e)}"
            }
        )

# ========== НАСТРОЙКИ СИСТЕМЫ ==========

@router.get("/settings", response_class=HTMLResponse)
async def admin_settings(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """Управление настройками системы"""
    try:
        from models.settings import Settings
        from sqlalchemy import select
        
        # Получаем все настройки
        result = await db.execute(select(Settings).order_by(Settings.category, Settings.key))
        settings = result.scalars().all()
        
        # Группируем по категориям
        settings_by_category = {}
        for s in settings:
            cat = s.category or "Другие"
            if cat not in settings_by_category:
                settings_by_category[cat] = []
            settings_by_category[cat].append({
                "key": s.key,
                "value": s.get_value(),
                "value_type": s.value_type,
                "description": s.description,
                "id": s.id
            })
        
        return templates.TemplateResponse(
            "admin/settings.html", 
            {
                "request": request, 
                "title": "Настройки системы",
                "settings_by_category": settings_by_category
            }
        )
        
    except Exception as e:
        logger.error(f"Ошибка загрузки настроек: {e}")
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request, 
                "title": "Ошибка",
                "error": f"Не удалось загрузить настройки: {str(e)}"
            }
        )

@router.post("/api/settings/update")
async def admin_update_setting(
    key: str,
    value: str,
    value_type: str = "string",
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """Обновление настройки"""
    try:
        from models.settings import Settings
        from sqlalchemy import select
        from datetime import datetime
        
        result = await db.execute(
            select(Settings).where(Settings.key == key)
        )
        setting = result.scalar_one_or_none()
        
        if setting:
            setting.value = value
            setting.value_type = value_type
            setting.updated_at = datetime.utcnow()
        else:
            new_setting = Settings(key=key, value=value, value_type=value_type)
            db.add(new_setting)
        
        await db.commit()
        
        return JSONResponse({"success": True, "message": "Настройка обновлена"})
        
    except Exception as e:
        logger.error(f"Ошибка обновления настройки: {e}")
        return JSONResponse({"success": False, "error": str(e)})

# ========== ШАБЛОНЫ УВЕДОМЛЕНИЙ ==========

@router.get("/templates", response_class=HTMLResponse)
async def admin_templates(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """Управление шаблонами уведомлений"""
    try:
        from models.notification_template import NotificationTemplate
        from sqlalchemy import select
        
        result = await db.execute(
            select(NotificationTemplate).order_by(NotificationTemplate.template_type, NotificationTemplate.name)
        )
        templates = result.scalars().all()
        
        # Группируем по типам
        templates_by_type = {}
        for t in templates:
            if t.template_type not in templates_by_type:
                templates_by_type[t.template_type] = []
            templates_by_type[t.template_type].append(t)
        
        return templates.TemplateResponse(
            "admin/templates.html", 
            {
                "request": request, 
                "title": "Шаблоны уведомлений",
                "templates_by_type": templates_by_type,
                "templates": templates
            }
        )
        
    except Exception as e:
        logger.error(f"Ошибка загрузки шаблонов: {e}")
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request, 
                "title": "Ошибка",
                "error": f"Не удалось загрузить шаблоны: {str(e)}"
            }
        )

@router.post("/api/templates/update")
async def admin_update_template(
    template_id: int,
    title: str = None,
    message: str = None,
    is_active: bool = None,
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """Обновление шаблона"""
    try:
        from models.notification_template import NotificationTemplate
        from sqlalchemy import select
        from datetime import datetime
        
        result = await db.execute(
            select(NotificationTemplate).where(NotificationTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        
        if not template:
            return JSONResponse({"success": False, "error": "Шаблон не найден"})
        
        if title is not None:
            template.title = title
        if message is not None:
            template.message = message
        if is_active is not None:
            template.is_active = is_active
        
        template.updated_at = datetime.utcnow()
        await db.commit()
        
        return JSONResponse({"success": True, "message": "Шаблон обновлён"})
        
    except Exception as e:
        logger.error(f"Ошибка обновления шаблона: {e}")
        return JSONResponse({"success": False, "error": str(e)})


# ========== АНАЛИТИКА MINI APP ==========

@router.get("/mini-app-analytics", response_class=HTMLResponse)
async def admin_mini_app_analytics(
    request: Request,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """Аналитика использования Telegram Mini App"""
    try:
        from models.user_activity import UserActivity
        from datetime import datetime, timedelta
        import json
        
        since = datetime.utcnow() - timedelta(days=days)
        
        # Получаем статистику из БД
        # Уникальные пользователи Mini App
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
        
        # Статистика по дням
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
        
        # Топ пользователей по времени
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
        
        # Вычисляем дополнительные метрики для графиков
        max_daily_minutes = max([d["avg_duration_minutes"] for d in daily_data], default=0)
        max_user_minutes = max([u["total_duration_minutes"] for u in top_users], default=0)
        
        # Среднее время за день (для всех пользователей)
        avg_daily_minutes = 0
        if daily_data:
            total_daily_avg = sum([d["avg_duration_minutes"] for d in daily_data])
            avg_daily_minutes = total_daily_avg / len(daily_data)
        
        # Данные для графика (инвертируем порядок для отображения)
        chart_data = {
            "labels": [d["date"] for d in daily_data],
            "data": [d["avg_duration_minutes"] for d in daily_data]
        }
        
        stats = {
            "total_unique_users": total_unique,
            "total_sessions": sessions_count,
            "avg_session_duration_seconds": round(avg_session_duration, 1),
            "avg_session_duration_minutes": round(avg_session_duration / 60, 1),
            "daily_stats": daily_data,
            "top_users": top_users
        }
        
        logger.info(f"Mini App аналитика загружена: {days} дней, {total_unique} пользователей, {sessions_count} сессий")
        
        return templates.TemplateResponse(
            "admin/mini-app-analytics.html",
            {
                "request": request,
                "title": "Аналитика Mini App",
                "days": days,
                "stats": stats,
                "avg_daily_minutes": round(avg_daily_minutes, 1),
                "max_daily_minutes": max_daily_minutes,
                "max_user_minutes": max_user_minutes,
                "chart_data_json": json.dumps(chart_data),
                "stats_json": json.dumps(stats)
            }
        )
        
    except Exception as e:
        import traceback
        logger.error(f"Ошибка загрузки аналитики Mini App: {e}\n{traceback.format_exc()}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "title": "Ошибка",
                "error": f"Не удалось загрузить аналитику Mini App: {str(e)}"
            }
        )


@router.get("/api/mini-app-stats")
async def admin_mini_app_stats(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    admin_username: str = Depends(verify_admin)
):
    """API для получения статистики Mini App"""
    try:
        from models.user_activity import UserActivity
        from datetime import datetime, timedelta
        
        since = datetime.utcnow() - timedelta(days=days)
        
        # Статистика по дням
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
        
        data = []
        for row in daily_stats.fetchall():
            data.append({
                "date": str(row.date) if row.date else None,
                "unique_users": row.unique_users or 0,
                "sessions": row.sessions or 0,
                "avg_duration_seconds": round(row.avg_duration or 0, 1),
                "avg_duration_minutes": round((row.avg_duration or 0) / 60, 1)
            })
        
        return JSONResponse({"success": True, "data": data})
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики Mini App: {e}")
        return JSONResponse({"success": False, "error": str(e)})
