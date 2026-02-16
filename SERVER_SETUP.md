# Быстрая настройка на сервере

## Ты сейчас здесь
Ты склонировал репозиторий в `/root/hickmet/tour_code/tour_code` (вложенная папка)

## Шаг 1: Перейти в правильную директорию

```bash
cd /root/hickmet/tour_code/tour_code
pwd  # Должно показать /root/hickmet/tour_code/tour_code
ls   # Должны увидеть: backend, frontend, db, docker-compose.yml, docker-compose.prod.yml
```

## Шаг 2: Создать backend/.env

```bash
# Проверить что backend/.env.example существует
ls -la backend/.env.example

# Скопировать example в .env
cp backend/.env.example backend/.env

# Открыть для редактирования
nano backend/.env
```

### Обязательные изменения в backend/.env:

Найди и измени эти строки:

```bash
# === DATABASE === (оставить как есть для Docker)
DATABASE_URL=postgresql+psycopg2://postgres:postgres@postgres:5432/hickmet

# === REDIS === (оставить как есть для Docker)
REDIS_URL=redis://redis:6379/0

# === SECRET KEY === ОБЯЗАТЕЛЬНО ИЗМЕНИТЬ!
SECRET_KEY=ВАШ_СЛУЧАЙНЫЙ_СЕКРЕТНЫЙ_КЛЮЧ_МИНИМУМ_50_СИМВОЛОВ_1234567890

# === DISPATCH === ВАЖНО!
DISPATCH_TARGET_URL=http://test.fondkamkor.kz
# Или для прода: https://fondkamkor.kz

# РЕАЛЬНЫЕ ДАННЫЕ ДЛЯ АВТОРИЗАЦИИ В QAMQOR
DISPATCH_AGENT_LOGIN=ваш_логин
DISPATCH_AGENT_PASS=ваш_пароль

# === GOOGLE SHEETS ===
GOOGLE_SHEETS_CREDENTIALS_FILE=/app/backend/credentials/credentials.json
```

**Сохранить:** `Ctrl+O`, `Enter`, выйти `Ctrl+X`

## Шаг 3: Создать credentials.json

```bash
# Создать папку credentials
mkdir -p backend/credentials

# Создать файл credentials.json
nano backend/credentials/credentials.json
```

Вставить JSON от Google Cloud Console (скопируй из локального файла):

```json
{
  "type": "service_account",
  "project_id": "ваш-project-id",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "...",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "..."
}
```

**Сохранить:** `Ctrl+O`, `Enter`, выйти `Ctrl+X`

## Шаг 4: Проверить что docker-compose.prod.yml существует

```bash
ls -la docker-compose.prod.yml
```

Если файла нет — создать:

```bash
nano docker-compose.prod.yml
```

И вставить содержимое из `/Users/muslimakosmagambetova/Downloads/Tour_code/docker-compose.prod.yml` (скопируй из локального репозитория).

## Шаг 5: Собрать и запустить

```bash
# Убедиться что ты в правильной папке
pwd  # Должно быть /root/hickmet/tour_code/tour_code

# Проверить структуру
ls -la  # Должны быть: backend/, frontend/, db/, docker-compose.prod.yml

# Собрать образы
docker compose -f docker-compose.prod.yml build --no-cache

# Запустить контейнеры
docker compose -f docker-compose.prod.yml up -d

# Проверить статус
docker compose -f docker-compose.prod.yml ps
```

## Шаг 6: Проверить логи

```bash
# Все логи
docker compose -f docker-compose.prod.yml logs -f

# Только backend
docker compose -f docker-compose.prod.yml logs -f backend

# Только worker
docker compose -f docker-compose.prod.yml logs -f worker
```

Должны увидеть:
```
✅ PostgreSQL подключен
✅ Приложение запущено
INFO:     Application startup complete.
```

## Шаг 7: Проверить health endpoint

```bash
curl http://localhost:8001/health
```

Должен вернуть:
```json
{"status":"healthy","database":"connected","version":"1.0.0"}
```

## Шаг 8: Настроить Caddy

```bash
# Подключить Caddy к Tour Code network
docker network connect tour_code_tour_code_network caddy

# Отредактировать Caddyfile
cd /root/hickmet/bull_project
nano Caddyfile
```

Добавить блок:

```caddyfile
hickmet.duckdns.org {
  reverse_proxy api:8000
}

tourcode.hickmet.duckdns.org {
  reverse_proxy tour_code_frontend:80
}
```

**Сохранить:** `Ctrl+O`, `Enter`, выйти `Ctrl+X`

Перезагрузить Caddy:

```bash
docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```

## Шаг 9: Проверить через браузер

Открыть:
```
https://tourcode.hickmet.duckdns.org
```

---

## Если что-то пошло не так

### Контейнеры не запускаются

```bash
cd /root/hickmet/tour_code/tour_code
docker compose -f docker-compose.prod.yml logs backend
```

### PostgreSQL ошибка

```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U postgres -d hickmet -c "\dt"
```

### Caddy не видит контейнеры

```bash
# Проверить что Caddy в сети
docker network inspect tour_code_tour_code_network | grep caddy

# Если нет — подключить
docker network connect tour_code_tour_code_network caddy
```

### Остановить всё и перезапустить

```bash
cd /root/hickmet/tour_code/tour_code
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d --force-recreate
```

---

## Полезные команды

```bash
# Статус
docker compose -f docker-compose.prod.yml ps

# Логи
docker compose -f docker-compose.prod.yml logs -f backend

# Перезапустить backend
docker compose -f docker-compose.prod.yml restart backend

# Зайти внутрь контейнера
docker compose -f docker-compose.prod.yml exec backend bash

# Проверить БД
docker compose -f docker-compose.prod.yml exec postgres psql -U postgres -d hickmet

# Использование ресурсов
docker stats
```
