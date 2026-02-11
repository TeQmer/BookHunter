#!/bin/bash
# Скрипт очистки проекта BookHunter от временных файлов и мусора

echo "🧹 Очистка проекта BookHunter..."

# Удаление Python cache
echo "📦 Удаление __pycache__..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

# Удаление .pyc файлов
echo "📦 Удаление .pyc файлов..."
find . -type f -name "*.pyc" -delete 2>/dev/null

# Удаление .pyo файлов
echo "📦 Удаление .pyo файлов..."
find . -type f -name "*.pyo" -delete 2>/dev/null

# Удаление .pyd файлов
echo "📦 Удаление .pyd файлов..."
find . -type f -name "*.pyd" -delete 2>/dev/null

# Удаление логов
echo "📋 Удаление логов..."
rm -rf logs/*.log 2>/dev/null
rm -f *.log 2>/dev/null

# Удаление временных файлов
echo "🗑️  Удаление временных файлов..."
rm -f *.tmp *.temp 2>/dev/null
rm -rf tmp/ temp/ 2>/dev/null

# Удаление кэша pytest
echo "🧪 Удаление кэша pytest..."
rm -rf .pytest_cache/ 2>/dev/null
rm -rf .coverage 2>/dev/null

# Удаление кэша mypy
echo "🔍 Удаление кэша mypy..."
rm -rf .mypy_cache/ 2>/dev/null

# Удаление build/dist
echo "🏗️  Удаление build/dist..."
rm -rf build/ dist/ 2>/dev/null

# Удаление .egg-info
echo "🥚 Удаление .egg-info..."
rm -rf *.egg-info/ 2>/dev/null

# Очистка Docker
echo "🐳 Очистка Docker..."
docker system prune -f 2>/dev/null

echo "✅ Очистка завершена!"
echo ""
echo "📊 Статистика:"
echo "  - Удалены Python cache файлы"
echo "  - Удалены логи"
echo "  - Удалены временные файлы"
echo "  - Очищен Docker кэш"
echo ""
echo "🚀 Проект готов к деплою!"
