# Руководство по системе автоматического обновления токена

## Обзор

Система автоматического обновления токена Читай-Города использует:
- **FlareSolverr** — для обхода Cloudflare защиты
- **Celery** — для запуска задач по расписанию
- **Redis** — для хранения токена
- **TokenManager** — для управления токеном

## Архитектура

```
┌─────────────────┐
│  ChitaiGorodAPI │
│   (парсер)      │
└────────┬────────┘
         │ 401 ошибка
         ↓
┌─────────────────┐
│  TokenManager   │
│   (триггер)     │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   Celery Task   │
│ (update_token)  │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  FlareSolverr   │
│ (Selenium)      │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│    Redis        │
│ (хранение)      │
└─────────────────┘
```

## Компоненты

### 1. FlareSolverr

Контейнер, который запускает Selenium с `undetected-chromedriver` и автоматически решает Cloudflare challenge.

**Преимущества:**
- Работает в idle режиме с минимальным потреблением ресурсов
- Простой HTTP API
- Не требует изменений в основном приложении

### 2. TokenManager (`services/token_manager.py`)

Менеджер токенов с хранением в Redis:

```python
from services.token_manager import get_token_manager

token_manager = get_token_manager()

# Получить токен (с fallback из Redis → .env)
token = token_manager.get_chitai_gorod_token_fallback()

# Сохранить токен
token_manager.save_chitai_gorod_token(token, ttl=86400)

# Триггер обновления
token_manager.trigger_token_update()
```

### 3. Celery задача (`services/celery_tasks.py`)

Задача `update_chitai_gorod_token`:
1. Запрашивает страницу через FlareSolverr
2. Извлекает токен из cookies
3. Проверяет работоспособность токена
4. Сохраняет в Redis и .env

### 4. API клиент (`services/chitai_gorod_api_client.py`)

Автоматическое обновление токена при 401 ошибке:
- Триггерит Celery задачу
- Ждет обновления (до 60 сек)
- Повторяет запрос с новым токеном

## Развертывание

### 1. Обновление docker-compose.prod.yml

FlareSolverr уже добавлен в `docker-compose.prod.yml`:

```yaml
flaresolverr:
  image: ghcr.io/flaresolverr/flaresolverr:latest
  container_name: bookhunter_flaresolverr
  restart: always
  environment:
    - LOG_LEVEL=info
    - TZ=Europe/Moscow
    - HEADLESS=true
    - DISABLE_MEDIA=true
  networks:
    - bookhunter_network
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8191"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s
```

### 2. Обновление .env

Добавьте в `.env`:

```env
# FlareSolverr Settings
FLARESOLVERR_URL=http://flaresolverr:8191/v1

# Chitai-Gorod API Settings
CHITAI_GOROD_API_URL=https://web-agr.chitai-gorod.ru/web/api/v2
CHITAI_GOROD_BEARER_TOKEN=ВАШ_ТОКЕН_БУДЕТ_ОБНОВЛЕН_АВТОМАТИЧЕСКИ
CHITAI_GOROD_USER_ID=ВАШ_USER_ID
CHITAI_GOROD_CITY_ID=39
```

### 3. Пересборка и запуск

```bash
# Остановите контейнеры
docker compose -f docker-compose.prod.yml down

# Пересоберите образы
docker compose -f docker-compose.prod.yml build

# Запустите контейнеры
docker compose -f docker-compose.prod.yml up -d

# Проверьте логи FlareSolverr
docker logs bookhunter_flaresolverr -f

# Проверьте логи Celery
docker logs bookhunter_celery_beat -f
docker logs bookhunter_celery_worker -f
```

## Расписание обновления токена

Задача обновления токена настроена в `services/celery_app.py`:

```python
CELERY_BEAT_SCHEDULE = {
    'update-chitai-gorod-token': {
        'task': 'services.celery_tasks.update_chitai_gorod_token',
        'schedule': crontab(minute=0, hour='*/3'),  # Каждые 3 часа
    },
    # ... другие задачи
}
```

