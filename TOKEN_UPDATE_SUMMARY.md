# Сводка изменений: Автоматическое обновление токена Читай-Города

## Что было сделано

### 1. FlareSolverr в docker-compose.prod.yml
- Добавлен контейнер `flaresolverr` для обхода Cloudflare
- Настроен headless режим
- Отключена загрузка медиа для экономии ресурсов
- Добавлен healthcheck

### 2. TokenManager (services/token_manager.py)
- Создан новый модуль для управления токенами
- Хранение токена в Redis с TTL
- Fallback механизм (Redis → .env)
- Триггер Celery задач для обновления

### 3. Celery задача (services/celery_tasks.py)
- Задача `update_chitai_gorod_token` для обновления токена
- Запрос через FlareSolverr
- Извлечение токена из cookies
- Проверка работоспособности токена
- Сохранение в Redis и .env
- Автоматический retry при ошибках

### 4. API клиент (services/chitai_gorod_api_client.py)
- Интеграция с TokenManager
- Автоматическое обновление токена при 401 ошибке
- Ожидание обновления токена (до 60 сек)
- Повторение запроса с новым токеном

### 5. Расписание (services/celery_app.py)
- Задача обновления токена каждые 3 часа
- Имя задачи: `update-chitai-gorod-token-every-3-hours`

### 6. Конфигурация (.env)
- Добавлена переменная `FLARESOLVERR_URL`
- Обновлены .env.example и .env.prod.example

### 7. Документация
- `TOKEN_UPDATE_GUIDE.md` — полное руководство
- `DEPLOY_TOKEN_UPDATE.md` — инструкции по развертыванию

## Как это работает

```
1. Парсер делает запрос к API Читай-Города
2. Получает 401 ошибку (токен истёк)
3. API клиент триггерит Celery задачу update_chitai_gorod_token
4. Задача запрашивает страницу через FlareSolverr
5. FlareSolverr обходит Cloudflare и возвращает cookies
6. Задача извлекает токен из cookies
7. Проверяет токен на работоспособность
8. Сохраняет в Redis (TTL: 24 часа) и .env
9. API клиент ждёт обновления токена
10. Повторяет запрос с новым токеном
```

## Развертывание на сервере

### Шаги:

1. **Обновить код:**
   ```bash
   cd /path/to/bookhunter
   git pull
   ```

2. **Обновить .env:**
   ```bash
   nano .env
   # Добавить: FLARESOLVERR_URL=http://flaresolverr:8191/v1
   ```

3. **Пересобрать контейнеры:**
   ```bash
   docker compose -f docker-compose.prod.yml down
   docker compose -f docker-compose.prod.yml up -d --build
   ```

4. **Проверить статус:**
   ```bash
   docker compose -f docker-compose.prod.yml ps
   # Должен видеть flaresolverr среди контейнеров
   ```

5. **Проверить логи:**
   ```bash
   docker logs bookhunter_flaresolverr --tail 50
   docker logs bookhunter_celery_beat --tail 50
   docker logs bookhunter_celery_worker --tail 50
   ```

6. **Ручное обновление токена (опционально):**
   ```bash
   docker exec -it bookhunter_celery_worker celery -A services.celery_app call \
     services.celery_tasks.update_chitai_gorod_token
   ```

7. **Проверить токен в Redis:**
   ```bash
   docker exec -it bookhunter_redis redis-cli -a ВАШ_ПАРОЛЬ_REDIS GET chitai_gorod_token
   ```

## Преимущества решения

✅ **Надёжность:** Автоматическое обновление при 401 ошибке
✅ **Эффективность:** Playwright/FlareSolverr только для получения токена
✅ **Минимальные ресурсы:** FlareSolverr в idle режиме потребляет минимум
✅ **Гибкость:** Расписание через Celery Beat
✅ **Отказоустойчивость:** Fallback механизм (Redis → .env)
✅ **Мониторинг:** Подробные логи и метрики

## Следующие шаги

1. Развернуть на сервере
2. Проверить работу FlareSolverr
3. Протестировать обновление токена
4. Мониторить логи первые 24 часа
5. При необходимости настроить частоту обновления

## Документация

- Полное руководство: `TOKEN_UPDATE_GUIDE.md`
- Инструкции по развертыванию: `DEPLOY_TOKEN_UPDATE.md`
