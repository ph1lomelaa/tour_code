# Hickmet Premium - Система управления тур-кодами

Веб-приложение для управления паломническими турами (Umrah/Hajj).

## Структура проекта

```
Tour_code/
├── backend/                   # Серверная часть (FastAPI + Python)
│   ├── app/                   # Основной код приложения
│   │   ├── api/v1/            # API эндпоинты (tours, manifest)
│   │   ├── core/              # Конфигурация и подключение к БД
│   │   ├── services/          # Бизнес-логика (Google Sheets, парсеры)
│   │   ├── models/            # Модели данных (SQLAlchemy)
│   │   ├── schemas/           # Pydantic-схемы валидации
│   │   ├── crud/              # CRUD-операции с БД
│   │   └── workers/           # Фоновые задачи
│   ├── credentials/           # Google API ключи (не в git)
│   ├── database/migrations/   # Миграции БД
│   ├── tests/                 # Тесты
│   ├── uploads/               # Загруженные манифесты
│   └── requirements.txt
│
├── frontend/                  # Клиентская часть (React + Vite + TS)
│   ├── app/
│   │   ├── pages/             # Страницы (CreateTourCode и др.)
│   │   └── components/
│   │       ├── ui/            # UI-компоненты (Button, Input, Table)
│   │       └── figma/         # Компоненты из Figma-дизайна
│   ├── src/lib/api/           # API-клиент (запросы к бэкенду)
│   ├── styles/                # CSS-стили
│   └── package.json
│
├── logic/                     # Скрипты и утилиты вне API
│   └── core/
│       ├── google_sheets/     # Работа с Google Sheets напрямую
│       ├── parsers/           # Парсеры данных
│       ├── models/            # Модели и скрипты
│       └── utils/             # Утилиты
│
├── test sheets/               # Тестовые Excel-файлы
└── docker-compose.dev.yml     # Docker для разработки
```

## Быстрый старт

### 1. Backend

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Backend: http://localhost:8000

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173

### 3. Google Sheets

Для работы с Google Sheets нужно положить файл `credentials.json` в папку `backend/credentials/`.

## Технологии

**Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Radix UI

**Backend:** Python 3.11+, FastAPI, Google Sheets API, SQLAlchemy, PostgreSQL
