#!/bin/bash

# =============================================================================
# Hickmet Premium Tour Code - Production Deployment Script
# =============================================================================

set -e  # Exit on error

SERVER_IP="65.21.188.181"
SERVER_USER="root"
SERVER_PATH="/root/hickmet/tour_code"
DOMAIN="tourcode.hickmet.duckdns.org"  # Измените на свой домен

echo "🚀 Deploying Hickmet Premium Tour Code to $SERVER_IP"
echo "================================================"

# Проверка что .env.prod существует
if [ ! -f "backend/.env.prod" ]; then
    echo "❌ Ошибка: backend/.env.prod не найден"
    echo "Скопируйте backend/.env.example в backend/.env.prod и заполните"
    exit 1
fi

# Проверка что credentials.json существует
if [ ! -f "backend/credentials/credentials.json" ]; then
    echo "⚠️  Предупреждение: backend/credentials/credentials.json не найден"
    echo "Google Sheets API не будет работать"
    read -p "Продолжить деплой? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Создать архив проекта
echo "📦 Архивирование проекта..."
tar -czf tour_code_deploy.tar.gz \
  --exclude=node_modules \
  --exclude=venv \
  --exclude=frontend/venv \
  --exclude=__pycache__ \
  --exclude='*.pyc' \
  --exclude=.git \
  --exclude=hickmet.db \
  --exclude=backend/uploads \
  --exclude=frontend/dist \
  --exclude=.claude \
  --exclude='*.log' \
  .

echo "📤 Загрузка на сервер..."
scp tour_code_deploy.tar.gz $SERVER_USER@$SERVER_IP:/tmp/

echo "🔧 Распаковка и настройка на сервере..."
ssh $SERVER_USER@$SERVER_IP <<'ENDSSH'
set -e

# Создать директорию если не существует
mkdir -p /root/hickmet/tour_code
cd /root/hickmet/tour_code

# Распаковать
tar -xzf /tmp/tour_code_deploy.tar.gz
rm /tmp/tour_code_deploy.tar.gz

echo "✅ Код распакован в /root/hickmet/tour_code"

# Проверить что docker-compose.prod.yml существует
if [ ! -f docker-compose.prod.yml ]; then
    echo "❌ docker-compose.prod.yml не найден"
    exit 1
fi

# Проверить что .env.prod существует
if [ ! -f backend/.env.prod ]; then
    echo "❌ backend/.env.prod не найден"
    exit 1
fi

echo "🐳 Сборка Docker образов..."
docker compose -f docker-compose.prod.yml build --no-cache

echo "🚀 Запуск контейнеров..."
docker compose -f docker-compose.prod.yml up -d

echo "⏳ Ожидание готовности контейнеров..."
sleep 10

echo "📊 Статус контейнеров:"
docker compose -f docker-compose.prod.yml ps

echo ""
echo "🔗 Подключение Caddy к Tour Code network..."
# Проверить что Caddy запущен
if docker ps | grep -q caddy; then
    # Подключить Caddy к Tour Code network (игнорировать ошибку если уже подключен)
    docker network connect tour_code_tour_code_network caddy 2>/dev/null || true

    echo "🔄 Перезагрузка Caddy..."
    docker exec caddy caddy reload --config /etc/caddy/Caddyfile || true
else
    echo "⚠️  Caddy не запущен. Нужно вручную настроить reverse proxy."
fi

echo ""
echo "✅ Деплой завершен!"
echo ""
echo "Проверка:"
echo "  - Статус: docker compose -f docker-compose.prod.yml ps"
echo "  - Логи: docker compose -f docker-compose.prod.yml logs -f"
echo "  - Health: curl http://localhost:8001/health"
echo ""
echo "Доступ:"
echo "  - API: http://localhost:8001/docs"
echo "  - Frontend (через Caddy): https://tourcode.hickmet.duckdns.org"
echo ""
ENDSSH

# Удалить локальный архив
rm -f tour_code_deploy.tar.gz

echo ""
echo "=========================================="
echo "✨ Деплой завершен успешно!"
echo "=========================================="
echo ""
echo "Следующие шаги:"
echo ""
echo "1. Проверить логи на сервере:"
echo "   ssh $SERVER_USER@$SERVER_IP"
echo "   cd $SERVER_PATH"
echo "   docker compose -f docker-compose.prod.yml logs -f backend"
echo ""
echo "2. Настроить Caddyfile (если еще не сделано):"
echo "   ssh $SERVER_USER@$SERVER_IP"
echo "   nano /root/hickmet/bull_project/Caddyfile"
echo ""
echo "   Добавить блок:"
echo "   $DOMAIN {"
echo "     reverse_proxy tour_code_frontend:80"
echo "   }"
echo ""
echo "   Затем перезагрузить:"
echo "   docker exec caddy caddy reload --config /etc/caddy/Caddyfile"
echo ""
echo "3. Открыть в браузере:"
echo "   https://$DOMAIN"
echo ""
