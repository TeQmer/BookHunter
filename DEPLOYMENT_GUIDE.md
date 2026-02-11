# 🚀 Руководство по развертыванию BookHunter в интернете

Полное руководство по запуску приложения на сервере с собственным доменом для работы Telegram Mini App.

---

## 📋 Содержание

1. [Что нужно для запуска](#что-нужно-для-запуска)
2. [Выбор сервера](#выбор-сервера)
3. [Выбор домена](#выбор-домена)
4. [Настройка DNS](#настройка-dns)
5. [Подготовка сервера](#подготовка-сервера)
6. [Настройка приложения](#настройка-приложения)
7. [Настройка Nginx и SSL](#настройка-nginx-и-ssl)
8. [Настройка Telegram Bot](#настройка-telegram-bot)
9. [Запуск приложения](#запуск-приложения)
10. [Проверка работы](#проверка-работы)

---

## 1. Что нужно для запуска

### Обязательно:

- ✅ **Сервер** (VPS/VDS)
- ✅ **Домен** (например, `bookhunter.ru`)
- ✅ **SSL сертификат** (бесплатный Let's Encrypt)
- ✅ **Telegram Bot Token** (через @BotFather)

### Желательно:

- 📊 **Мониторинг** (UptimeRobot, Sentry)
- 💾 **Бэкапы** (автоматические)
- 🔒 **Firewall** (настроенный)

---

## 2. Выбор сервера

### Рекомендуемые провайдеры:

| Провайдер | Минимальная конфигурация | Цена | Подходит для |
|-----------|------------------------|------|--------------|
| **Timeweb** | 2 CPU, 4 GB RAM, 40 GB SSD | ~300 ₽/мес | Начало |
| **Beget** | 2 CPU, 4 GB RAM, 50 GB SSD | ~350 ₽/мес | Начало |
| **Reg.ru** | 2 CPU, 4 GB RAM, 40 GB SSD | ~400 ₽/мес | Начало |
| **DigitalOcean** | 2 CPU, 4 GB RAM, 80 GB SSD | ~$20/мес | Проект |
| **Hetzner** | 2 CPU, 4 GB RAM, 80 GB SSD | ~€10/мес | Проект |

### Минимальные требования:

```
CPU: 2 ядра
RAM: 4 ГБ
Диск: 40 ГБ SSD
ОС: Ubuntu 22.04 LTS или Debian 12
```

### Почему нужен сервер?

- ❌ **Нельзя** запустить на домашнем компьютере (нет статического IP, нет HTTPS)
- ❌ **Нельзя** использовать бесплатные хостинги (нет Docker, нет PostgreSQL)
- ✅ **Нужен** VPS/VDS сервер с доступом по SSH

---

## 3. Выбор домена

### Где купить домен:

| Регистратор | Цена .ru | Цена .com | Рекомендация |
|-------------|----------|-----------|--------------|
| **Reg.ru** | 200 ₽/год | 1000 ₽/год | ✅ Рекомендую |
| **Nic.ru** | 250 ₽/год | 1200 ₽/год | ✅ Рекомендую |
| **2domains** | 150 ₽/год | 900 ₽/год | ✅ Дешево |
| **Timeweb** | 200 ₽/год | 1000 ₽/год | ✅ Удобно |

### Рекомендации по выбору домена:

- ✅ **.ru** — дешевле, быстрее для РФ
- ✅ **Короткий** — легко запомнить
- ✅ **Латиница** — `bookhunter.ru` (не `букстракер.рф`)
- ✅ **Без цифр** — `books.ru` (не `books123.ru`)

### Примеры хороших доменов:

- `bookhunter.ru`
- `skidkiknig.ru`
- `bookmonitor.ru`
- `bookdeals.ru`

---

## 4. Настройка DNS

### Шаг 4.1: Купите домен

1. Зарегистрируйтесь на регистраторе (например, Reg.ru)
2. Купите домен
3. Получите доступ к панели управления DNS

### Шаг 4.2: Получите IP адрес сервера

После покупки сервера вам пришлют:
- IP адрес: `123.45.67.89`
- Доступы SSH: `root@123.45.67.89`

### Шаг 4.3: Настройте DNS записи

В панели управления доменом добавьте:

```
Тип: A
Имя: @ (или ваше доменное имя)
Значение: 123.45.67.89 (IP вашего сервера)
TTL: 3600
```

```
Тип: A
Имя: www
Значение: 123.45.67.89 (IP вашего сервера)
TTL: 3600
```

### Шаг 4.4: Проверьте DNS

Перейдите на [https://www.nslookup.io/](https://www.nslookup.io/) и проверьте:

```
bookhunter.ru → 123.45.67.89
www.bookhunter.ru → 123.45.67.89
```

⚠️ **Важно:** DNS обновляется от 1 до 24 часов!

---

## 5. Подготовка сервера

### Шаг 5.1: Подключитесь к серверу

```bash
ssh root@123.45.67.89
```

### Шаг 5.2: Обновите систему

```bash
apt update && apt upgrade -y
```

### Шаг 5.3: Установите необходимое ПО

```bash
# Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Nginx
apt install nginx -y

# Certbot (для SSL)
apt install certbot python3-certbot-nginx -y

# Git
apt install git -y
```

### Шаг 5.4: Создайте директорию для проекта

```bash
mkdir -p /var/www/bookhunter
cd /var/www/bookhunter
```

### Шаг 5.5: Склонируйте проект

```bash
# Если проект на GitHub
git clone https://github.com/ваш-юзернейм/bookhunter.git .

# Или загрузите файлы через SFTP
```

### Шаг 5.6: Настройте firewall

```bash
# Разрешите SSH, HTTP, HTTPS
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

---

## 6. Настройка приложения

### Шаг 6.1: Создайте файл `.env`

```bash
nano .env
```

### Шаг 6.2: Добавьте следующее содержимое:

```env
# ========== БАЗА ДАННЫХ ==========
DATABASE_URL=postgresql+asyncpg://bookuser:СЛОЖНЫЙ_ПАРОЛЬ_БД@postgres:5432/book_discounts
POSTGRES_USER=bookuser
POSTGRES_PASSWORD=СЛОЖНЫЙ_ПАРОЛЬ_БД

# ========== REDIS ==========
REDIS_URL=redis://:СЛОЖНЫЙ_ПАРОЛЬ_REDIS@redis:6379/0
REDIS_PASSWORD=СЛОЖНЫЙ_ПАРОЛЬ_REDIS

# ========== GOOGLE SHEETS ==========
GOOGLE_SHEETS_CREDENTIALS_PATH=credentials.json
GOOGLE_SHEET_ID=ваш_id_google_таблицы

# ========== TELEGRAM BOT ==========
TELEGRAM_BOT_TOKEN=ваш_токен_бота

# ========== TELEGRAM MINI APP ==========
MINI_APP_URL=https://bookhunter.ru/telegram

# ========== БЕЗОПАСНОСТЬ ==========
SECRET_KEY=СЛОЖНЫЙ_СЕКРЕТНЫЙ_КЛЮЧ
ALGORITHM=HS256
ADMIN_USERNAME=admin
ADMIN_PASSWORD=СЛОЖНЫЙ_ПАРОЛЬ_АДМИНА

# ========== CORS ==========
ALLOWED_ORIGINS=https://bookhunter.ru,https://www.bookhunter.ru,https://t.me,https://web.telegram.org
ALLOWED_HOSTS=bookhunter.ru,www.bookhunter.ru

# ========== НАСТРОЙКИ ПРИЛОЖЕНИЯ ==========
APP_NAME=BookHunter
DEBUG=False
LOG_LEVEL=INFO

# ========== CELERY ==========
CELERY_BROKER_URL=redis://:СЛОЖНЫЙ_ПАРОЛЬ_REDIS@redis:6379/0
CELERY_RESULT_BACKEND=redis://:СЛОЖНЫЙ_ПАРОЛЬ_REDIS@redis:6379/0
```

### Шаг 6.3: Сгенерируйте сложные пароли

```bash
# Генерация пароля для БД
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Генерация пароля для Redis
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Генерация SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Замените `СЛОЖНЫЙ_ПАРОЛЬ` на сгенерированные значения!

### Шаг 6.4: Разместите файл `credentials.json`

```bash
# Создайте файл credentials.json с вашим Google Service Account ключом
nano credentials.json
```

Вставьте содержимое вашего `credentials.json` (полученный из Google Cloud Console).

⚠️ **Важно:** Убедитесь, что `credentials.json` НЕ в Git!

---

## 7. Настройка Nginx и SSL

### Шаг 7.1: Создайте конфигурацию Nginx

```bash
nano /etc/nginx/sites-available/bookhunter
```

### Шаг 7.2: Добавьте следующее содержимое:

```nginx
# HTTP (перенаправление на HTTPS)
server {
    listen 80;
    server_name bookhunter.ru www.bookhunter.ru;

    # Перенаправляем все на HTTPS
    return 301 https://$server_name$request_uri;
}

# HTTPS
server {
    listen 443 ssl http2;
    server_name bookhunter.ru www.bookhunter.ru;

    # SSL сертификаты (будут созданы Certbot)
    ssl_certificate /etc/letsencrypt/live/bookhunter.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bookhunter.ru/privkey.pem;

    # SSL настройки
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Заголовки безопасности
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Логи
    access_log /var/log/nginx/bookhunter_access.log;
    error_log /var/log/nginx/bookhunter_error.log;

    # Прокси на FastAPI приложение
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket поддержка
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Статические файлы
    location /static {
        alias /var/www/bookhunter/web/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Telegram Mini App
    location /telegram {
        alias /var/www/bookhunter/telegram/app;
        try_files $uri $uri/ /index.html;
    }
}
```

### Шаг 7.3: Активируйте конфигурацию

```bash
ln -s /etc/nginx/sites-available/bookhunter /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default
```

### Шаг 7.4: Проверьте конфигурацию Nginx

```bash
nginx -t
```

Должно быть: `syntax is ok` и `test is successful`

### Шаг 7.5: Перезапустите Nginx

```bash
systemctl restart nginx
```

---

## 8. Получение SSL сертификата

### Шаг 8.1: Получите бесплатный SSL сертификат

```bash
certbot --nginx -d bookhunter.ru -d www.bookhunter.ru
```

Ответьте на вопросы:
1. Email для уведомлений: `ваш@email.com`
2. Согласие с условиями: `Y`
3. Перенаправление HTTP на HTTPS: `2`

### Шаг 8.2: Проверьте автоматическое обновление

```bash
certbot renew --dry-run
```

### Шаг 8.3: Добавьте автообновление в cron

```bash
crontab -e
```

Добавьте строку:

```
0 3 * * * certbot renew --quiet && systemctl reload nginx
```

---

## 9. Настройка Telegram Bot

### Шаг 9.1: Создайте бота через @BotFather

1. Откройте Telegram: [@BotFather](https://t.me/BotFather)
2. Отправьте: `/newbot`
3. Введите имя бота: `bookhunter Bot`
4. Введите username бота: `bookhunter_bot`
5. Сохраните полученный токен: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`

### Шаг 9.2: Настройте Web App

Отправьте @BotFather:

```
/mybots
```

Выберите вашего бота → **Bot Settings** → **Menu Button** → **Setup Menu Button**

Текст кнопки:
```
📚 Открыть приложение
```

URL Web App:
```
https://bookhunter.ru/telegram
```

### Шаг 9.3: Добавьте токен в `.env`

Откройте `.env` и замените:

```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

---

## 10. Запуск приложения

### Шаг 10.1: Запустите Docker Compose

```bash
docker-compose up -d
```

### Шаг 10.2: Проверьте статус контейнеров

```bash
docker-compose ps
```

Все контейнеры должны быть `Up`

### Шаг 10.3: Проверьте логи

```bash
docker-compose logs -f app
```

### Шаг 10.4: Запустите Telegram бота

```bash
docker-compose exec telegram_bot python /app/app/run_bot.py
```

Или запустите как демон:

```bash
docker-compose up -d telegram_bot
```

---

## 11. Проверка работы

### Шаг 11.1: Проверьте веб-сайт

Откройте в браузере:

- ✅ `http://bookhunter.ru` → должен перенаправить на HTTPS
- ✅ `https://bookhunter.ru` → должен открыться сайт
- ✅ `https://bookhunter.ru/telegram` → должен открыться Mini App
- ✅ `https://bookhunter.ru/admin` → админ-панель (требует авторизацию)

### Шаг 11.2: Проверьте SSL

Перейдите на [https://www.ssllabs.com/ssltest/](https://www.ssllabs.com/ssltest/) и проверьте ваш домен.

Должно быть **A+** или **A**.

### Шаг 11.3: Проверьте Telegram Bot

1. Откройте вашего бота в Telegram
2. Нажмите `/start`
3. Нажмите кнопку "📚 Открыть приложение"
4. Mini App должен открыться!

### Шаг 11.4: Проверьте API

```bash
curl https://bookhunter.ru/api/health
```

Должен вернуться JSON с информацией о здоровье системы.

---

## 📋 Чек-лист перед запуском

- [ ] Куплен домен
- [ ] Куплен сервер (VPS/VDS)
- [ ] Настроены DNS записи
- [ ] Установлен Docker и Docker Compose
- [ ] Установлен Nginx
- [ ] Получен SSL сертификат
- [ ] Создан `.env` файл
- [ ] Сгенерированы сложные пароли
- [ ] Размещен `credentials.json`
- [ ] Создан Telegram Bot
- [ ] Настроен Web App URL
- [ ] Запущены Docker контейнеры
- [ ] Проверен веб-сайт
- [ ] Проверен Telegram Bot

---

## 🔧 Полезные команды

### Просмотр логов:

```bash
# Все контейнеры
docker-compose logs -f

# Только приложение
docker-compose logs -f app

# Только Telegram бот
docker-compose logs -f telegram_bot
```

### Перезапуск контейнеров:

```bash
# Все
docker-compose restart

# Только приложение
docker-compose restart app

# Только бот
docker-compose restart telegram_bot
```

### Остановка контейнеров:

```bash
docker-compose down
```

### Обновление приложения:

```bash
git pull
docker-compose down
docker-compose up -d --build
```

### Проверка дискового пространства:

```bash
df -h
```

### Проверка использования RAM:

```bash
free -h
```

---

## 🚨 Решение проблем

### Проблема: Сайт не открывается

**Решение:**

1. Проверьте Nginx:
```bash
systemctl status nginx
```

2. Проверьте Docker:
```bash
docker-compose ps
```

3. Проверьте логи:
```bash
docker-compose logs app
```

### Проблема: SSL сертификат не работает

**Решение:**

```bash
certbot --nginx -d bookhunter.ru -d www.bookhunter.ru --force-renewal
```

### Проблема: Telegram Bot не отвечает

**Решение:**

1. Проверьте токен в `.env`
2. Проверьте логи бота:
```bash
docker-compose logs telegram_bot
```

3. Перезапустите бота:
```bash
docker-compose restart telegram_bot
```

### Проблема: Mini App не открывается в Telegram

**Решение:**

1. Проверьте `MINI_APP_URL` в `.env`:
```env
MINI_APP_URL=https://bookhunter.ru/telegram
```

2. Проверьте `ALLOWED_ORIGINS`:
```env
ALLOWED_ORIGINS=https://bookhunter.ru,https://t.me,https://web.telegram.org
```

3. Проверьте Web App URL в @BotFather

---

## 📚 Дополнительные ресурсы

- [Docker Documentation](https://docs.docker.com/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [Let's Encrypt](https://letsencrypt.org/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

## 💡 Рекомендации

### Для начала:

1. ✅ Используйте Timeweb или Beget (дешево и надежно)
2. ✅ Купите домен .ru (дешевле)
3. ✅ Используйте Ubuntu 22.04 LTS
4. ✅ Используйте Docker Compose для запуска

### Для продакшена:

1. ✅ Настройте автоматические бэкапы
2. ✅ Настройте мониторинг (Sentry, UptimeRobot)
3. ✅ Используйте CDN для статических файлов
4. ✅ Настройте логирование (ELK Stack)
5. ✅ Используйте Firewall

---

## 🎉 Поздравляем!

Если вы выполнили все шаги, ваше приложение теперь доступно в интернете и Telegram Mini App должен работать!

Если возникнут проблемы — проверьте логи и этот раздел "Решение проблем".

---

**Создано для BookHunter** 📚❤️
