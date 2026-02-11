# Скрипт быстрого деплоя BookHunter на сервере (Windows)

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("update", "restart", "logs", "status", "backup", "cleanup")]
    [string]$Action
)

# Цвета для вывода
function log_info { Write-Host "ℹ️  $args" -ForegroundColor Blue }
function log_success { Write-Host "✅ $args" -ForegroundColor Green }
function log_warning { Write-Host "⚠️  $args" -ForegroundColor Yellow }
function log_error { Write-Host "❌ $args" -ForegroundColor Red }

switch ($Action) {
    "update" {
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
        Start-Sleep -Seconds 5
        docker compose ps

        log_success "Обновление завершено!"
    }

    "restart" {
        log_info "🔄 Перезапуск BookHunter..."

        docker compose down
        docker compose up -d

        log_success "Перезапуск завершен!"
    }

    "logs" {
        log_info "📋 Просмотр логов..."

        if ($args.Count -gt 0) {
            docker compose logs -f $args[0]
        } else {
            docker compose logs -f
        }
    }

    "status" {
        log_info "📊 Статус контейнеров..."

        docker compose ps

        Write-Host ""
        log_info "Проверка API..."
        try {
            $response = Invoke-RestMethod -Uri "http://localhost:8000/api/health" -ErrorAction Stop
            $response | ConvertTo-Json
        } catch {
            Write-Host "API недоступен" -ForegroundColor Red
        }
    }

    "backup" {
        log_info "💾 Создание бэкапа..."

        $BACKUP_DIR = "./backups"
        $DATE = Get-Date -Format "yyyyMMdd_HHmmss"

        New-Item -ItemType Directory -Force -Path $BACKUP_DIR | Out-Null

        # Бэкап базы данных
        log_info "Бэкап базы данных..."
        docker compose exec -T postgres pg_dump -U bookuser book_discounts | Out-File -FilePath "$BACKUP_DIR\db_$DATE.sql" -Encoding utf8

        # Бэкап файлов
        log_info "Бэкап файлов..."
        Compress-Archive -Path ".env", "credentials.json" -DestinationPath "$BACKUP_DIR\files_$DATE.zip" -Force

        # Удаление старых бэкапов
        Get-ChildItem -Path $BACKUP_DIR -Recurse | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } | Remove-Item -Force

        log_success "Бэкап создан: $BACKUP_DIR\db_$DATE.sql"
    }

    "cleanup" {
        log_info "🧹 Очистка проекта..."

        # Удаление Python cache
        Get-ChildItem -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        Get-ChildItem -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

        # Удаление логов
        Get-ChildItem -Path "logs" -Filter "*.log" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

        # Удаление временных файлов
        Get-ChildItem -Filter "*.tmp" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
        Get-ChildItem -Filter "*.temp" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

        # Очистка Docker
        docker system prune -f

        log_success "Очистка завершена!"
    }

    default {
        log_error "Неизвестное действие: $Action"
        Write-Host "Доступные действия:"
        Write-Host "  update   - Обновить проект из Git"
        Write-Host "  restart  - Перезапустить контейнеры"
        Write-Host "  logs     - Просмотр логов (опционально: logs app)"
        Write-Host "  status   - Показать статус"
        Write-Host "  backup   - Создать бэкап"
        Write-Host "  cleanup  - Очистить проект"
    }
}
