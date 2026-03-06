# 🚀 Инструкция по деплою BookHunter

## Предварительные требования

- Сервер с Ubuntu 20.04+
- Docker и Docker Compose установлены
- Доступ к репозиторию GitHub
- Настроенный FlareSolverr (для обхода защиты)

---

## ⚡ Быстый деплой

Выполните на сервере:

```bash
# 1. Переходим в директорию проекта
cd /var/www/bookhunter

# 2. Pull последних изменений
git pull origin main

# 3. Копируем статику Telegram Mini App
cp telegram/app/css/mini-app.css /var/www/bookhunter/telegram/css/mini-app.css
cp telegram/app/js/telegram.js /var/www/bookhunter/telegram/js/telegram.js
cp telegram/app/index.html /var/www/bookhunter/telegram/index.html
chown www-data:www-data /var/www/bookhunter/telegram/css/mini-app.css
chown www-data:www-data /var/www/bookhunter/telegram/js/telegram.js
chown www-data:www-data /var/www/bookhunter/telegram/index.html

# 4. Перезапускаем контейнеры
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

---

## 🔧 Ручной перезапуск сервисов

### Перезапуск только парсера (без простоя БД):
```bash
docker compose -f docker-compose.prod.yml restart parser
```

### Перезапуск Celery (для применения изменений в задачах):
```bash
docker compose -f docker-compose.prod.yml restart celery
```

### Перезапуск всех сервисов:
```bash
docker compose -f docker-compose.prod.yml restart
```

### Просмотр статуса контейнеров:
```bash
docker compose -f docker-compose.prod.yml ps
```

---

## 📊 Мониторинг и логи

### 🔍 Логи парсера Wildberries (в реальном времени)

```bash
# Все логи парсера
docker compose -f docker-compose.prod.yml logs -f parser

# Только ошибки
docker compose -f docker-compose.prod.yml logs parser | grep -i error

# Логи сtimestamp
docker compose -f docker-compose.prod.yml logs -f --timestamps parser

# Последние 100 строк
docker compose -f docker-compose.prod.yml logs --tail 100 parser
```

### 🔍 Логи Celery (задачи)

```bash
# Все логи Celery worker
docker compose -f docker-compose.prod.yml logs -f celery

# Логи конкретной задачи (обновление cookies WB)
docker compose -f docker-compose.prod.yml logs celery | grep -i "wildberries"

# Логи Celery Beat (расписание)
docker compose -f docker-compose.prod.yml logs -f celery-beat
```

### 🔍 Логи FlareSolverr

```bash
docker compose -f docker-compose.prod.yml logs -f flaresolverr
```

### 🔍 Логи Redis

```bash
docker compose -f docker-compose.prod.yml logs -f redis
```

### 📈 Мониторинг всех сервисов

```bash
# Статус всех контейнеров
docker compose -f docker-compose.prod.yml ps

# Использование ресурсов
docker stats

# Использование конкретного сервиса
docker stats bookhunter-parser-1
docker stats bookhunter-celery-1
```

---

## 🧪 Тестирование парсера Wildberries

### 1. Ручной тест через Celery

```bash
# Запустить парсинг тестового запроса
docker compose -f docker-compose.prod.yml exec celery celery -A services.celery_app call services.celery_tasks.parse_books --args='["python"]' --kwargs='{"source": "wildberries", "max_pages": 1}'

# Или через Python в контейнере парсера
docker compose -f docker-compose.prod.yml exec parser python -c "
import asyncio
from parsers.wildberries import WildberriesParser

async def test():
    parser = WildberriesParser()
    books = await parser.search_books('python', max_pages=1)
    print(f'Найдено книг: {len(books)}')
    for book in books[:3]:
        print(f'  - {book.title}: {book.current_price} руб. ({book.discount_percent}% скидка)')

