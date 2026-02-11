# 🚀 Инструкция по деплою BookHunter на сервер

Полное руководство по развертыванию BookHunter на Ubuntu/Debian сервере с Docker.

---

## 📋 Требования к серверу

### Минимальная конфигурация:
- **CPU:** 2 ядра
- **RAM:** 4 GB
- **Disk:** 20 GB SSD
- **OS:** Ubuntu 20.04+ / Debian 11+

### Программное обеспечение:
- Docker 20.10+
- Docker Compose 2.0+
- Git
- Nginx (опционально, для SSL)

---

## 🚀 Быстрый деплой (5 минут)

### 1. Подключение к серверу

```bash
ssh user@your-server-ip
```

### 2. Установка Docker и Docker Compose

```bash
# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Установка Docker Compose
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Добавление пользователя в группу docker
sudo usermod -aG docker $USER
newgrp docker
```

### 3. Клонирование проекта

```bash
# Клонирование репозитория
git clone https://github.com/YOUR_USERNAME/BookHunter.git
cd BookHunter

# Или загрузка через SCP (если локально)
scp -r ./BookHunter user@your-server-ip:/home/user/
```

### 4. Настройка переменных окружения

```bash
# Копирование примера .env
cp .env.example .env

# Редактирование .env
nano .env
```

**Обязательные изменения в .env:**
```env
# База данных
POSTGRES_PASSWORD=your_secure_password_here

# Redis
REDIS_PASSWORD=your_redis_password_here

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Google Sheets
GOOGLE_SHEET_ID=your_sheet_id_here

# Админ-панель
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_admin_password_here

# Mini App URL (ОБЯЗАТЕЛЬНО!)
MINI_APP_URL=https://yourdomain.com/telegram

# CORS
ALLOWED_ORIGINS=https://yourdomain.com
ALLOWED_HOSTS=yourdomain.com

# Отключение debug режима
DEBUG=False
```

### 5. Загрузка Google Credentials

```bash
# Создайте файл credentials.json с ключом сервисного аккаунта
# Загрузите его на сервер:
scp credentials.json user@your-server-ip:/home/user/BookHunter/

# Или создайте прямо на сервере:
nano credentials.json
```

### 6. Запуск приложения

```bash
# Запуск контейнеров
docker compose up -d

# Проверка статуса
docker compose ps

# Просмотр логов
docker compose logs -f app
```

### 7. Настройка Telegram Bot

