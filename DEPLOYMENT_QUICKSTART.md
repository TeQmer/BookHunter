# ⚡ Быстрый старт развертывания

Краткий чек-лист для быстрого запуска приложения на сервере.

---

## 📦 Что купить (примерные цены)

| Что | Где | Цена |
|-----|-----|------|
| **Сервер (VPS)** | Timeweb / Beget | ~300 ₽/мес |
| **Домен** | Reg.ru / Nic.ru | ~200 ₽/год |
| **Итого** | | ~500 ₽ в первый раз |

---

## 🚀 Пошаговый план (30 минут)

### 1️⃣ Купите домен (5 минут)

1. Перейдите на [Reg.ru](https://www.reg.ru/)
2. Зарегистрируйтесь
3. Купите домен (например, `bookhunter.ru`)
4. В панели DNS добавьте запись:
   - Тип: `A`
   - Имя: `@`
   - Значение: `(пока пустой, заполните после покупки сервера)`

### 2️⃣ Купите сервер (5 минут)

1. Перейдите на [Timeweb Cloud](https://timeweb.cloud/)
2. Зарегистрируйтесь
3. Создайте сервер:
   - ОС: **Ubuntu 22.04 LTS**
   - Тариф: **2 CPU, 4 GB RAM, 40 GB SSD**
   - Пароль: **сложный**
4. Сохраните IP адрес (например, `123.45.67.89`)

### 3️⃣ Настройте DNS (1 минута)

Вернитесь на Reg.ru → DNS → Измените запись:

```
Тип: A
Имя: @
Значение: 123.45.67.89 (IP вашего сервера)
```

### 4️⃣ Подключитесь к серверу (2 минуты)

На вашем компьютере откройте терминал:

```bash
ssh root@123.45.67.89
```

Введите пароль от сервера.

### 5️⃣ Установите Docker (5 минут)

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

apt install nginx certbot python3-certbot-nginx git -y
```

### 6️⃣ Загрузите проект (3 минуты)

```bash
mkdir -p /var/www/bookhunter
cd /var/www/bookhunter

# Если проект на GitHub:
git clone https://github.com/ваш-юзернейм/проект.git .

# Или загрузьте через SFTP/FTP
```

### 7️⃣ Настройте .env (5 минут)

```bash
nano .env
```

Вставьте и отредактируйте:

```env
# База данных
DATABASE_URL=postgresql+asyncpg://bookuser:СгенерированныйПарольБД@postgres:5432/book_discounts
POSTGRES_USER=bookuser
POSTGRES_PASSWORD=СгенерированныйПарольБД

# Redis
REDIS_PASSWORD=СгенерированныйПарольRedis

# Telegram Bot
TELEGRAM_BOT_TOKEN=ВашТокенОтBotFather

# Mini App URL (ВАЖНО!)
MINI_APP_URL=https://bookhunter.ru/telegram

# CORS (ВАЖНО!)
ALLOWED_ORIGINS=https://bookhunter.ru,https://t.me,https://web.telegram.org
ALLOWED_HOSTS=bookhunter.ru,www.bookhunter.ru

# Безопасность
SECRET_KEY=СгенерированныйСекретныйКлюч
ADMIN_USERNAME=admin
ADMIN_PASSWORD=СгенерированныйПарольАдмина
```

**Генерация паролей:**

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 8️⃣ Настройте Nginx (3 минуты)

```bash
nano /etc/nginx/sites-available/bookhunter
```

Вставьте:

```nginx
server {
    listen 80;
    server_name bookhunter.ru www.bookhunter.ru;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name bookhunter.ru www.bookhunter.ru;

    ssl_certificate /etc/letsencrypt/live/bookhunter.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bookhunter.ru/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /telegram {
        alias /var/www/bookhunter/telegram/app;
        try_files $uri $uri/ /index.html;
    }
}
```

Активируйте:

```bash
ln -s /etc/nginx/sites-available/bookhunter /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx
```

### 9️⃣ Получите SSL сертификат (2 минуты)

```bash
certbot --nginx -d bookhunter.ru -d www.bookhunter.ru
```

Ответьте:
- Email: `ваш@email.com`
- Согласие: `Y`
- Перенаправление: `2`

### 🔟 Запустите приложение (2 минуты)

```bash
docker-compose up -d
```

Проверьте статус:

```bash
docker-compose ps
```

### 1️⃣1️⃣ Настройте Telegram Bot (2 минуты)

1. Откройте [@BotFather](https://t.me/BotFather)
2. `/newbot` → `bookhunter` → `bookhunter_bot`
3. Сохраните токен
4. `/mybots` → Ваш бот → **Bot Settings** → **Menu Button**
5. Текст: `📚 Открыть приложение`
6. URL: `https://bookhunter.ru/telegram`

### 1️⃣2️⃣ Проверьте (1 минута)

Откройте в браузере:
- ✅ `https://bookhunter.ru`
- ✅ `https://bookhunter.ru/telegram`

Откройте в Telegram:
- ✅ Ваш бот → `/start` → "📚 Открыть приложение"

---

## ✅ Чек-лист

- [ ] Домен куплен
- [ ] Сервер куплен
- [ ] DNS настроен
- [ ] Docker установлен
- [ ] Проект загружен
- [ ] `.env` настроен
- [ ] Nginx настроен
- [ ] SSL получен
- [ ] Приложение запущено
- [ ] Telegram Bot настроен
- [ ] Проверен веб-сайт
- [ ] Проверен Mini App

---

## 🆘 Если не работает

### Сайт не открывается:

```bash
# Проверьте Nginx
systemctl status nginx

# Проверьте Docker
docker-compose ps

# Проверьте логи
docker-compose logs app
```

### SSL не работает:

```bash
certbot --nginx -d bookhunter.ru -d www.bookhunter.ru --force-renewal
```

### Telegram Bot не работает:

```bash
# Проверьте токен в .env
nano .env

# Проверьте логи бота
docker-compose logs telegram_bot

# Перезапустите бота
docker-compose restart telegram_bot
```

### Mini App не открывается:

Проверьте `.env`:

```env
MINI_APP_URL=https://bookhunter.ru/telegram  # Правильно?
ALLOWED_ORIGINS=https://bookhunter.ru,https://t.me  # Включен t.me?
```

---

## 📞 Поддержка

Если возникнут проблемы:

1. Проверьте логи: `docker-compose logs`
2. Проверьте этот файл: `DEPLOYMENT_GUIDE.md`
3. Напишите в поддержку хостинга

---

**Удачи с запуском!** 🚀
