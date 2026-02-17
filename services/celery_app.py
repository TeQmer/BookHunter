from celery import Celery
from celery.schedules import crontab
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

def setup_celery() -> Celery:
    """Настройка и создание Celery приложения"""
    
    # Создаем Celery приложение
    celery_app = Celery(
        "book_discount_monitor",
        broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
        backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
        include=[
            'services.celery_tasks'
        ]
    )
    
    # Настройки Celery - используем старый формат (CELERY_*) для совместимости
    celery_app.conf.update(
        CELERY_TASK_SERIALIZER=os.getenv("CELERY_TASK_SERIALIZER", "json"),
        CELERY_RESULT_SERIALIZER=os.getenv("CELERY_RESULT_SERIALIZER", "json"),
        CELERY_ACCEPT_CONTENT=['json'],
        CELERY_TIMEZONE=os.getenv("CELERY_TIMEZONE", "Europe/Moscow"),
        CELERY_ENABLE_UTC=True,
        
        # Настройки для повторных попыток
        CELERY_TASK_ACKS_LATE=True,
        CELERY_WORKER_PREFETCH_MULTIPLIER=1,
        
        # Логирование
        CELERY_WORKER_LOG_FORMAT='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
        CELERY_WORKER_TASK_LOG_FORMAT='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
        
        # Настройки для периодических задач
        CELERY_BEAT_SCHEDULE={
            # Проверка подписок каждые 30 минут
            'check-all-alerts-every-30-minutes': {
                'task': 'services.celery_tasks.check_all_alerts',
                'schedule': 1800.0,  # 30 минут в секундах
            },
            # Сканирование скидок каждый час
            'scan-discounts-every-hour': {
                'task': 'services.celery_tasks.scan_discounts',
                'schedule': 3600.0,  # 1 час в секундах
            },
            # Обновление популярных книг каждые 6 часов
            'update-popular-books-every-6-hours': {
                'task': 'services.celery_tasks.update_popular_books',
                'schedule': 21600.0,  # 6 часов в секундах
            },
            # Очистка старых логов каждый день в 3:00
            'cleanup-old-logs-daily': {
                'task': 'services.celery_tasks.cleanup_old_logs',
                'schedule': crontab(hour=3, minute=0),  # Каждый день в 3:00
            },
            # Тестовая задача каждый день в 9:00
            'daily-test-task': {
                'task': 'services.celery_tasks.test_task',
                'schedule': crontab(hour=9, minute=0),  # Каждый день в 9:00
            },
            # Обновление токена Читай-города каждые 3 часа
            'update-chitai-gorod-token-every-3-hours': {
                'task': 'services.celery_tasks.update_chitai_gorod_token',
                'schedule': 10800.0,  # 3 часа в секундах
            },
        },
        CELERY_BEAT_SCHEDULER='celery.beat.PersistentScheduler',
        CELERY_BEAT_SCHEDULE_FILENAME=os.getenv('CELERY_BEAT_SCHEDULE_FILENAME', '/tmp/celerybeat-schedule'),
        
        # Отключаем проблемные настройки
        CELERY_TASK_SEND_SENT_EVENT=False,
        CELERY_TASK_TRACK_STARTED=False,
    )
    
    return celery_app

# Создаем глобальный экземпляр Celery
celery_app = setup_celery()

if __name__ == "__main__":
    celery_app.start()
