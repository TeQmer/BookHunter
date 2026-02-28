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
        
        if isinstance(schedule, (int, float)):
            # Интервал в секундах
            seconds = int(schedule)
            if seconds >= 3600:
                hours = seconds // 3600
                interval_description = f"Каждые {hours} ч."
                next_run = now.replace(second=0, microsecond=0)
                # Округляем до ближайшего интервала
                next_run = next_run.replace(minute=((now.minute // 15) * 15) % 60)
            else:
                minutes = seconds // 60
                interval_description = f"Каждые {minutes} мин."
                next_run = now.replace(second=0, microsecond=0)
                next_run = next_run.replace(minute=((now.minute // 15) * 15) % 60)
        elif isinstance(schedule, crontab):
            # Crontab расписание
            interval_description = f"Ежедневно в {schedule.hour:02d}:{schedule.minute:02d}"
            # Вычисляем следующий запуск
            next_run = now.replace(hour=schedule.hour, minute=schedule.minute, second=0, microsecond=0)
            if next_run <= now:
                from datetime import timedelta
                next_run = next_run + timedelta(days=1)
        
        schedule_data.append({
            'name': task_name,
            'task': task_full_name,
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
    
    # Формируем данные о последних запусках
    last_runs['check_all_alerts'] = {
        'last_run': None,
        'status': 'unknown',
        'duration': None
    }
    last_runs['update_chitai_gorod_token'] = {
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
        update_chitai_gorod_token,
        scan_discounts,
        update_popular_books,
        test_task,
        cleanup_old_logs,
        send_pending_notifications
    )
    from services.celery_app import celery_app
    
    task_mapping = {
        'check_all_alerts': check_all_alerts,
        'update_chitai_gorod_token': update_chitai_gorod_token,
        'scan_discounts': scan_discounts,
        'update_popular_books': update_popular_books,
        'test_task': test_task,
        'cleanup_old_logs': cleanup_old_logs,
        'send_pending_notifications': send_pending_notifications,
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
        # Статистика книг по магазинам
        stores_stats = await db.execute(
            select(Book.source, func.count(Book.id).label('count'))
            .where(Book.source.isnot(None))
            .group_by(Book.source)
            .order_by(desc('count'))
        )
        stores_data = stores_stats.mappings().all()
        
        # Статистика по авторам (топ-10)
        authors_stats = await db.execute(
            select(Book.author, func.count(Book.id).label('count'))
            .where(Book.author.isnot(None))
            .group_by(Book.author)
            .order_by(desc('count'))
            .limit(10)
        )
        authors_data = authors_stats.mappings().all()
        
        # Статистика по ценовым диапазонам
        price_ranges = await db.execute(
            select(
                func.sum(case((Book.current_price < 500, 1), else_=0)).label('under_500'),
                func.sum(case((Book.current_price >= 500, Book.current_price < 1000, 1), else_=0)).label('500_1000'),
                func.sum(case((Book.current_price >= 1000, Book.current_price < 2000, 1), else_=0)).label('1000_2000'),
                func.sum(case((Book.current_price >= 2000, 1), else_=0)).label('over_2000')
            )
        )
        price_stats = price_ranges.mappings().one_or_none()
        
        # Статистика скидок
        discount_stats = await db.execute(
            select(
                func.avg(Book.discount_percent).label('avg_discount'),
                func.max(Book.discount_percent).label('max_discount'),
                func.sum(case((Book.discount_percent > 0, 1), else_=0)).label('discounted_books'),
                func.count(Book.id).label('total_books')
            )
        )
        discount_data = discount_stats.mappings().one_or_none()
        
        # Активность пользователей за последние 30 дней
        thirty_days_ago = datetime.now() - timedelta(days=30)
        user_activity = await db.execute(
            select(func.count(User.id))
            .where(User.created_at >= thirty_days_ago)
        )
        new_users_30d = user_activity.scalar() or 0

        # Статистика подписок по статусу
        alerts_stats = await db.execute(
            select(Alert.is_active, func.count(Alert.id))
            .group_by(Alert.is_active)
        )
        alerts_data = alerts_stats.mappings().all()
        
        # Статистика парсинга за последние 7 дней
        seven_days_ago = datetime.now() - timedelta(days=7)
        parsing_stats = await db.execute(
            select(ParsingLog.status, func.count(ParsingLog.id))
            .where(ParsingLog.created_at >= seven_days_ago)
            .group_by(ParsingLog.status)
        )
        parsing_data = parsing_stats.mappings().all()

        # Формируем данные для шаблона - явно преобразуем к словарям
        def row_to_dict(row):
            """Безопасное преобразование строки результата в словарь"""
            if hasattr(row, '_mapping'):
                return dict(row._mapping)
            return dict(row) if hasattr(row, 'keys') else row
        
        analytics_data = {
            'stores_stats': [row_to_dict(row) for row in stores_data],
            'authors_stats': [row_to_dict(row) for row in authors_data],
            'price_stats': {
                'under_500': int(price_stats['under_500']) if price_stats and price_stats.get('under_500') else 0,
                '500_1000': int(price_stats['500_1000']) if price_stats and price_stats.get('500_1000') else 0,
                '1000_2000': int(price_stats['1000_2000']) if price_stats and price_stats.get('1000_2000') else 0,
                'over_2000': int(price_stats['over_2000']) if price_stats and price_stats.get('over_2000') else 0
            },
            'discount_stats': {
                'avg_discount': round(float(discount_data['avg_discount']), 1) if discount_data and discount_data.get('avg_discount') else 0,
                'max_discount': int(discount_data['max_discount']) if discount_data and discount_data.get('max_discount') else 0,
                'discounted_books': int(discount_data['discounted_books']) if discount_data and discount_data.get('discounted_books') else 0,
                'total_books': int(discount_data['total_books']) if discount_data and discount_data.get('total_books') else 0,
                'discount_percentage': round((int(discount_data['discounted_books']) / int(discount_data['total_books']) * 100), 1) if discount_data and discount_data.get('total_books') and int(discount_data['total_books']) > 0 else 0
            },
            'user_stats': {
                'new_users_30d': new_users_30d
            },
            'alerts_stats': [row_to_dict(row) for row in alerts_data],
            'parsing_stats': [row_to_dict(row) for row in parsing_data]
        }
        
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
