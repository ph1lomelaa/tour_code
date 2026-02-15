
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
