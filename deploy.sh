#!/bin/bash
# Скрипт быстрого деплоя BookHunter на сервере

set -e  # Остановиться при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Проверка аргументов
if [ $# -eq 0 ]; then
    log_error "Укажите действие!"
    echo "Использование: ./deploy.sh [update|restart|logs|status|backup]"
    exit 1
fi

ACTION=$1

case $ACTION in
    update)
        log_info "🔄 Обновление BookHunter..."

        # Получение обновлений
        log_info "Получение обновлений из Git..."
        git pull origin main

        # Остановка контейнеров
        log_info "Остановка контейнеров..."
        docker compose down

        # Пересборка и запуск
        log_info "Пересборка и запуск..."
        docker compose up -d --build

        # Очистка старых образов
        log_info "Очистка старых образов..."
        docker image prune -f

        # Проверка статуса
        log_info "Проверка статуса..."
        sleep 5
        docker compose ps

        log_success "Обновление завершено!"
        ;;

    restart)
        log_info "🔄 Перезапуск BookHunter..."

        docker compose down
        docker compose up -d

        log_success "Перезапуск завершен!"
        ;;

    logs)
        log_info "📋 Просмотр логов..."

        if [ -n "$2" ]; then
            docker compose logs -f "$2"
        else
            docker compose logs -f
        fi
        ;;

    status)
        log_info "📊 Статус контейнеров..."

        docker compose ps

        echo ""
        log_info "Проверка API..."
        curl -s http://localhost:8000/api/health | jq . || echo "API недоступен"
        ;;

    backup)
        log_info "💾 Создание бэкапа..."

        BACKUP_DIR="./backups"
        DATE=$(date +%Y%m%d_%H%M%S)

        mkdir -p $BACKUP_DIR

        # Бэкап базы данных
        log_info "Бэкап базы данных..."
        docker compose exec -T postgres pg_dump -U bookuser book_discounts > $BACKUP_DIR/db_$DATE.sql

        # Бэкап файлов
        log_info "Бэкап файлов..."
        tar -czf $BACKUP_DIR/files_$DATE.tar.gz .env credentials.json

        # Удаление старых бэкапов
        find $BACKUP_DIR -type f -mtime +7 -delete

        log_success "Бэкап создан: $BACKUP_DIR/db_$DATE.sql"
        ;;

    cleanup)
        log_info "🧹 Очистка проекта..."

        # Удаление Python cache
        find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
        find . -type f -name "*.pyc" -delete 2>/dev/null

        # Удаление логов
        rm -f logs/*.log 2>/dev/null

        # Удаление временных файлов
        rm -f *.tmp *.temp 2>/dev/null

        # Очистка Docker
        docker system prune -f

        log_success "Очистка завершена!"
        ;;

    *)
        log_error "Неизвестное действие: $ACTION"
        echo "Доступные действия:"
        echo "  update   - Обновить проект из Git"
        echo "  restart  - Перезапустить контейнеры"
        echo "  logs     - Просмотр логов (опционально: logs app)"
        echo "  status   - Показать статус"
        echo "  backup   - Создать бэкап"
        echo "  cleanup  - Очистить проект"
        exit 1
        ;;
esac
