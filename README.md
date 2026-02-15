
## Структура проекта

```text
Tour_code/
├── backend/                 # FastAPI + Celery
├── frontend/                # React + Vite
├── db/                      # SQLAlchemy модели + schema.sql
├── docker-compose.dev.yml   # PostgreSQL + Redis + pgAdmin + Redis Commander
└── requirements.txt         # Python зависимости (вынесены в корень)
```

### 3. Установить Python зависимости

Из корня проекта:

```bash
python3 -m venv backend/venv
source backend/venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Установить frontend зависимости

```bash
cd frontend
npm install
cd ..
```

### 5. Запустить backend API

Терминал 1:

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API будет доступен на:

- `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

### 6. Запустить Celery worker

Терминал 2:

```bash
cd backend
source venv/bin/activate
celery -A app.core.celery_app worker -l info -Q tour_dispatch
```

### 7. Запустить frontend

Терминал 3:

```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

Frontend:

- `http://localhost:5173`

## Проверка после запуска

1. Открой `http://localhost:8000/health` и проверь статус.
2. Открой `http://localhost:5173`.
3. На странице создания тура загрузи манифест и сравни с таблицей.
4. Нажми `Создать тур код` и проверь, что задача появляется в очереди.

## Google Sheets credentials

Файл сервисного аккаунта ожидается по пути:

`backend/credentials/credentials.json`

## Docker (frontend + backend + worker + postgres + redis)

Из корня проекта:

```bash
docker compose up -d --build
```

Проверка:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

Логи:

```bash
docker compose logs -f backend worker
```

Остановка:

```bash
docker compose down
```
