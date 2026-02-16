# 🚀 План деплоя Hickmet Premium Tour Code

## Текущее состояние сервера

**IP:** 65.21.188.181
**Существующий проект:** Bull API на hickmet.duckdns.org
**Reverse proxy:** Caddy
**Занятые порты:** 80, 443, 8000, 8080, 5432 (localhost)

---

## Стратегия деплоя

- **Домен:** `tourcode.hickmet.duckdns.org` (или tours.hickmet.kz если купите домен)
- **Порты (внутренние):**
  - Backend API: `8001` (внутри Docker network)
  - Frontend: `3001` (внутри Docker network)
  - PostgreSQL: `5433` (localhost only, не конфликтует с Bull PostgreSQL на 5432)
  - Redis: `6380` (localhost only, свой Redis для Tour Code)
- **Caddy** будет проксировать:
  - `hickmet.duckdns.org` → Bull API (8000) — существующий
  - `tourcode.hickmet.duckdns.org` → Tour Code Frontend (3001) — новый

---

## Этап 1: Подготовка на локальной машине

### 1.1 Создать продакшн docker-compose

```bash
cd /Users/muslimakosmagambetova/Downloads/Tour_code
```

Создать файл `docker-compose.prod.yml` (см. ниже)

### 1.2 Подготовить .env для продакшна

Скопировать `backend/.env.example` → `backend/.env.prod` и заполнить:

```bash
cp backend/.env.example backend/.env.prod
```

Обязательно изменить:
- `SECRET_KEY` — сгенерировать новый
- `DATABASE_URL` — будет `postgresql+psycopg2://postgres:postgres@postgres:5432/hickmet`
- `REDIS_URL` — будет `redis://redis:6379/0`
- `DISPATCH_AGENT_LOGIN` / `DISPATCH_AGENT_PASS` — реальные данные для QAMQOR API
- `GOOGLE_SHEETS_CREDENTIALS_FILE` — положить credentials.json в backend/credentials/

### 1.3 Подготовить credentials

```bash
# Убедиться что credentials.json существует
ls -la backend/credentials/credentials.json
```

Если нет — получить из Google Cloud Console и положить туда.

---

## Этап 2: Подготовка на сервере

### 2.1 SSH подключение

```bash
ssh root@65.21.188.181
```

### 2.2 Создать директорию для Tour Code

```bash
mkdir -p /root/hickmet/tour_code
cd /root/hickmet/tour_code
```

### 2.3 Установить Git (если нет)

```bash
git --version || apt update && apt install -y git
```

---

## Этап 3: Загрузка кода на сервер

**Вариант A: Через Git (рекомендуется)**

Если код в GitHub/GitLab:

```bash
cd /root/hickmet/tour_code
git clone <ваш-репозиторий> .
```

**Вариант B: Через scp с локальной машины**

С локальной машины:

```bash
cd /Users/muslimakosmagambetova/Downloads/Tour_code

# Архивировать проект (исключая node_modules, venv, __pycache__)
tar -czf tour_code.tar.gz \
  --exclude=node_modules \
  --exclude=venv \
  --exclude=frontend/venv \
  --exclude=__pycache__ \
  --exclude=*.pyc \
  --exclude=.git \
  --exclude=hickmet.db \
  --exclude=backend/uploads \
  --exclude=frontend/dist \
  .

# Загрузить на сервер
scp tour_code.tar.gz root@65.21.188.181:/root/hickmet/tour_code/

# На сервере распаковать
ssh root@65.21.188.181
cd /root/hickmet/tour_code
tar -xzf tour_code.tar.gz
rm tour_code.tar.gz
```

---

## Этап 4: Настройка docker-compose.prod.yml на сервере

Файл уже должен быть в репозитории. Если нет — создать на сервере:

```bash
cd /root/hickmet/tour_code
nano docker-compose.prod.yml
```

