# 🚀 Полная инструкция по запуску BookHunter на сервере

**Ваши домены:**
- Основной: `mybook-hunter.ru`
- Для Telegram: `mybook-hunter.store`

**Время на развертывание:** ~60 минут

---

## 📋 СОДЕРЖАНИЕ

1. [Выбор и покупка сервера](#1-выбор-и-покупка-сервера)
2. [Настройка DNS для доменов](#2-настройка-dns-для-доменов)
3. [Подключение к серверу](#3-подключение-к-серверу)
4. [Установка необходимого ПО](#4-установка-необходимого-по)
5. [Загрузка проекта на сервер](#5-загрузка-проекта-на-сервер)
6. [Настройка переменных окружения (.env)](#6-настройка-переменных-окружения-env)
7. [Настройка Nginx](#7-настройка-nginx)
8. [Получение SSL сертификата](#8-получение-ssl-сертификата)
9. [Запуск приложения](#9-запуск-приложения)
10. [Настройка Telegram Bot](#10-настройка-telegram-bot)
11. [Проверка работы](#11-проверка-работы)
12. [Траблшутинг](#12-траблшутинг)

---

## 1. ВЫБОР И ПОКУПКА СЕРВЕРА

### Рекомендуемый хостинг:

**Beget (простой и надёжный):**
- Сайт: https://beget.com/ru
- Рекомендуемый тариф: **Cloud-2**
  - 2 CPU ядра
  - 4 GB RAM
  - 40 GB SSD
  - Цена: ~350 ₽/мес

**Или Timeweb Cloud:**
- Сайт: https://timeweb.cloud/
- Рекомендуемый тариф: **Cloud-2**
  - 2 CPU ядра
  - 4 GB RAM
  - 40 GB SSD
  - Цена: ~300 ₽/мес

### Пошаговая инструкция (на примере Beget):

1. **Перейдите на сайт:** https://beget.com/ru

2. **Нажмите кнопку:** "Регистрация" (верхний правый угол)

3. **Заполните форму:**
   - Email: ваш email
   - Пароль: сложный пароль (запомните!)
   - Нажмите: "Зарегистрироваться"

4. **Подтвердите email:**
   - Зайдите в почту
   - Найдите письмо от Beget
   - Нажмите на кнопку подтверждения

5. **Перейдите в панель управления:**
   - После входа нажмите: "Войти в панель"

6. **Нажмите:** "Облачные серверы" (в меню слева)

7. **Нажмите кнопку:** "Создать сервер"

8. **Настройте сервер:**
   - **Название:** `bookhunter` (любое имя)
   - **Операционная система:** выберите:
     - 🖥️ **Ubuntu 22.04 LTS** (НЕ выбирайте CentOS или другие!)
   - **Тариф:** выберите "Cloud-2" (2 CPU, 4 GB RAM, 40 GB)
   - **Пароль root:**
     - Нажмите кнопку "Сгенерировать"
     - Скопируйте пароль и сохраните в безопасном месте!
   - Нажмите: "Создать сервер"

9. **Дождитесь создания сервера:**
   - Обычно занимает 2-5 минут
   - Статус изменится на "Активен"

10. **Скопируйте IP адрес:**
    - Найдите поле "IP адрес"
    - Пример: `123.45.67.89`
    - Скопируйте его (будет нужен позже)

**✅ Сервер готов! Переходите к следующему шагу.**

---

## 2. НАСТРОЙКА DNS ДЛЯ ДОМЕНОВ

Ваши домены уже должны быть куплены. Теперь нужно привязать их к IP сервера.

### Если домены на Reg.ru:

1. **Перейдите:** https://www.reg.ru/

2. **Войдите в аккаунт**

3. **Нажмите:** "Мои домены" (верхнее меню)

4. **Найдите домен `mybook-hunter.ru`:**
   - Нажмите на домен
   - Нажмите кнопку: "Управление зоной"

5. **Настройте DNS записи для `mybook-hunter.ru`:**

   **Удалите все существующие записи** (кроме NS записей!)

   **Добавьте новую запись:**
   - Нажмите кнопку: "Добавить запись"
   - Тип: выберите `A`
   - Имя: оставьте пустым (или введите `@`)
   - Значение: вставьте ваш IP сервера (например, `123.45.67.89`)
   - Нажмите: "ОК"

   **Добавьте запись для www:**
   - Нажмите кнопку: "Добавить запись"
   - Тип: выберите `A`
   - Имя: `www`
   - Значение: вставьте ваш IP сервера (например, `123.45.67.89`)
   - Нажмите: "ОК"

6. **Настройте DNS для `mybook-hunter.store`:**
   - Вернитесь в "Мои домены"
   - Нажмите на домен `mybook-hunter.store`
   - Нажмите: "Управление зоной"
   - Удалите все записи (кроме NS)
   - Добавьте записи (как для первого домена):
     - Тип: `A`, Имя: `@`, Значение: `123.45.67.89`
     - Тип: `A`, Имя: `www`, Значение: `123.45.67.89`

7. **Нажмите:** "Сохранить изменения"

8. **Дождитесь обновления DNS:**
   - Обычно занимает 5-30 минут
   - Можно проверить здесь: https://www.whatsmydns.net/

**✅ DNS настроен! Переходите к следующему шагу.**

---

## 3. ПОДКЛЮЧЕНИЕ К СЕРВЕРУ

### На Windows:

1. **Откройте PowerShell:**
   - Нажмите: `Win + X`
   - Выберите: "Windows PowerShell"

2. **Подключитесь к серверу:**
   ```bash
   ssh root@123.45.67.89
   ```
   *(замените `123.45.67.89` на ваш реальный IP)*

3. **Введите пароль:**
   - Пароль не отображается при вводе (это нормально!)
   - Вставьте пароль из письма от хостинга
   - Нажмите: `Enter`

4. **Успешное подключение:**
   - Вы увидите что-то вроде: `root@server-name:~#`
   - Вы подключены к серверу!

### На Mac/Linux:

1. **Откройте терминал:**
   - `Cmd + Space` → введите "Terminal"

2. **Подключитесь:**
   ```bash
   ssh root@123.45.67.89
   ```

3. **Введите пароль и нажмите Enter**

**✅ Вы подключены к серверу!**

---

## 4. УСТАНОВКА НЕОБХОДИМОГО ПО

Выполните следующие команды по очереди (копируйте и вставляйте):

### 1. Обновите систему:

```bash
apt update && apt upgrade -y
```

*(Подождите, пока установка завершится — 2-5 минут)*

### 2. Установите Docker:

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

*(Подождите 1-2 минуты)*

### 3. Установите Docker Compose:

```bash
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

### 4. Установите Nginx и Certbot:

```bash
apt install nginx certbot python3-certbot-nginx git -y
```

### 5. Установите Python (для генерации паролей):

```bash
apt install python3 python3-pip -y
```

### 6. Проверьте установки:

```bash
docker --version
docker-compose --version
nginx -v
```

Вы должны увидеть версии программ.

**✅ ПО установлено! Переходите к следующему шагу.**

---

## 5. ЗАГРУЗКА ПРОЕКТА НА СЕРВЕР

### Вариант 1: Из GitHub (рекомендуется)

1. **Клонируйте проект:**

   ```bash
   cd /var/www
   git clone https://github.com/TeQmer/BookHunter.git bookhunter
   cd bookhunter
   ```

2. **Проверьте файлы:**

   ```bash
   ls -la
   ```

   Вы должны увидеть файлы: `main.py`, `docker-compose.prod.yml`, и т.д.

### Вариант 2: Через SFTP (если GitHub не работает)

1. **Скачайте FileZilla:** https://filezilla-project.org/

2. **Установите и откройте FileZilla**

3. **Подключитесь к серверу:**
   - Хост: `123.45.67.89`
   - Пользователь: `root`
   - Пароль: ваш пароль от сервера
   - Порт: `22`

4. **Загрузите файлы:**
   - Перетащите все файлы проекта в `/var/www/bookhunter`

**✅ Проект загружен! Переходите к следующему шагу.**

---

## 6. НАСТРОЙКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ (.ENV)

### 1. Создайте файл .env.prod:

```bash
nano .env.prod
```

### 2. Сгенерируйте сильные пароли:

Откройте новую вкладку терминала на вашем компьютере (НЕ на сервере!) и выполните:

```bash
python3 -c "import secrets; print('DB Password:', secrets.token_urlsafe(32)); print('Redis Password:', secrets.token_urlsafe(32)); print('Secret Key:', secrets.token_urlsafe(32))"
```

Скопируйте сгенерированные пароли!

### 3. Заполните .env.prod:

Вставьте следующее содержимое в редактор `nano` (на сервере) и замените значения:

```bash
# ============================================================
# КОНФИГУРАЦИЯ ДЛЯ ПРОДАКШЕНА
# ============================================================

# ========== БАЗА ДАННЫХ POSTGRESQL ==========
DATABASE_URL=postgresql+asyncpg://bookuser:ВАШ_СГЕНЕРИРОВАННЫЙ_ПАРОЛЬ_БД@postgres:5432/book_discounts
POSTGRES_USER=bookuser
POSTGRES_PASSWORD=ВАШ_СГЕНЕРИРОВАННЫЙ_ПАРОЛЬ_БД

# ========== REDIS ==========
REDIS_URL=redis://:ВАШ_СГЕНЕРИРОВАННЫЙ_ПАРОЛЬ_REDIS@redis:6379/0
REDIS_PASSWORD=ВАШ_СГЕНЕРИРОВАННЫЙ_ПАРОЛЬ_REDIS

# ========== GOOGLE SHEETS ==========
GOOGLE_SHEET_ID=ВАШ_ID_ТАБЛИЦЫ_GOOGLE

# Google Credentials (скопируйте из вашего credentials.json)
GOOGLE_CREDENTIALS_TYPE=service_account
GOOGLE_CREDENTIALS_PROJECT_ID=ВАШ_PROJECT_ID
GOOGLE_CREDENTIALS_PRIVATE_KEY_ID=ВАШ_PRIVATE_KEY_ID
GOOGLE_CREDENTIALS_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nВАШ_ПРИВАТНЫЙ_КЛЮЧ\n-----END PRIVATE KEY-----\n"
GOOGLE_CREDENTIALS_CLIENT_EMAIL=ВАШ_EMAIL@project-id.iam.gserviceaccount.com
GOOGLE_CREDENTIALS_CLIENT_ID=ВАШ_CLIENT_ID
GOOGLE_CREDENTIALS_AUTH_URI=https://accounts.google.com/o/oauth2/auth
GOOGLE_CREDENTIALS_TOKEN_URI=https://oauth2.googleapis.com/token
GOOGLE_CREDENTIALS_AUTH_PROVIDER_CERT_URL=https://www.googleapis.com/oauth2/v1/certs
GOOGLE_CREDENTIALS_CLIENT_CERT_URL=https://www.googleapis.com/robot/v1/metadata/x509/ВАШ_EMAIL%40project-id.iam.gserviceaccount.com

# ========== TELEGRAM BOT ==========
TELEGRAM_BOT_TOKEN=ВАШ_ТОКЕН_ОТ_BOTFATHER

# ========== TELEGRAM MINI APP ==========
MINI_APP_URL=https://mybook-hunter.store/telegram

# ========== БЕЗОПАСНОСТЬ ==========
SECRET_KEY=ВАШ_СГЕНЕРИРОВАННЫЙ_СЕКРЕТНЫЙ_КЛЮЧ
ALGORITHM=HS256

# ========== АДМИН-ПАНЕЛЬ ==========
ADMIN_USERNAME=admin
ADMIN_PASSWORD=ВАШ_ПАРОЛЬ_ДЛЯ_АДМИНКИ

# ========== CORS ==========
ALLOWED_ORIGINS=https://mybook-hunter.ru,https://www.mybook-hunter.ru,https://mybook-hunter.store,https://www.mybook-hunter.store,https://t.me,https://web.telegram.org

# ========== TRUSTED HOSTS ==========
ALLOWED_HOSTS=mybook-hunter.ru,www.mybook-hunter.ru,mybook-hunter.store,www.mybook-hunter.store

# ========== НАСТРОЙКИ ПРИЛОЖЕНИЯ ==========
APP_NAME=BookHunter
DEBUG=False
LOG_LEVEL=INFO

# ========== CELERY ==========
CELERY_BROKER_URL=redis://:ВАШ_СГЕНЕРИРОВАННЫЙ_ПАРОЛЬ_REDIS@redis:6379/0
CELERY_RESULT_BACKEND=redis://:ВАШ_СГЕНЕРИРОВАННЫЙ_ПАРОЛЬ_REDIS@redis:6379/0
CELERY_TASK_SERIALIZER=json
CELERY_RESULT_SERIALIZER=json
CELERY_ACCEPT_CONTENT=['json']
CELERY_TIMEZONE=Europe/Moscow
```

### 4. Сохраните файл:

- Нажмите: `Ctrl + O`
- Нажмите: `Enter`
- Нажмите: `Ctrl + X` (для выхода)

### 5. Проверьте файл:

```bash
cat .env.prod
```

**✅ .env.prod настроен! Переходите к следующему шагу.**

---

## 7. НАСТРОЙКА NGINX

### 1. Создайте конфигурацию для основного домена:

```bash
nano /etc/nginx/sites-available/mybook-hunter.ru
```

### 2. Вставьте конфигурацию:

```nginx
# HTTP → HTTPS Redirect
server {
    listen 80;
    server_name mybook-hunter.ru www.mybook-hunter.ru;
    return 301 https://$server_name$request_uri;
}

# HTTPS Configuration
server {
    listen 443 ssl http2;
    server_name mybook-hunter.ru www.mybook-hunter.ru;

    # SSL сертификаты (будут получены через Certbot)
    ssl_certificate /etc/letsencrypt/live/mybook-hunter.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mybook-hunter.ru/privkey.pem;

    # SSL настройки безопасности
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # CORS заголовки
    add_header Access-Control-Allow-Origin "$http_origin" always;
    add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
    add_header Access-Control-Allow-Headers "Authorization, Content-Type, X-Requested-With" always;
    add_header Access-Control-Allow-Credentials "true" always;

    # Обработка OPTIONS запросов
    if ($request_method = 'OPTIONS') {
        return 204;
    }

    # Основной прокси на приложение
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_http_version 1.1;
        proxy_read_timeout 86400;
    }

    # Telegram Mini App
    location /telegram {
        alias /var/www/bookhunter/telegram/app;
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    # WebSocket поддержка (если нужно)
    location /ws {
        proxy_pass http://127.0.0.1:8000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

Сохраните: `Ctrl + O`, `Enter`, `Ctrl + X`

### 3. Создайте конфигурацию для Telegram домена:

```bash
nano /etc/nginx/sites-available/mybook-hunter.store
```

Вставьте:

```nginx
# HTTP → HTTPS Redirect
server {
    listen 80;
    server_name mybook-hunter.store www.mybook-hunter.store;
    return 301 https://$server_name$request_uri;
}

# HTTPS Configuration (для Telegram Mini App)
server {
    listen 443 ssl http2;
    server_name mybook-hunter.store www.mybook-hunter.store;

    ssl_certificate /etc/letsencrypt/live/mybook-hunter.store/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mybook-hunter.store/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # CORS для Telegram
    add_header Access-Control-Allow-Origin "https://t.me https://web.telegram.org" always;
    add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
    add_header Access-Control-Allow-Headers "Content-Type, X-Requested-With" always;

    if ($request_method = 'OPTIONS') {
        return 204;
    }

    # Telegram Mini App
    location / {
        alias /var/www/bookhunter/telegram/app;
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    # Проксируем API запросы на основное приложение
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Сохраните: `Ctrl + O`, `Enter`, `Ctrl + X`

### 4. Активируйте конфигурации:

```bash
ln -s /etc/nginx/sites-available/mybook-hunter.ru /etc/nginx/sites-enabled/
ln -s /etc/nginx/sites-available/mybook-hunter.store /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default
```

### 5. Проверьте конфигурацию Nginx:

```bash
nginx -t
```

Вы должны увидеть: `syntax is ok` и `test is successful`

### 6. Перезапустите Nginx:

```bash
systemctl restart nginx
systemctl enable nginx
```

**✅ Nginx настроен! Переходите к следующему шагу.**

---

## 8. ПОЛУЧЕНИЕ SSL СЕРТИФИКАТА

### 1. Получите сертификат для основного домена:

```bash
certbot --nginx -d mybook-hunter.ru -d www.mybook-hunter.ru
```

**Ответьте на вопросы:**
1. Email: введите ваш email
2. Согласие с условиями: введите `Y` и нажмите Enter
3. Перенаправление HTTP на HTTPS: введите `2` и нажмите Enter

### 2. Получите сертификат для Telegram домена:

```bash
certbot --nginx -d mybook-hunter.store -d www.mybook-hunter.store
```

Ответьте на вопросы так же, как в первом случае.

### 3. Проверьте сертификаты:

```bash
certbot certificates
```

Вы должны увидеть оба домена с сертификатами.

### 4. Настройте автообновление:

```bash
(crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet") | crontab -
```

**✅ SSL сертификаты получены! Переходите к следующему шагу.**

---

## 9. ЗАПУСК ПРИЛОЖЕНИЯ

### 1. Запустите Docker контейнеры:

```bash
docker-compose -f docker-compose.prod.yml up -d
```

*(Подождите 2-3 минуты, пока контейнеры запустятся)*

### 2. Проверьте статус контейнеров:

```bash
docker-compose -f docker-compose.prod.yml ps
```

Вы должны увидеть все контейнеры со статусом `Up`:
- `app`
- `celery_worker`
- `celery_beat`
- `telegram_bot`
- `postgres`
- `redis`

### 3. Проверьте логи приложения:

```bash
docker-compose -f docker-compose.prod.yml logs app
```

Вы должны увидеть что-то вроде:
```
INFO: Uvicorn running on http://0.0.0.0:8000
INFO: Application startup complete
```

### 4. Проверьте логи Telegram бота:

```bash
docker-compose -f docker-compose.prod.yml logs telegram_bot
```

**✅ Приложение запущено! Переходите к следующему шагу.**

---

## 10. НАСТРОЙКА TELEGRAM BOT

### 1. Получите токен бота (если ещё нет):

1. **Откройте Telegram**
2. **Найдите @BotFather**
3. **Напишите:** `/newbot`
4. **Название бота:** `BookHunter` (или любое)
5. **Имя пользователя:** `mybookhunter_bot` (или любое, должно заканчиваться на `_bot`)
6. **Скопируйте токен** (выглядит как `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Настройте Webhook (опционально):

```bash
curl -F "url=https://mybook-hunter.ru/api/telegram/webhook" \
     -F "max_connections=100" \
     https://api.telegram.org/botВАШ_ТОКЕН/setWebhook
```

*(замените `ВАШ_ТОКЕН` на реальный токен)*

### 3. Настройте Menu Button (для Mini App):

1. **Откройте @BotFather**
2. **Напишите:** `/mybots`
3. **Выберите вашего бота**
4. **Bot Settings** → **Menu Button**
5. **Текст кнопки:** `📚 Открыть приложение`
6. **URL:** `https://mybook-hunter.store/telegram`
7. **Нажмите:** "Done"

### 4. Проверьте бота:

1. **Откройте вашего бота в Telegram**
2. **Напишите:** `/start`
3. **Нажмите на кнопку меню** (должна быть "📚 Открыть приложение")

**✅ Telegram Bot настроен! Переходите к следующему шагу.**

---

## 11. ПРОВЕРКА РАБОТЫ

### Проверьте в браузере:

1. **Откройте:** https://mybook-hunter.ru
   - ✅ Должен открыться сайт с HTTPS замком
   - ✅ Должна работать админка на `/admin`

2. **Откройте:** https://mybook-hunter.ru/api/health
   - ✅ Должен вернуть статус приложения

3. **Откройте:** https://mybook-hunter.store/telegram
   - ✅ Должен открыться Telegram Mini App

### Проверьте в Telegram:

1. **Откройте вашего бота**
2. **Напишите:** `/start`
3. **Нажмите кнопку меню**
4. ✅ Mini App должен открыться

### Проверьте логи:

```bash
docker-compose -f docker-compose.prod.yml logs -f
```

*(Нажмите `Ctrl + C` для выхода)*

**✅ Всё работает! Поздравляю с запуском!** 🎉

---

## 12. ТРАБЛШУТИНГ

### Сайт не открывается:

```bash
# Проверьте Nginx
systemctl status nginx

# Проверьте Docker контейнеры
docker-compose -f docker-compose.prod.yml ps

# Проверьте логи приложения
docker-compose -f docker-compose.prod.yml logs app

# Перезапустите Nginx
systemctl restart nginx
```

### SSL сертификат не работает:

```bash
# Проверьте сертификат
certbot certificates

# Получите сертификат заново
certbot --nginx -d mybook-hunter.ru -d www.mybook-hunter.ru --force-renewal

# Перезапустите Nginx
systemctl restart nginx
```

### Telegram Bot не отвечает:

```bash
# Проверьте токен в .env.prod
cat .env.prod | grep TELEGRAM_BOT_TOKEN

# Проверьте логи бота
docker-compose -f docker-compose.prod.yml logs telegram_bot

# Перезапустите бота
docker-compose -f docker-compose.prod.yml restart telegram_bot
```

### Mini App не открывается в Telegram:

Проверьте `.env.prod`:

```bash
cat .env.prod | grep -E "MINI_APP_URL|ALLOWED_ORIGINS|ALLOWED_HOSTS"
```

Должно быть:
```env
MINI_APP_URL=https://mybook-hunter.store/telegram
ALLOWED_ORIGINS=https://mybook-hunter.ru,https://mybook-hunter.store,https://t.me
ALLOWED_HOSTS=mybook-hunter.ru,mybook-hunter.store
```

### Google Sheets не работает:

```bash
# Проверьте Google Credentials
docker-compose -f docker-compose.prod.yml logs app | grep -i google

# Проверьте ID таблицы
cat .env.prod | grep GOOGLE_SHEET_ID
```

### Контейнеры не запускаются:

```bash
# Остановите все контейнеры
docker-compose -f docker-compose.prod.yml down

# Удалите volume (это удалит данные из БД!)
docker volume rm bookhunter_postgres_data bookhunter_redis_data

# Запустите заново
docker-compose -f docker-compose.prod.yml up -d
```

### Посмотреть логи всех контейнеров:

```bash
docker-compose -f docker-compose.prod.yml logs
```

### Посмотреть логи конкретного контейнера:

```bash
docker-compose -f docker-compose.prod.yml logs app
docker-compose -f docker-compose.prod.yml logs celery_worker
docker-compose -f docker-compose.prod.yml logs celery_beat
docker-compose -f docker-compose.prod.yml logs telegram_bot
```

---

## 📋 ЧЕК-ЛИСТ ДЕПЛОЯ

- [ ] Куплен сервер (Ubuntu 22.04)
- [ ] Домены привязаны к IP сервера (DNS)
- [ ] Docker установлен
- [ ] Docker Compose установлен
- [ ] Nginx установлен
- [ ] Проект загружен на сервер
- [ ] `.env.prod` настроен с реальными данными
- [ ] Nginx настроен для обоих доменов
- [ ] SSL сертификаты получены
- [ ] Docker контейнеры запущены
- [ ] Сайт открывается по HTTPS
- [ ] Telegram Bot настроен
- [ ] Mini App работает в Telegram
- [ ] Админ-панель доступна

---

## 📞 НУЖНА ПОМОЩЬ?

Если возникнут проблемы:

1. **Проверьте логи:** `docker-compose -f docker-compose.prod.yml logs`
2. **Проверьте конфигурацию Nginx:** `nginx -t`
3. **Проверьте статус служб:**
   ```bash
   systemctl status nginx
   systemctl status docker
   ```
4. **Перезагрузите сервер:**
   ```bash
   reboot
   ```
5. **Подключитесь снова и запустите:**
   ```bash
   cd /var/www/bookhunter
   docker-compose -f docker-compose.prod.yml up -d
   ```

---

## 🔧 ПОЛЕЗНЫЕ КОМАНДЫ

### Управление Docker:

```bash
# Запуск
docker-compose -f docker-compose.prod.yml up -d

# Остановка
docker-compose -f docker-compose.prod.yml down

# Перезапуск
docker-compose -f docker-compose.prod.yml restart

# Просмотр логов
docker-compose -f docker-compose.prod.yml logs -f

# Обновление проекта
git pull
docker-compose -f docker-compose.prod.yml up -d --build
```

### Управление Nginx:

```bash
# Перезапуск
systemctl restart nginx

# Проверка конфигурации
nginx -t

# Просмотр логов
tail -f /var/log/nginx/error.log
```

### Управление SSL:

```bash
# Продление сертификата
certbot renew

# Проверка сертификатов
certbot certificates

# Тестовое продление
certbot renew --dry-run
```

---

**🎉 Удачи с запуском BookHunter!**

Если всё сделано правильно, ваш проект будет работать на:
- **Основной сайт:** https://mybook-hunter.ru
- **Telegram Mini App:** https://mybook-hunter.store/telegram
