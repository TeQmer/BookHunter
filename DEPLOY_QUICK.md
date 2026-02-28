# Инструкция по деплою на сервер

## Быстрый деплой

```bash
# 1. Подключение к серверу
ssh root@lcvajxhzpy

# 2. Переход в директорию проекта
cd ~/BookHunter

# 3. Загрузка обновлений с Git
git pull origin main

# 4. Пересборка и запуск контейнеров
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d

# 5. Проверка статуса
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f
```

## После деплоя

Перезапустить Celery:

```bash
docker exec bookhunter-celery-1 supervisorctl restart all
```

Или перезапустить все контейнеры:

```bash
docker compose -f docker-compose.prod.yml restart
```

## Проверка логов

```bash
# Все сервисы
docker compose -f docker-compose.prod.yml logs -f

# Конкретный сервис
docker compose -f docker-compose.prod.yml logs -f celery
docker compose -f docker-compose.prod.yml logs -f web
```
