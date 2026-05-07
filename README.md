# Tour Code

Система для подготовки и отправки тур-кодов Hickmet Premium. Проект состоит из frontend-приложения для операторов, backend API для бизнес-логики, PostgreSQL для хранения состояния, Redis для очередей и Celery worker для фоновой отправки данных во внешний партнерский сервис.

## Назначение

Основной сценарий:

1. Оператор ищет тур по дате вылета.
2. Backend находит подходящие листы в Google Sheets.
3. Оператор получает паломников из выбранного листа.
4. Оператор загружает Excel-манифест.
5. Система сравнивает данные из манифеста и таблицы.
6. Подтвержденные записи сохраняются как тур и паломники.
7. Задача на отправку ставится в очередь.
8. Celery worker собирает payload и отправляет его во внешний сервис.
9. Полученные tour codes сохраняются обратно в БД и отображаются в интерфейсе.

## Архитектура

### Состав сервисов

- `frontend` - React + Vite SPA для операторов.
- `backend` - FastAPI приложение с REST API.
- `worker` - Celery worker для фоновой отправки задач dispatch.
- `postgres` - основная БД проекта.
- `redis` - брокер/вспомогательное хранилище для очередей Celery.

В Docker-режиме все сервисы поднимаются из `docker-compose.yml`.

### Общая схема взаимодействия

```text
React UI
   |
   v
FastAPI (/api/v1/*)
   | \
   |  \__ Google Sheets + Excel parsing
   |
   +--> PostgreSQL (tours, pilgrims, dispatch_jobs, tour_offers)
   |
   \--> Celery enqueue -> Redis -> Celery worker
                               |
                               v
                     External partner dispatch service
                               |
                               v
                          PostgreSQL update
```

## Структура проекта

```text
Tour_code/
├── backend/
│   └── app/
│       ├── api/v1/                 # REST endpoints
│       ├── core/                   # config, DB, celery setup
│       ├── google_sheet_parser/    # интеграция с Google Sheets и парсинг файлов
│       ├── queue/tasks/            # Celery tasks
│       └── services/               # нормализация и сборка partner payload
├── frontend/
│   ├── app/                        # страницы, layout, UI
│   └── src/lib/api/                # клиент API для frontend
├── db/                             # SQLAlchemy модели, engine, schema.sql
├── docker-compose.yml              # production-like локальный запуск
├── requirements.txt                # Python dependencies
└── README.md
```

## Backend

### Точка входа

Приложение инициализируется в `backend/app/main.py`.

Что происходит при старте:

- читаются настройки из `backend/.env` через `pydantic-settings`
- поднимается FastAPI
- подключается CORS
- проверяется доступность PostgreSQL
- вызывается `init_db()`
- подключаются роутеры `tours`, `manifest`, `dispatch`, `pilgrims`, `tour_packages`, `dashboard`

Конфигурация собрана в `backend/app/core/config.py`. Через env настраиваются:

- `DATABASE_URL`
- `REDIS_URL`
- доступ к Google Sheets
- параметры dispatch
- URL и учетные данные внешнего партнера

### API модули

- `backend/app/api/v1/tours.py` - поиск туров по дате и чтение паломников из листа Google Sheets.
- `backend/app/api/v1/manifest.py` - загрузка Excel-манифеста и сравнение с данными таблицы.
- `backend/app/api/v1/dispatch.py` - создание dispatch jobs, сохранение снапшота тура и контроль статусов отправки.
- `backend/app/api/v1/tour_packages.py` - просмотр сохраненных туров, matched-данных и доотправка.
- `backend/app/api/v1/pilgrims.py` - список паломников с фильтрами.
- `backend/app/api/v1/dashboard.py` - агрегированная статистика и последние операции.

### Google Sheets и парсинг файлов

- `backend/app/google_sheet_parser/google_sheets_service.py` реализует доступ к Google Sheets через service account.
- Поиск туров идет по названиям листов: дата, диапазон дат, маршрут и длительность извлекаются из sheet name.
- `backend/app/google_sheet_parser/manifest_parser.py` читает Excel через `pandas`, пытается распознать колонки `surname`, `name`, `passport`, `iin`, нормализует документы и формирует единый список паломников.

### Слой очередей и dispatch

Фоновая отправка реализована через Celery:

- конфигурация очереди находится в `backend/app/queue/celery_app.py`
- основная задача отправки находится в `backend/app/queue/tasks/dispatch.py`

Логика dispatch:

1. Frontend вызывает enqueue endpoint.
2. Backend сохраняет snapshot входных данных в `dispatch_jobs.payload`.
3. На основе snapshot создаются `tours`, `pilgrims`, `tour_offers`.
4. Job ставится в очередь `tour_dispatch`.
5. Worker собирает partner payload через `backend/app/services/partner_payload_builder.py`.
6. Worker проходит авторизацию во внешнем сервисе и отправляет данные.
7. Из ответа извлекается `tour code`.
8. `tour_code` сохраняется у соответствующего паломника.
9. Статус job обновляется в БД.

Ключевая архитектурная идея здесь: отправка вынесена в отдельный outbox-like слой `dispatch_jobs`, поэтому пользовательский запрос не блокируется сетевой интеграцией, а состояние отправки можно отслеживать и повторять.

## Модель данных

Основные SQLAlchemy-модели находятся в `db/models.py`.

- `Tour` - агрегат тура, хранит ссылку на Google Sheet, даты, маршрут, отель, страну, remark и статус.
- `Pilgrim` - паломник, связанный с туром; содержит имя, документ, пакет и итоговый `tour_code`.
- `TourOffer` - сегменты поездки, в текущем сценарии в основном перелеты туда и обратно.
- `DispatchJob` - запись фоновой отправки; хранит snapshot формы, подготовленный payload, ответ внешнего сервиса, счетчики попыток и ошибки.
- `User`, `SystemSettings` - инфраструктурные сущности, подготовленные под дальнейшее развитие.

