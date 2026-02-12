from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from bull_project.bull_bot.core.websocket_manager import (
    phone_subscribers,
    admin_request_subscribers,
)


router = APIRouter()


@router.websocket("/ws/phones")
async def websocket_phone_updates(websocket: WebSocket):
    """WebSocket endpoint - клиенты подключаются сюда для получения новых телефонов мгновенно."""
    await websocket.accept()
    phone_subscribers.append(websocket)
    print(f"📱 WebSocket клиент подключен. Всего подписчиков: {len(phone_subscribers)}")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        phone_subscribers.remove(websocket)
        print(f"📱 WebSocket клиент отключился. Всего подписчиков: {len(phone_subscribers)}")


@router.websocket("/ws/admin-requests")
async def websocket_admin_requests(websocket: WebSocket):
    """WebSocket endpoint - админы подключаются для получения уведомлений о заявках."""
    await websocket.accept()
    admin_request_subscribers.append(websocket)
    print(f"🔔 WebSocket админ подключен. Всего подписчиков: {len(admin_request_subscribers)}")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        admin_request_subscribers.remove(websocket)
        print(f"🔔 WebSocket админ отключился. Всего подписчиков: {len(admin_request_subscribers)}")
