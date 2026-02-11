# Настройка Google Sheets Credentials через переменные окружения

## Обзор

Этот метод позволяет хранить Google Service Account credentials в переменных окружения вместо файла `credentials.json`. Это более безопасный подход для продакшен-среды.

---

## Шаг 1: Откройте файл `credentials.json`

Найдите ваш файл `credentials.json` и откройте его в текстовом редакторе. Он должен выглядеть примерно так:

```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "1234567890abcdef",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQD...\n-----END PRIVATE KEY-----\n",
  "client_email": "your-service-account@your-project-id.iam.gserviceaccount.com",
  "client_id": "123456789012345678901",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/your-service-account%40your-project-id.iam.gserviceaccount.com"
}
```

---

## Шаг 2: Извлеките данные и добавьте в `.env`

Добавьте следующие переменные в ваш файл `.env` или `.env.prod`:

### Обязательные поля:

```bash
# Тип учетной записи (обычно "service_account")
GOOGLE_CREDENTIALS_TYPE=service_account

# ID проекта Google Cloud
GOOGLE_CREDENTIALS_PROJECT_ID=your-project-id

# ID приватного ключа
GOOGLE_CREDENTIALS_PRIVATE_KEY_ID=1234567890abcdef

# Приватный ключ (ВАЖНО: сохраните переводы строк \n как есть!)
GOOGLE_CREDENTIALS_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQD...\n-----END PRIVATE KEY-----\n"

# Email сервисного аккаунта
GOOGLE_CREDENTIALS_CLIENT_EMAIL=your-service-account@your-project-id.iam.gserviceaccount.com

# ID клиента
GOOGLE_CREDENTIALS_CLIENT_ID=123456789012345678901
```

### Опциональные поля (обычно можно оставить значения по умолчанию):

```bash
# URI для авторизации (по умолчанию)
GOOGLE_CREDENTIALS_AUTH_URI=https://accounts.google.com/o/oauth2/auth

# URI для получения токена (по умолчанию)
GOOGLE_CREDENTIALS_TOKEN_URI=https://oauth2.googleapis.com/token

# URL сертификата провайдера авторизации (по умолчанию)
GOOGLE_CREDENTIALS_AUTH_PROVIDER_CERT_URL=https://www.googleapis.com/oauth2/v1/certs

# URL клиентского сертификата
GOOGLE_CREDENTIALS_CLIENT_CERT_URL=https://www.googleapis.com/robot/v1/metadata/x509/your-service-account%40your-project-id.iam.gserviceaccount.com
```

---

## Шаг 3: Настройка ID таблицы

Не забудьте также настроить ID вашей Google таблицы:

```bash
# ID таблицы Google Sheets
GOOGLE_SHEET_ID=1BxiMVs0XRA5nFMdKvBdBZjGMUUqpt3547N0xY0k
```

ID таблицы можно найти в URL:
`https://docs.google.com/spreadsheets/d/`**`1BxiMVs0XRA5nFMdKvBdBZjGMUUqpt3547N0xY0k`**`/edit`

---

## Шаг 4: Удалите файл `credentials.json`

После настройки переменных окружения и проверки работы можно удалить файл:

```bash
rm credentials.json
```

---

## Приоритет методов

Приложение проверяет credentials в следующем порядке:

1. **Переменные окружения** (приоритетный метод)
2. **Файл credentials.json** (резервный метод)

Это означает, что если настроены переменные окружения, файл `credentials.json` использоваться не будет.

---

## Пример полного `.env` для Google Sheets

```bash
# Google Sheets - переменные окружения
GOOGLE_CREDENTIALS_TYPE=service_account
GOOGLE_CREDENTIALS_PROJECT_ID=my-book-hunter-12345
GOOGLE_CREDENTIALS_PRIVATE_KEY_ID=abc123def456
GOOGLE_CREDENTIALS_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQD...\n-----END PRIVATE KEY-----\n"
GOOGLE_CREDENTIALS_CLIENT_EMAIL=book-hunter-bot@my-book-hunter-12345.iam.gserviceaccount.com
GOOGLE_CREDENTIALS_CLIENT_ID=123456789012345678901
GOOGLE_CREDENTIALS_AUTH_URI=https://accounts.google.com/o/oauth2/auth
GOOGLE_CREDENTIALS_TOKEN_URI=https://oauth2.googleapis.com/token
GOOGLE_CREDENTIALS_AUTH_PROVIDER_CERT_URL=https://www.googleapis.com/oauth2/v1/certs
GOOGLE_CREDENTIALS_CLIENT_CERT_URL=https://www.googleapis.com/robot/v1/metadata/x509/book-hunter-bot%40my-book-hunter-12345.iam.gserviceaccount.com

# ID таблицы
GOOGLE_SHEET_ID=1BxiMVs0XRA5nFMdKvBdBZjGMUUqpt3547N0xY0k
```

---

## Важные примечания

### 🔐 Безопасность

- **Никогда не коммитите** файл `.env` в Git (он уже в `.gitignore`)
- **Не делитесь** приватным ключом (`GOOGLE_CREDENTIALS_PRIVATE_KEY`) ни с кем
- В продакшене используйте секреты вашего хостинга (Docker Secrets, AWS Secrets Manager, и т.д.)

### ⚠️ Переводы строк в приватном ключе

Приватный ключ содержит переводы строк (`\n`). Важно:

- ✅ Правильно: `GOOGLE_CREDENTIALS_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"`
- ❌ Неправильно: `GOOGLE_CREDENTIALS_PRIVATE_KEY="-----BEGIN PRIVATE KEY----- ... -----END PRIVATE KEY-----"`

Символы `\n` должны быть сохранены как есть, они будут преобразованы в реальные переводы строк при чтении переменной окружения.

### 🧪 Тестирование

После настройки переменных окружения можно проверить работу:

```bash
# Запустите приложение
python main.py

# Проверьте логи на наличие:
# "Credentials загружены из переменных окружения"
# "Google Sheets инициализирован успешно"
```

---

## Устранение проблем

### Ошибка: "Не удалось загрузить credentials"

**Причины:**
1. Не все обязательные поля заполнены
2. Приватный ключ имеет неправильный формат
3. Переменные окружения не загружены

**Решение:**
1. Проверьте, что все обязательные поля заполнены
2. Убедитесь, что в приватном ключе сохранены символы `\n`
3. Перезагрузите приложение после изменения переменных окружения

### Ошибка: "Invalid grant"

**Причина:** Неверный формат приватного ключа

**Решение:** Убедитесь, что приватный ключ заключен в кавычки и содержит символы `\n` для переводов строк

---

## Дополнительная информация

- [Создание Service Account в Google Cloud](https://cloud.google.com/iam/docs/creating-managing-service-accounts)
- [Подключение Google Sheets к Service Account](https://docs.gspread.org/en/latest/oauth2.html#for-bots-using-service-account)