Почему данные устроены так:

- `Tour` хранит операционное состояние тура после ручного выбора оператором.
- `Pilgrim` отделен от snapshot манифеста, чтобы можно было хранить фактический результат обработки.
- `DispatchJob` хранит оригинальный payload и ответ интеграции, поэтому его удобно использовать для диагностики, повторной отправки и аудита.

## Frontend

Frontend - это SPA на React Router.

Маршруты описаны в `frontend/app/routes.ts`:

- `/` - dashboard
- `/create` - создание тур-кода
- `/packages` - сохраненные туры и детали пакетов
- `/pilgrims` - список паломников

### Основные страницы

- `frontend/app/pages/CreateTourCode.tsx` - главный рабочий экран. Здесь сосредоточен пользовательский flow: поиск тура, выбор листа, загрузка манифеста, client-side нормализация и fuzzy matching, отправка job, опрос статуса.
- `Dashboard.tsx` - сводная статистика и последние операции.
- `TourPackages.tsx` - просмотр уже сохраненных туров, результатов сравнения и статусов.
- `Pilgrims.tsx` - поиск и просмотр паломников.

### API слой frontend

Frontend не ходит по API напрямую из компонентов, а использует клиент из `frontend/src/lib/api/`.

Там модули разделены по доменам:

- `tours.ts`
- `manifest.ts`
- `dispatch.ts`
- `tourPackages.ts`
- `pilgrims.ts`
- `dashboard.ts`

Это упрощает поддержку: контракты API и преобразование ответов лежат в одном месте, а страницы работают с уже подготовленными функциями.

## Как реализован основной бизнес-процесс

### 1. Поиск тура

Пользователь вводит дату.

- frontend вызывает `POST /api/v1/tours/search-by-date`
- backend ищет Google Sheets текущего и следующего года
- из названий листов извлекаются даты, маршрут и длительность
- в UI возвращается список доступных туров

### 2. Получение паломников из Google Sheet

После выбора тура:

- frontend вызывает `POST /api/v1/tours/sheet-pilgrims`
- backend читает выбранный лист
- паломники группируются по пакетам
- UI получает структуру по пакетам и общему количеству

### 3. Загрузка и парсинг манифеста

- frontend отправляет Excel в `POST /api/v1/manifest/upload`
- backend читает первый лист файла через `pandas`
- пытается распознать релевантные колонки по алиасам
- документы и ИИН нормализуются
- возвращается канонический список паломников

### 4. Сравнение таблицы и манифеста

Сравнение идет в двух слоях:

- backend делает базовое сопоставление по нормализованному документу
- frontend дополнительно применяет fuzzy matching по имени, фамилии, ИИН и похожести паспортов

Это сделано потому, что в реальных файлах часто встречаются опечатки, разный формат документов и неодинаковое написание имен.

### 5. Постановка на отправку

Когда оператор подтверждает итоговый набор:

- frontend вызывает enqueue endpoint dispatch
- backend сохраняет snapshot выбранного тура, параметров и matched-списка
- создаются записи `Tour`, `Pilgrim`, `TourOffer`, `DispatchJob`
- Celery worker берет job из Redis-очереди

### 6. Интеграция с внешним сервисом

Worker:

- собирает partner-совместимый payload
- авторизуется во внешнем кабинете
- отправляет данные по каждому подтвержденному паломнику
- парсит ответ, извлекает код
- записывает код в `pilgrims.tour_code`
- обновляет `dispatch_jobs.status`, прогресс и диагностические поля

## Локальный запуск

### Требования

- Python 3.11
- Node.js 20+
- Docker + Docker Compose
- PostgreSQL и Redis, если запуск без Docker
- Google service account credentials

### Переменные и секреты

Ожидается файл:

- `backend/.env`

Для Google Sheets нужен файл:

- `backend/credentials/credentials.json`

### Запуск через Docker

Из корня проекта:

```bash
docker compose up -d --build
```

После запуска:

- frontend: `http://localhost:3000`
- backend: `http://localhost:8001`
- docs: `http://localhost:8001/docs`

Логи:

```bash
docker compose logs -f backend worker frontend
```

Остановка:

```bash
docker compose down
```


## Что важно знать 

- Главный пользовательский flow сейчас сосредоточен в `CreateTourCode.tsx`. Это центральный экран системы.
- Проект опирается на внешние данные, которые могут быть грязными: Google Sheets, Excel-манифесты, ответы партнерской системы. Поэтому в коде много нормализации и defensive parsing.
- Источник истины для уже обработанных туров - PostgreSQL, а не Google Sheets.
- Очередь dispatch нельзя рассматривать как "fire and forget": статус, payload и response сохраняются в `dispatch_jobs`, это часть бизнес-процесса.
- Если нужно менять интеграцию с партнером, в первую очередь смотреть `partner_payload_builder.py` и `queue/tasks/dispatch.py`.
- Если нужно менять поведение сопоставления паломников, смотреть backend `manifest.py` и frontend `CreateTourCode.tsx`.

## Проверка после запуска

1. Открыть `/health` и убедиться, что backend видит БД.
2. Открыть frontend.
3. Выполнить сценарий: поиск тура -> загрузка манифеста -> сравнение -> enqueue dispatch.
4. Проверить, что job появился в БД и меняет статус.
5. Проверить, что у паломников появляются `tour_code` после успешной отправки.
