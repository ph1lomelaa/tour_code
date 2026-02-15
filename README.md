
## Docker (frontend + backend + worker + postgres + redis)

Из корня проекта:

```bash
docker compose up -d --build
```

Логи:

```bash
docker compose logs -f backend worker
```

Остановка:

```bash
docker compose down
```
