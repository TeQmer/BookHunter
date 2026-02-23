from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
import uvicorn
import os

from database.config import init_db
from api.health import router as health_router
from api.alerts import router as alerts_router
from api.stats import router as stats_router
from api.parser import router as parser_router
from api.users import router as users_router
from api.auth import router as auth_router
# Веб-интерфейс
from web.main import router as web_router
from web.books import router as books_router
from web.alerts import router as web_alerts_router
from web.admin import router as admin_router
from services.logger import setup_logger
from services.celery_app import setup_celery

# Настройка логгера
logger = setup_logger(__name__)


# ========== ЗАГОЛОВКИ БЕЗОПАСНОСТИ ==========

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware для добавления заголовков безопасности"""

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # Разрешённые источники для CSP
        cdn_sources = [
            "https://cdn.jsdelivr.net",
            "https://cdnjs.cloudflare.com",
            "https://fonts.googleapis.com",
            "https://fonts.gstatic.com"
        ]

        cdn_sources_str = " ".join(cdn_sources)

        # Заголовки безопасности
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; "
            f"script-src 'self' 'unsafe-inline' 'unsafe-eval' {cdn_sources_str}; "
            f"style-src 'self' 'unsafe-inline' {cdn_sources_str}; "
            f"img-src 'self' data: https:; "
            f"font-src 'self' data: {cdn_sources_str}; "
            f"connect-src 'self' {cdn_sources_str} https://api.telegram.org; "
            f"frame-ancestors 'none';"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        return response

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Инициализация при запуске
    logger.info("Starting BookHunter - book discount monitoring system")

    try:
        # Инициализация базы данных
        await init_db()
        logger.info("Database initialized")
        
        # Настройка Celery
        celery_app = setup_celery()
        app.state.celery_app = celery_app
        logger.info("Celery configured")
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации: {e}")
        raise
    
    yield
    
    # Очистка при завершении
    logger.info("System shutdown complete")

# Создание FastAPI приложения
app = FastAPI(
    title="📚 BookHunter — Мониторинг скидок на книги",
    description="BookHunter — система для отслеживания скидок на книги с интеграцией Google Sheets, Telegram Bot и веб-интерфейсом",
    version="1.0.0",
    lifespan=lifespan
)

# ========== НАСТРОЙКА CORS ==========
# Получаем разрешенные источники из переменных окружения
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # В продакшене укажите конкретные домены
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ========== ЗАЩИТА ОТ ЗАГРУЗОЧНЫХ ХОСТОВ ==========
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=os.getenv("ALLOWED_HOSTS", "*").split(","),  # В продакшене укажите конкретные хосты
)

# ========== ЗАГОЛОВКИ БЕЗОПАСНОСТИ ==========
app.add_middleware(SecurityHeadersMiddleware)

# Подключение статических файлов
app.mount("/static", StaticFiles(directory="web/static"), name="static")

# Подключение Telegram Mini App
app.mount("/telegram", StaticFiles(directory="telegram/app", html=True), name="telegram")

# Подключение шаблонов Jinja2
templates = Jinja2Templates(directory="web/templates")

# Регистрация роутеров API
app.include_router(health_router, prefix="/api/health", tags=["health"])
app.include_router(alerts_router, prefix="/api/alerts", tags=["alerts"])
app.include_router(stats_router, prefix="/api/stats", tags=["stats"])
app.include_router(parser_router, prefix="/api/parser", tags=["parser"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])

# Регистрация веб-роутеров
app.include_router(web_router, prefix="/web", tags=["web"])
app.include_router(books_router, prefix="/web/books", tags=["books"])
app.include_router(web_alerts_router, prefix="/web/alerts", tags=["web-alerts"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])

# Обработчик для корневого пути
@app.get("/")
async def root():
    """Перенаправление на веб-интерфейс"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/web", status_code=302)

# Глобальный обработчик ошибок
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Глобальный обработчик исключений"""
    logger.error(f"Необработанная ошибка: {exc}", exc_info=True)
    return {"error": "Внутренняя ошибка сервера"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
