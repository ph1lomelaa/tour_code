# 🕌 Hickmet Premium - Система управления тур-кодами

Веб-приложение для управления паломническими турами (Umrah/Hajj).

## 📁 Структура проекта

```
Tour_code/
├── frontend/              # React + Vite приложение
│   ├── app/              # Компоненты и страницы
│   ├── styles/           # CSS стили
│   ├── package.json
│   └── vite.config.ts
│
├── backend/              # FastAPI приложение
│   ├── app/             # Python код
│   ├── database/        # SQL схема и миграции
│   ├── requirements.txt
│   └── README.md
│
├── docker-compose.dev.yml    # Docker для разработки
├── ARCHITECTURE_DIAGRAMS.md  # Детальная архитектура
└── QUICKSTART.md             # Быстрый старт

```

## 🚀 Быстрый старт

### 1. Запустить базу данных

```bash
# PostgreSQL + Redis
docker-compose -f docker-compose.dev.yml up -d
```

### 2. Запустить Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend: http://localhost:8000

### 3. Запустить Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173

---

## 📚 Документация

- [QUICKSTART.md](QUICKSTART.md) - Подробная инструкция
- [ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md) - Архитектура системы
- [backend/README.md](backend/README.md) - Backend документация

---

## 🛠️ Технологии

**Frontend:**
- React 18
- TypeScript
- Vite
- Tailwind CSS
- Radix UI

**Backend:**
- Python 3.11+
- FastAPI
- PostgreSQL 16
- Redis
- SQLAlchemy
- Celery

---

## 📊 Основные функции

1. ✅ Создание тур-кодов
2. ✅ Загрузка и парсинг манифестов (Excel)
3. ✅ Управление базой паломников
4. ✅ Поиск и фильтрация паломников
5. ✅ Просмотр туристических пакетов
6. ✅ История всех операций (audit log)

---

**Разработано для Hickmet Premium** 🕌
# tour_code
# tour_code
