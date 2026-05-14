# Tour Code

Система для подготовки, проверки и отправки тур-кодов Hickmet Premium. Проект состоит из frontend-приложения для операторов, backend API на FastAPI, PostgreSQL для хранения состояния, Redis как брокера задач и Celery worker для фоновой отправки данных во внешний сервис `kamkor/qamqor`.

## Что делает проект

Основной пользовательский сценарий:

1. Оператор ищет тур по дате вылета.
2. Backend находит подходящие листы в Google Sheets.
3. Оператор выбирает лист и получает паломников, сгруппированных по пакетам.
4. Оператор загружает Excel-манифест.
5. Система сравнивает данные из манифеста и Google Sheet.
6. Подтвержденные записи сохраняются в БД как `tours`, `pilgrims`, `tour_offers`.
7. Создается `dispatch_job` со snapshot входных данных.
8. Celery worker отправляет данные во внешний партнерский сервис.
9. Полученные тур-коды сохраняются в `pilgrims.tour_code` и отображаются в интерфейсе.

## Состав репозитория

```text
Tour_code/
├── backend/
│   ├── app/
│   │   ├── api/v1/                 # FastAPI endpoints
│   │   ├── core/                   # config, DB helpers
│   │   ├── google_sheet_parser/    # интеграция с Google Sheets и Excel parsing
│   │   ├── queue/                  # Celery app и задачи
│   │   ├── services/               # нормализация и сборка payload
│   │   └── worker.py               # точка входа worker
│   ├── credentials/                # Google service account
│   └── uploads/                    # временные загрузки
├── db/                             # SQLAlchemy models, schema, setup
├── frontend/
│   ├── app/                        # страницы и UI
│   └── src/lib/api/                # typed API client
├── docs/                           # подробная документация для разработчиков
└── docker-compose.yml              # локальная сборка всех сервисов
```

## Быстрый старт

### Через Docker Compose

```bash
docker compose up --build
```

Поднимаются сервисы:

- `postgres` на `localhost:5433`
- `redis` на `localhost:6379`
- `backend` на `localhost:8001`
- `frontend` на `localhost:3000`
- `worker` как отдельный Celery consumer очереди `tour_dispatch`

### Локальный запуск по частям

Нужны:

- Python 3.11+
- Node.js 18+
- PostgreSQL
- Redis
- Google service account credentials
- файл `backend/.env`

Примерный порядок:

```bash
cd backend
uvicorn app.main:app --reload
```

```bash
cd backend
celery -A app.core.celery_app worker --loglevel=info -Q tour_dispatch
```

```bash
cd frontend
npm install
npm run dev
```

## Конфигурация

Основные настройки лежат в [backend/app/core/config.py](/backend/app/core/config.py) и читаются из `backend/.env`.

Ключевые переменные:

- `DATABASE_URL`
- `REDIS_URL`
- `GOOGLE_SHEETS_CREDENTIALS_FILE`
- `DISPATCH_AUTH_URL`
- `DISPATCH_SAVE_URL`
- `DISPATCH_AGENT_LOGIN`
- `DISPATCH_AGENT_PASS`
- `DISPATCH_MAX_ATTEMPTS`
- `DISPATCH_RETRY_DELAY_SECONDS`
- `DISPATCH_QUEUE_NAME`

## Документация

Подробная документация вынесена в `docs/`:

- [docs/architecture.md](/docs/architecture.md) — архитектура проекта и общая схема взаимодействия
- [docs/backend-api.md](/docs/backend-api.md) — полный контракт backend API
- [docs/kamkor-integration.md](/docs/kamkor-integration.md) — подробная документация по интеграции `kamkor/qamqor`
- [docs/celery-dispatch.md](/docs/celery-dispatch.md) — очередь, worker, retry, статусы и диагностика
- [docs/data-model.md](/docs/data-model.md) — структура БД и `mermaid` ER-диаграмма
- [docs/google-sheets-and-manifest.md](/docs/google-sheets-and-manifest.md) — parsing Google Sheets и Excel-манифестов
- [docs/frontend-flow.md](/docs/frontend-flow.md) — пользовательский flow и устройство frontend
- [docs/operations.md](/docs/operations.md) — окружение, запуск, Docker и troubleshooting
- [docs/repo-notes-and-gaps.md](/docs/repo-notes-and-gaps.md) — текущие расхождения в репозитории и техдолг, которые нужно учитывать разработчику

## Ключевые кодовые точки

- [backend/app/main.py](/backend/app/main.py) — FastAPI entrypoint
- [backend/app/api/v1/dispatch.py](/backend/app/api/v1/dispatch.py) — постановка задач dispatch и чтение статусов
- [backend/app/queue/tasks/dispatch.py](/backend/app/queue/tasks/dispatch.py) — Celery task отправки в partner-систему
- [backend/app/services/partner_payload_builder.py](/backend/app/services/partner_payload_builder.py) — сборка payload для `kamkor/qamqor`
- [db/models.py](/db/models.py) — SQLAlchemy модели
- [frontend/app/pages/CreateTourCode.tsx](/frontend/app/pages/CreateTourCode.tsx) — основной рабочий экран оператора
