# Скрипт очистки проекта BookHunter от временных файлов и мусора

Write-Host "🧹 Очистка проекта BookHunter..." -ForegroundColor Green

# Удаление Python cache
Write-Host "📦 Удаление __pycache__..." -ForegroundColor Yellow
Get-ChildItem -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# Удаление .pyc файлов
Write-Host "📦 Удаление .pyc файлов..." -ForegroundColor Yellow
Get-ChildItem -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

# Удаление .pyo файлов
Write-Host "📦 Удаление .pyo файлов..." -ForegroundColor Yellow
Get-ChildItem -Recurse -Filter "*.pyo" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

# Удаление логов
Write-Host "📋 Удаление логов..." -ForegroundColor Yellow
Get-ChildItem -Path "logs" -Filter "*.log" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Filter "*.log" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

# Удаление временных файлов
Write-Host "🗑️  Удаление временных файлов..." -ForegroundColor Yellow
Get-ChildItem -Filter "*.tmp" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Filter "*.temp" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Directory -Filter "tmp" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Directory -Filter "temp" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# Удаление кэша pytest
Write-Host "🧪 Удаление кэша pytest..." -ForegroundColor Yellow
Get-ChildItem -Directory -Filter ".pytest_cache" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Filter ".coverage" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

# Удаление кэша mypy
Write-Host "🔍 Удаление кэша mypy..." -ForegroundColor Yellow
Get-ChildItem -Directory -Filter ".mypy_cache" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# Удаление build/dist
Write-Host "🏗️  Удаление build/dist..." -ForegroundColor Yellow
Get-ChildItem -Directory -Filter "build" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Directory -Filter "dist" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# Удаление .egg-info
Write-Host "🥚 Удаление .egg-info..." -ForegroundColor Yellow
Get-ChildItem -Directory -Filter "*.egg-info" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# Очистка Docker
Write-Host "🐳 Очистка Docker..." -ForegroundColor Yellow
docker system prune -f 2>$null

Write-Host "✅ Очистка завершена!" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Статистика:" -ForegroundColor Cyan
Write-Host "  - Удалены Python cache файлы"
Write-Host "  - Удалены логи"
Write-Host "  - Удалены временные файлы"
Write-Host "  - Очищен Docker кэш"
Write-Host ""
Write-Host "🚀 Проект готов к деплою!" -ForegroundColor Green
