# Развертывание системы автоматического обновления токена

## Быстрый старт

### 1. Обновите код на сервере

```bash
# На сервере
cd /path/to/bookhunter
git pull
```

### 2. Обновите .env

Добавьте новую переменную:

```bash
nano .env
```

Добавьте в конец:

```env
# FlareSolverr Settings
FLARESOLVERR_URL=http://flaresolverr:8191/v1
```

### 3. Пересоберите контейнеры

```bash
# Остановите контейнеры
docker compose -f docker-compose.prod.yml down

# Удалите старый образ Celery (если есть)
docker rmi bookhunter-celery_beat bookhunter-celery_worker 2>/dev/null || true

# Пересоберите и запустите
docker compose -f docker-compose.prod.yml up -d --build

# Подождите запуска FlareSolverr (около 40 сек)
sleep 40
```

### 4. Проверьте статус

```bash
# Проверьте все контейнеры
docker compose -f docker-compose.prod.yml ps

# Должны видеть: flaresolverr, redis, postgres, api, celery_beat, celery_worker, nginx
```

### 5. Проверьте логи

```bash
# FlareSolverr
docker logs bookhunter_flaresolverr --tail 50

# Celery Beat (должен видеть scheduled task)
docker logs bookhunter_celery_beat --tail 50

# Celery Worker
docker logs bookhunter_celery_worker --tail 50
```

### 6. Ручное обновление токена (опционально)

```bash
# Запустите задачу обновления токена вручную
docker exec -it bookhunter_celery_worker celery -A services.celery_app call \
  services.celery_tasks.update_chitai_gorod_token
```

### 7. Проверьте токен в Redis

```bash
# Получите пароль Redis из .env
grep REDIS_PASSWORD .env

# Зайдите в Redis
docker exec -it bookhunter_redis redis-cli -a ВАШ_ПАРОЛЬ_REDIS

# Проверьте токен
GET chitai_gorod_token

# Проверьте TTL (должен быть > 0)
TTL chitai_gorod_token

# Выход
exit
```

### 8. Проверьте работу парсера

```bash
# Протестируйте API
curl http://ВАШ_ДОМЕН/api/books/search?q=python
```

## Проверка работоспособности

### ✅ Успешное развертывание, если:

1. **FlareSolverr запущен:**
   ```bash
   docker ps | grep flaresolverr
   # Должен видеть: bookhunter_flaresolverr
   ```

2. **Celery Beat планирует задачу:**
   ```bash
   docker logs bookhunter_celery_beat | grep "update-chitai-gorod-token"
   # Должен видеть: Scheduler: Sending due task
   ```

3. **Токен в Redis:**
   ```bash
   docker exec -it bookhunter_redis redis-cli -a ВАШ_ПАРОЛЬ_REDIS GET chitai_gorod_token
   # Должен видеть токен (длинная строка)
   ```

4. **Парсер работает:**
   ```bash
   curl http://ВАШ_ДОМЕН/api/books/search?q=python
   # Должен видеть JSON с книгами
   ```

## Мониторинг

### Основные логи

```bash
# Все логи одновременно
docker compose -f docker-compose.prod.yml logs -f

# Только важные
docker compose -f docker-compose.prod.yml logs -f celery_worker flaresolverr
```

### Частые проверки

```bash
# Статус контейнеров
docker compose -f docker-compose.prod.yml ps

# Ресурсы
docker stats

# Токен в Redis
docker exec -it bookhunter_redis redis-cli -a ВАШ_ПАРОЛЬ_REDIS GET chitai_gorod_token
```

## Решение проблем

### FlareSolverr не запускается

```bash
# Проверьте логи
docker logs bookhunter_flaresolverr

# Перезапустите
docker restart bookhunter_flaresolverr

# Проверьте сеть
docker network inspect bookhunter_bookhunter_network
```

### Токен не обновляется

```bash
# Проверьте логи Celery
docker logs bookhunter_celery_worker --tail 100

# Ручной запуск
docker exec -it bookhunter_celery_worker celery -A services.celery_app call \
  services.celery_tasks.update_chitai_gorod_token

# Проверьте FlareSolverr
curl -X POST http://localhost:8191/v1 \
  -H "Content-Type: application/json" \
  -d '{"cmd": "ping"}'
```

### 401 ошибки

1. Подождите, пока токен обновится (до 60 сек)
2. Проверьте токен в Redis
3. Проверьте логи обновления
4. При необходимости обновите вручную

## Следующие шаги

1. ✅ Разверните систему
2. ✅ Проверьте работоспособность
3. ✅ Настройте мониторинг
4. ✅ Следите за логами первые 24 часа
5. ✅ При необходимости настройте частоту обновления

## Полная документация

Подробная документация: `TOKEN_UPDATE_GUIDE.md`