Вставить содержимое (см. файл docker-compose.prod.yml в этой папке)

---

## Этап 5: Настройка .env.prod

```bash
cd /root/hickmet/tour_code
nano backend/.env
```

Заполнить все переменные (см. backend/.env.example).

**ВАЖНО:** Изменить:
- `SECRET_KEY` на случайную строку
- `DISPATCH_AGENT_LOGIN` / `DISPATCH_AGENT_PASS` — реальные данные
- `GOOGLE_SHEETS_CREDENTIALS_FILE=/app/backend/credentials/credentials.json`

---

## Этап 6: Загрузка credentials.json

С локальной машины:

```bash
scp /Users/muslimakosmagambetova/Downloads/Tour_code/backend/credentials/credentials.json \
  root@65.21.188.181:/root/hickmet/tour_code/backend/credentials/
```

Или создать на сервере:

```bash
mkdir -p /root/hickmet/tour_code/backend/credentials
nano /root/hickmet/tour_code/backend/credentials/credentials.json
# Вставить JSON из Google Cloud
```

---

## Этап 7: Настройка Caddy для Tour Code

### 7.1 Добавить поддомен в DuckDNS (или купить домен)

Зайти на https://www.duckdns.org и создать поддомен `tourcode` (станет `tourcode.hickmet.duckdns.org`)

Или если есть домен `hickmet.kz` — создать A-запись:
```
tours.hickmet.kz → 65.21.188.181
```

### 7.2 Обновить Caddyfile

```bash
cd /root/hickmet/bull_project
nano Caddyfile
```

Добавить новый блок:

```caddyfile
hickmet.duckdns.org {
  reverse_proxy api:8000
}

tourcode.hickmet.duckdns.org {
  reverse_proxy tour_code_frontend:80
}
```

Или если используете `tours.hickmet.kz`:

```caddyfile
hickmet.duckdns.org {
  reverse_proxy api:8000
}

tours.hickmet.kz {
  reverse_proxy tour_code_frontend:80
}
```

### 7.3 Перезагрузить Caddy

```bash
docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```

---

## Этап 8: Запуск Tour Code

```bash
cd /root/hickmet/tour_code

# Пересобрать образы
docker compose -f docker-compose.prod.yml build --no-cache

# Запустить всё
docker compose -f docker-compose.prod.yml up -d

# Проверить статус
docker compose -f docker-compose.prod.yml ps

# Логи
docker compose -f docker-compose.prod.yml logs -f backend worker
```

---

## Этап 9: Подключить Caddy к Tour Code network

Caddy должен видеть контейнер `tour_code_frontend`:

```bash
# Найти имя Tour Code network
docker network ls | grep tour_code

# Подключить Caddy к Tour Code network
docker network connect tour_code_tour_code_network caddy

# Перезагрузить Caddy
docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```

---

## Этап 10: Проверка

### 10.1 Проверить что контейнеры запустились

```bash
docker compose -f docker-compose.prod.yml ps
```

Должны быть:
- `tour_code_postgres` — UP (healthy)
- `tour_code_redis` — UP (healthy)
- `tour_code_backend` — UP
- `tour_code_worker` — UP
- `tour_code_frontend` — UP

### 10.2 Проверить логи бэкенда

```bash
docker compose -f docker-compose.prod.yml logs backend | tail -50
```

Должны увидеть:
```
✅ PostgreSQL подключен
✅ Приложение запущено
INFO:     Application startup complete.
```

### 10.3 Проверить health endpoint

```bash
curl http://localhost:8001/health
```

Должен вернуть:
```json
{"status":"healthy","database":"connected","version":"1.0.0"}
```

### 10.4 Проверить Swagger API

```bash
curl http://localhost:8001/docs
```

### 10.5 Проверить frontend

```bash
curl http://localhost:3001
```

### 10.6 Проверить через Caddy (публичный домен)

```bash
curl https://tourcode.hickmet.duckdns.org
```

