from celery import Celery
from celery.schedules import crontab
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Определяем расписание задач
CELERY_BEAT_SCHEDULE = {
    # Проверка цен подписок каждые 4 часа (с парсингом по ссылкам)
    'check-subscriptions-prices-every-4-hours': {
        'task': 'services.celery_tasks.check_all_alerts',
        'schedule': 14400.0,  # 4 часа в секундах
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
    # Обновление токена Читай-города каждые 12 часов
    'update-chitai-gorod-token-every-12-hours': {
        'task': 'services.celery_tasks.update_chitai_gorod_token',
        'schedule': 43200.0,  # 12 часов в секундах
    },
}

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
    
    # Настройки Celery
    celery_app.conf.update(
        task_serializer=os.getenv("CELERY_TASK_SERIALIZER", "json"),
        result_serializer=os.getenv("CELERY_RESULT_SERIALIZER", "json"),
        accept_content=['json'],
        timezone=os.getenv("CELERY_TIMEZONE", "Europe/Moscow"),
        enable_utc=True,
        
        # Настройки для повторных попыток
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        
        # Логирование
        worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
        worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
        
        # Настройки для периодических задач
        beat_schedule=CELERY_BEAT_SCHEDULE,

        # Отключаем проблемные настройки
        task_send_sent_event=False,
        task_track_started=False,
    )
    
    return celery_app

# Создаем глобальный экземпляр Celery
celery_app = setup_celery()

if __name__ == "__main__":
    celery_app.start()