1. Перейдите к [@BotFather](https://t.me/BotFather)
2. Откройте вашего бота
3. Настройте Web App:
   ```
   /setmenubutton
   Выберите вашего бота
   /newapps
   Текст кнопки: 📚 BookHunter
   URL: https://yourdomain.com/telegram
   ```

---

## 🔒 Настройка SSL/HTTPS (Let's Encrypt)

### Вариант 1: Через Nginx Proxy Manager

```bash
# Запуск Nginx Proxy Manager
docker run -d \
  --name npm \
  -p 80:80 \
  -p 443:443 \
  -p 81:81 \
  -v npm_data:/data \
  -v npm_letsencrypt:/etc/letsencrypt \
  jc21/nginx-proxy-manager:latest
```

1. Откройте `http://your-server-ip:81`
2. Войдите (default: admin@example.com / changeme)
3. Добавьте прокси:
   - Domain Names: `yourdomain.com`
   - Forward Hostname: `app` (имя контейнера)
   - Forward Port: `8000`
   - Enable SSL: Let's Encrypt

### Вариант 2: Через Certbot

```bash
# Установка Certbot
sudo apt-get install certbot python3-certbot-nginx

# Получение сертификата
sudo certbot --nginx -d yourdomain.com

# Автоматическое обновление
sudo crontab -e
# Добавьте строку:
0 3 * * * certbot renew --quiet
```

---

## 🔄 Обновление проекта

### Через Git

```bash
# Подключение к серверу
ssh user@your-server-ip

# Переход в директорию проекта
cd BookHunter

# Получение обновлений
git pull origin main

# Остановка контейнеров
docker compose down

# Пересборка и запуск
docker compose up -d --build

# Проверка статуса
docker compose ps
```

### Скрипт автоматического обновления

Создайте файл `update.sh`:

```bash
#!/bin/bash
echo "🔄 Обновление BookHunter..."

# Получение обновлений
git pull origin main

# Остановка контейнеров
docker compose down

# Пересборка и запуск
docker compose up -d --build

# Очистка старых образов
docker image prune -f

echo "✅ Обновление завершено!"
```

Сделайте исполняемым:
```bash
chmod +x update.sh
./update.sh
```

---

## 📊 Мониторинг

### Просмотр логов

```bash
# Логи приложения
docker compose logs -f app

# Логи всех сервисов
docker compose logs -f

# Логи за последние 100 строк
docker compose logs --tail=100 app
```

### Проверка здоровья

```bash
# Проверка статуса контейнеров
docker compose ps

# Проверка API
curl https://yourdomain.com/api/health

# Проверка админ-панели
curl https://yourdomain.com/admin/api/stats
```

---

## 🐛 Решение проблем

### Контейнер не запускается

```bash
# Просмотр логов
docker compose logs app

# Перезапуск контейнера
docker compose restart app

# Пересборка
docker compose up -d --build
```

### Ошибка подключения к базе данных

```bash
# Проверка статуса PostgreSQL
docker compose logs postgres

# Перезапуск PostgreSQL
docker compose restart postgres

# Проверка подключения
docker compose exec postgres psql -U bookuser -d book_discounts
```

### Проблемы с Redis

```bash
# Проверка Redis
docker compose logs redis

# Перезапуск Redis
docker compose restart redis

# Проверка подключения
docker compose exec redis redis-cli ping
```

### Очистка и сброс

```bash
# Полный сброс проекта (удалит все данные!)
docker compose down -v

# Удаление старых образов
docker system prune -a

# Запуск с нуля
docker compose up -d
```

---

## 🔐 Безопасность

### Настройка Firewall

```bash
# Разрешить SSH, HTTP, HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Включить firewall
sudo ufw enable

# Проверка статуса
sudo ufw status
```

### Резервное копирование

```bash
# Создание скрипта бэкапа
nano backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/backups/bookhunter"
DATE=$(date +%Y%m%d_%H%M%S)

# Создание директории
mkdir -p $BACKUP_DIR

# Бэкап базы данных
docker compose exec -T postgres pg_dump -U bookuser book_discounts > $BACKUP_DIR/db_$DATE.sql

# Бэкап файлов
tar -czf $BACKUP_DIR/files_$DATE.tar.gz .env credentials.json

# Удаление старых бэкапов (старше 7 дней)
find $BACKUP_DIR -type f -mtime +7 -delete

echo "✅ Бэкап создан: $BACKUP_DIR/db_$DATE.sql"
```

Добавьте в cron:
```bash
crontab -e
# Каждый день в 2 часа ночи
0 2 * * * /home/user/BookHunter/backup.sh
```

---

## 📈 Масштабирование

### Увеличение ресурсов

Отредактируйте `docker-compose.yml`:

```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
```

### Балансировка нагрузки

Для высокой нагрузки используйте несколько инстансов:

```yaml
services:
  app:
    deploy:
      replicas: 3
```

---

## ✅ Проверка после деплоя

1. **Главная страница:** https://yourdomain.com/web
2. **API Health:** https://yourdomain.com/api/health
3. **Админ-панель:** https://yourdomain.com/admin
4. **Mini App:** https://yourdomain.com/telegram
5. **Telegram Bot:** Отправьте /start боту

---

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи: `docker compose logs`
2. Проверьте статус: `docker compose ps`
3. Проверьте .env файл
4. Свяжитесь с поддержкой

---

**Удачи с деплоем!** 🚀