Или открыть в браузере:
```
https://tourcode.hickmet.duckdns.org
```

---

## Этап 11: Настройка автозапуска

Docker уже настроен на `restart: unless-stopped`, поэтому контейнеры будут автоматически запускаться при перезагрузке сервера.

Проверить:

```bash
docker inspect tour_code_backend | grep -i restart
```

Должно быть: `"RestartPolicy": {"Name": "unless-stopped"}`

---

## Этап 12: Мониторинг

### 12.1 Логи в реальном времени

```bash
docker compose -f docker-compose.prod.yml logs -f
```

### 12.2 Использовать Dozzle (уже установлен на сервере)

Открыть http://65.21.188.181:8080 — увидите все контейнеры включая Tour Code.

### 12.3 Проверка использования ресурсов

```bash
docker stats
```

---

## Этап 13: Бэкапы PostgreSQL

Настроить автоматические бэкапы БД:

```bash
# Создать директорию для бэкапов
mkdir -p /root/backups/tour_code

# Создать скрипт бэкапа
nano /root/backups/backup_tour_code.sh
```

Вставить:

```bash
#!/bin/bash
BACKUP_DIR="/root/backups/tour_code"
DATE=$(date +%Y%m%d_%H%M%S)
CONTAINER="tour_code_postgres"

docker exec $CONTAINER pg_dump -U postgres hickmet > "$BACKUP_DIR/hickmet_$DATE.sql"

# Удалить бэкапы старше 7 дней
find $BACKUP_DIR -name "hickmet_*.sql" -mtime +7 -delete

echo "Backup completed: hickmet_$DATE.sql"
```

Сделать исполняемым:

```bash
chmod +x /root/backups/backup_tour_code.sh
```

Добавить в crontab (запуск каждый день в 3 часа ночи):

```bash
crontab -e
```

Добавить строку:

```
0 3 * * * /root/backups/backup_tour_code.sh >> /root/backups/tour_code/backup.log 2>&1
```

---

## Troubleshooting

### Контейнер не запускается

```bash
docker compose -f docker-compose.prod.yml logs backend
```

### PostgreSQL не готов

```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U postgres -d hickmet -c "\dt"
```

### Caddy не видит Tour Code

```bash
# Проверить что Caddy в той же сети
docker network inspect tour_code_tour_code_network | grep caddy
```

Если нет — подключить:

```bash
docker network connect tour_code_tour_code_network caddy
docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```

### 502 Bad Gateway от Caddy

Проверить что backend запущен и слушает порт:

```bash
docker compose -f docker-compose.prod.yml exec backend curl http://localhost:8000/health
```

---

## Откат изменений

Если что-то пошло не так:

```bash
cd /root/hickmet/tour_code
docker compose -f docker-compose.prod.yml down
```

Caddy останется работать и будет продолжать обслуживать Bull API.

---

## Обновление кода (после деплоя)

```bash
cd /root/hickmet/tour_code

# Если через Git
git pull

# Если через scp — загрузить новый архив и распаковать

# Пересобрать и перезапустить
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d --force-recreate

# Проверить
docker compose -f docker-compose.prod.yml logs -f backend
```

---

## Полезные команды

```bash
# Статус всех контейнеров Tour Code
docker compose -f docker-compose.prod.yml ps

# Логи конкретного сервиса
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f worker
docker compose -f docker-compose.prod.yml logs -f frontend

# Остановить всё
docker compose -f docker-compose.prod.yml down

# Запустить заново
docker compose -f docker-compose.prod.yml up -d

# Пересоздать контейнеры
docker compose -f docker-compose.prod.yml up -d --force-recreate

# Зайти внутрь контейнера
docker compose -f docker-compose.prod.yml exec backend bash
docker compose -f docker-compose.prod.yml exec postgres psql -U postgres -d hickmet

# Посмотреть использование ресурсов
docker stats
```
