.PHONY: help up down restart logs migrate migrate-down create-admin shell test lint clean

# Основные команды
help: ## Показать справку по командам
	@echo "Доступные команды:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

up: ## Запустить все сервисы
	docker-compose up -d

down: ## Остановить все сервисы
	docker-compose down

restart: down up ## Перезапустить все сервисы

logs: ## Показать логи всех сервисов
	docker-compose logs -f

logs-app: ## Логи основного приложения
	docker-compose logs -f app

logs-worker: ## Логи Celery worker
	docker-compose logs -f celery_worker

logs-beat: ## Логи Celery beat
	docker-compose logs -f celery_beat

# База данных
migrate: ## Создать и применить миграции Alembic
	docker-compose exec app alembic revision --autogenerate -m "Auto migration"
	docker-compose exec app alembic upgrade head

migrate-down: ## Откатить миграции
	docker-compose exec app alembic downgrade -1

create-admin: ## Создать админ-пользователя
	docker-compose exec app python -c "from models import User; from database import get_db; db = next(get_db()); from auth import create_user; create_user(db, 'admin', 'admin@admin.com', 'admin123', is_admin=True)"

# Оболочка
shell: ## Войти в оболочку приложения
	docker-compose exec app bash

# Тестирование
test: ## Запустить тесты
	docker-compose exec app pytest

# Линтинг и формат
lint: ## Проверить код линтером
	docker-compose exec app flake8 .
	docker-compose exec app black --check .
	docker-compose exec app isort --check-only .

format: ## Форматировать код
	docker-compose exec app black .
	docker-compose exec app isort .

# Очистка
clean: ## Очистить Docker ресурсы
	docker-compose down -v
	docker system prune -f

# Мониторинг
stats: ## Показать статистику системы
	@echo "Статистика Docker контейнеров:"
	docker-compose ps
	@echo "\nСтатистика PostgreSQL:"
	docker-compose exec postgres psql -U bookuser -d book_discounts -c "SELECT count(*) as total_books FROM books; SELECT count(*) as total_alerts FROM alerts; SELECT count(*) as total_notifications FROM notifications;"

health: ## Проверить состояние всех сервисов
	@echo "Проверка PostgreSQL:"
	docker-compose exec postgres pg_isready -U bookuser -d book_discounts && echo "✅ PostgreSQL OK" || echo "❌ PostgreSQL ERROR"
	@echo "\nПроверка Redis:"
	docker-compose exec redis redis-cli ping && echo "✅ Redis OK" || echo "❌ Redis ERROR"
	@echo "\nПроверка приложения:"
	curl -s http://localhost:8000/health || echo "❌ App ERROR"

# Разработка
dev-setup: ## Настройка для разработки
	@echo "Копирование .env файла..."
	cp .env.example .env
	@echo "Создание структуры папок..."
	mkdir -p logs uploads static/templates
	@echo "✅ Разработческая среда настроена"