asyncio.run(test())
"
```

### 2. Тест обновления cookies WB

```bash
# Запустить задачу обновления cookies вручную
docker compose -f docker-compose.prod.yml exec celery celery -A services.celery_app call services.celery_tasks.update_wildberries_cookies
```

### 3. Проверка cookies в Redis

```bash
# Подключиться к Redis
docker compose -f docker-compose.prod.yml exec redis redis-cli

# Проверить наличие cookies
GET wildberries_cookies

# Удалить старые cookies (для тестирования обновления)
DEL wildberries_cookies
```

### 4. Тест через API (если есть)

```bash
# Пример запроса к API
curl -X POST http://localhost:8000/api/parse \
  -H "Content-Type: application/json" \
  -d '{"query": "python", "source": "wildberries", "max_pages": 1}'
```

---

## 🐛 Диагностика проблем

### Парсер возвращает 401:
```bash
# 1. Проверить cookies в Redis
docker compose -f docker-compose.prod.yml exec redis redis-cli GET wildberries_cookies

# 2. Проверить статус FlareSolverr
curl http://localhost:8191/v1/status

# 3. Запустить обновление cookies вручную
docker compose -f docker-compose.prod.yml exec celery celery -A services.celery_app call services.celery_tasks.update_wildberries_cookies
```

### Парсер возвращает 429 (rate limit):
```bash
# Подождать и проверить логи
docker compose -f docker-compose.prod.yml logs --tail 50 parser | grep -i "429\|rate"
```

### Celery задачи не выполняются:
```bash
# Проверить очередь задач
docker compose -f docker-compose.prod.yml exec celery celery -A services.celery_app inspect active

# Проверить запланированные задачи
docker compose -f docker-compose.prod.yml exec celery celery -A services.celery_app inspect scheduled
```

### FlareSolverr не работает:
```bash
# Проверить статус
curl http://localhost:8191/v1/status

# Перезапустить FlareSolverr
docker compose -f docker-compose.prod.yml restart flaresolverr
```

---

## 📋 Проверка работоспособности после деплоя

```bash
# 1. Проверить, что все контейнеры запущены
docker compose -f docker-compose.prod.yml ps

# 2. Проверить логи парсера на наличие ошибок
docker compose -f docker-compose.prod.yml logs parser --tail 20

# 3. Проверить доступность FlareSolverr
curl -s http://localhost:8191/v1/status | jq .

# 4. Проверить наличие cookies в Redis
docker compose -f docker-compose.prod.yml exec redis redis-cli EXISTS wildberries_cookies
# Должно вернуть 1 (есть) или 0 (нет)

# 5. Запустить тестовый парсинг
docker compose -f docker-compose.prod.yml exec parser python -c "
import asyncio
from parsers.wildberries import WildberriesParser

async def test():
    parser = WildberriesParser()
    books = await parser.search_books('книга', max_pages=1)
    print(f'Найдено: {len(books)}')

asyncio.run(test())
"
```

---

## 🔐 Полезные переменные окружения

Проверить в `.env` файле:

```bash
# Для WB парсера
FLARESOLVERR_URL=http://flaresolverr:8191/v1
WB_X_WBAAS_TOKEN=...
WB_COOKIES_TTL=43200  # 12 часов

# Для Читай-города
CHITAI_GOROD_BEARER_TOKEN=...
```

---

## 📞 Быстрые команды

| Действие | Команда |
|----------|---------|
| Перезапустить всё | `docker compose -f docker-compose.prod.yml restart` |
| Логи парсера | `docker compose -f docker-compose.prod.yml logs -f parser` |
| Логи Celery | `docker compose -f docker-compose.prod.yml logs -f celery` |
| Обновить cookies WB | `docker compose -f docker-compose.prod.yml exec celery celery -A services.celery_app call services.celery_tasks.update_wildberries_cookies` |
| Тест парсера | `docker compose -f docker-compose.prod.yml exec parser python -c "..."` |
| Статус контейнеров | `docker compose -f docker-compose.prod.yml ps` |
| Ресурсы | `docker stats` |