Вы можете изменить расписание по необходимости:
- Каждые 6 часов: `crontab(minute=0, hour='*/6')`
- Каждый день в 3 ночи: `crontab(minute=0, hour=3)`
- Каждые 30 минут: `crontab(minute='*/30')`

## Проверка работы

### 1. Проверка FlareSolverr

```bash
# Проверьте, что контейнер запущен
docker ps | grep flaresolverr

# Проверьте логи
docker logs bookhunter_flaresolverr

# Проверьте API
curl -X POST http://localhost:8191/v1 \
  -H "Content-Type: application/json" \
  -d '{"cmd": "ping"}'
```

### 2. Проверка токена в Redis

```bash
# Зайдите в Redis контейнер
docker exec -it bookhunter_redis redis-cli -a ВАШ_ПАРОЛЬ_REDIS

# Проверьте токен
GET chitai_gorod_token

# Проверьте TTL
TTL chitai_gorod_token

# Выход
exit
```

### 3. Ручное обновление токена

```bash
# Выполните Celery задачу вручную
docker exec -it bookhunter_celery_worker celery -A services.celery_app call \
  services.celery_tasks.update_chitai_gorod_token

# Или через Flower (если настроен)
```

### 4. Проверка парсера

```bash
# Протестируйте API
curl http://ВАШ_ДОМЕН/api/books/search?q=python
```

## Мониторинг

### Логи

```bash
# FlareSolverr
docker logs bookhunter_flaresolverr -f

# Celery Beat
docker logs bookhunter_celery_beat -f

# Celery Worker
docker logs bookhunter_celery_worker -f

# API
docker logs bookhunter_api -f
```

### Метрики

Проверьте:
- Частоту обновления токена
- Успешность обновления (200 OK)
- Время выполнения задачи
- Ошибки в логах

## Решение проблем

### Проблема: FlareSolverr не запускается

**Решение:**

```bash
# Проверьте логи
docker logs bookhunter_flaresolverr

# Проверьте здоровье
docker inspect bookhunter_flaresolverr | grep -A 10 Health

# Перезапустите
docker restart bookhunter_flaresolverr
```

### Проблема: Токен не обновляется

**Решение:**

```bash
# Проверьте логи Celery
docker logs bookhunter_celery_worker --tail 100

# Проверьте логи FlareSolverr
docker logs bookhunter_flaresolverr --tail 100

# Ручной запуск задачи
docker exec -it bookhunter_celery_worker celery -A services.celery_app call \
  services.celery_tasks.update_chitai_gorod_token
```

### Проблема: 401 ошибки продолжаются

**Решение:**

1. Проверьте токен в Redis
2. Проверьте логи обновления токена
3. Убедитесь, что FlareSolverr работает
4. Попробуйте увеличить время ожидания в `_wait_for_token_update()`

### Проблема: Высокое потребление ресурсов

**Решение:**

FlareSolverr в idle режиме потребляет минимум ресурсов. Если потребление высокое:

1. Проверьте, что не запущено много задач одновременно
2. Уменьшите частоту обновления токена
3. Используйте `DISABLE_MEDIA=true` для отключения загрузки медиа

## Альтернативные подходы

Если FlareSolverr не работает, можно попробовать:

### 1. Playwright вместо FlareSolverr

```python
from playwright.async_api import async_playwright

async def get_token_playwright():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://www.chitai-gorod.ru")
        cookies = await page.context.cookies()
        token = next((c['value'] for c in cookies if c['name'] == 'bearer_token'), None)
        await browser.close()
        return token
```

### 2. Мобильный API

Проанализируйте трафик мобильного приложения Читай-Город и используйте его API.

### 3. Прокси

Используйте прокси для обхода IP-блокировок.

## Вывод

Система автоматического обновления токена обеспечивает:
- ✅ Надежное обновление токена
- ✅ Минимальное потребление ресурсов
- ✅ Автоматическое восстановление при 401 ошибках
- ✅ Хранение токена в Redis с TTL
- ✅ Расписание обновления через Celery Beat
