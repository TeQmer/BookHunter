# 🚀 Инструкция по деплою на сервер Beget

**Дата:** 2025-01-21  
**Цель:** Обновить CORS настройки и развернуть BookHunter на сервере Beget

---

## 📋 Что изменилось

В этом обновлении исправлена проблема с CORS для Telegram Mini App. Теперь в `ALLOWED_ORIGINS` добавлены домены Telegram, чтобы приложение работало корректно.

**Изменения в `.env.prod.example`:**
```env
ALLOWED_ORIGINS=https://ВАШ_ДОМЕН.ru,https://www.ВАШ_ДОМЕН.ru,https://t.me,https://web.telegram.org
```

---

## 🚀 Быстрый деплой (3 шага)

### Шаг 1: Подключение к серверу

```bash
ssh root@85.198.103.166
```

### Шаг 2: Обновление кода и конфигурации

```bash
# Переход в директорию проекта
cd BookHunter

# Получение последних изменений из Git
git pull origin main

# Обновление .env файла (ВАЖНО!)
cp .env.prod.example .env
nano .env
```

**В .env файле ОБЯЗАТЕЛЬНО измените:**

```env
# Ваш домен
MINI_APP_URL=https://mybook-hunter.ru/telegram

# CORS с Telegram доменами (УЖЕ В ФАЙЛЕ, но проверьте!)
ALLOWED_ORIGINS=https://mybook-hunter.ru,https://www.mybook-hunter.ru,https://t.me,https://web.telegram.org

# Trusted Hosts
ALLOWED_HOSTS=mybook-hunter.ru,www.mybook-hunter.ru

# База данных
DATABASE_URL=postgresql+asyncpg://bookuser:Rusik88228@postgres:5432/book_discounts
POSTGRES_USER=bookuser
POSTGRES_PASSWORD=Rusik88228

# Redis
REDIS_URL=redis://:Rusik88228@redis:6379/0
REDIS_PASSWORD=Rusik88228

# Telegram Bot
TELEGRAM_BOT_TOKEN=8333283624:AAHT1_EOeGk4xdmXz5bNZqxRfgVVMKLNjec

# Google Sheets
GOOGLE_SHEET_ID=1Ti418MqA5wy2jZkVkwibvDT8fgtszGxUQzHFmkhnkZc
# Убедитесь, что все GOOGLE_CREDENTIALS_* переменные заполнены!

# Админ-панель
ADMIN_USERNAME=admin
ADMIN_PASSWORD=Rusik88228

# Безопасность
SECRET_KEY=book_discount_monitor_secret_key_2024
DEBUG=False
LOG_LEVEL=INFO
```

**⚠️ ВАЖНО:** Проверьте, что все `GOOGLE_CREDENTIALS_*` переменные заполнены из вашего текущего .env файла!

### Шаг 3: Перезапуск приложения

```bash
# Остановка текущих контейнеров
docker compose -f docker-compose.prod.yml down

# Пересборка и запуск
docker compose -f docker-compose.prod.yml up -d --build

# Проверка статуса
docker compose -f docker-compose.prod.yml ps

# Просмотр логов (чтобы убедиться, что всё работает)
docker compose -f docker-compose.prod.yml logs -f app
```

---

## ✅ Проверка после деплоя

### 1. Проверка по IP (если домен не работает)

```bash
curl http://85.198.103.166:8080/api/health
```

Ожидаемый результат: `{"status":"ok"}`

### 2. Проверка по домену

Откройте в браузере:
- **Главная страница:** https://mybook-hunter.ru/web
- **API Health:** https://mybook-hunter.ru/api/health
- **Mini App:** https://mybook-hunter.ru/telegram
- **Админ-панель:** https://mybook-hunter.ru/admin

### 3. Проверка Telegram Mini App

1. Откройте бота в Telegram
2. Нажмите кнопку "📚 BookHunter"
3. Попробуйте добавить/редактировать подписку
4. **Должно работать без ошибок!**

---

## 🐛 Если что-то не работает

### Ошибка CORS в браузере

**Симптом:** В консоли браузера видите ошибку `Access-Control-Allow-Origin`

**Решение:**
```bash
# Проверьте .env файл
cat .env | grep ALLOWED_ORIGINS

# Должно быть:
# ALLOWED_ORIGINS=https://mybook-hunter.ru,https://www.mybook-hunter.ru,https://t.me,https://web.telegram.org

# Если не так, исправьте и перезапустите
docker compose -f docker-compose.prod.yml restart app
```

### Приложение не запускается

```bash
# Просмотр логов
docker compose -f docker-compose.prod.yml logs app

# Если ошибка в .env, исправьте и перезапустите
nano .env
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

### Telegram Mini App не открывается

**Симптом:** При нажатии на кнопку бота ничего не происходит

**Решение:**
1. Проверьте, что `MINI_APP_URL` правильный: `https://mybook-hunter.ru/telegram`
2. Проверьте, что SSL сертификат установлен (замок 🔒 в адресной строке)
3. Проверьте настройки Web App в @BotFather:
   ```
   /setmenubutton
   Выберите вашего бота
   URL: https://mybook-hunter.ru/telegram
   ```

---

## 🔄 Автоматическое обновление (скрипт)

Для упрощения будущих обновлений создайте скрипт:

```bash
nano update.sh
```

```bash
#!/bin/bash
echo "🔄 Обновление BookHunter..."

# Получение обновлений
git pull origin main

# Перезапуск контейнеров
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d --build

# Очистка старых образов
docker image prune -f

echo "✅ Обновление завершено!"
echo "📊 Проверка статуса:"
docker compose -f docker-compose.prod.yml ps
```

Сделайте исполняемым:
```bash
chmod +x update.sh
```

Теперь для обновления достаточно:
```bash
./update.sh
```

---

## 📊 Мониторинг

### Логи приложения
```bash
docker compose -f docker-compose.prod.yml logs -f app
```

### Статус контейнеров
```bash
docker compose -f docker-compose.prod.yml ps
```

### Ресурсы сервера
```bash
htop
# Или
top
```

---

## 🎯 Чек-лист для деплоя

- [ ] Подключились к серверу по SSH
- [ ] Выполнили `git pull origin main`
- [ ] Скопировали `.env.prod.example` в `.env`
- [ ] Проверили и исправили все переменные в `.env`
- [ ] Проверили, что `ALLOWED_ORIGINS` содержит Telegram домены
- [ ] Проверили, что все `GOOGLE_CREDENTIALS_*` заполнены
- [ ] Остановили контейнеры: `docker compose -f docker-compose.prod.yml down`
- [ ] Запустили контейнеры: `docker compose -f docker-compose.prod.yml up -d --build`
- [ ] Проверили статус: `docker compose -f docker-compose.prod.yml ps`
- [ ] Проверили логи: `docker compose -f docker-compose.prod.yml logs app`
- [ ] Проверили API Health: `curl http://85.198.103.166:8080/api/health`
- [ ] Проверили веб-интерфейс по домену: https://mybook-hunter.ru/web
- [ ] Проверили Telegram Mini App: https://mybook-hunter.ru/telegram
- [ ] Протестировали добавление/редактирование подписки в Mini App

---

## 📞 Поддержка

Если возникнут проблемы:
1. Проверьте логи: `docker compose -f docker-compose.prod.yml logs app`
2. Проверьте .env файл: `cat .env | grep -E "ALLOWED_ORIGINS|MINI_APP_URL"`
3. Перезапустите контейнеры: `docker compose -f docker-compose.prod.yml restart app`

---

**Удачи с деплоем! 🚀**
