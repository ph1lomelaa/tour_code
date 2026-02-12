"""
API endpoints для работы с OPEN DATE бронированиями
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import logging

from bull_project.bull_bot.database import requests as db
from bull_project.bull_bot.core.google_sheets.writer import (
    write_open_date_to_certificate,
    move_pilgrim_from_certificate_to_used
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/open-date", tags=["open-date"])


# === MODELS ===

class OpenDatePilgrimData(BaseModel):
    """Данные паломника для OPEN DATE (требуются обязательные поля)"""
    last_name: str
    first_name: str
    gender: str
    date_of_birth: Optional[str] = None
    passport_num: Optional[str] = None
    passport_expiry: Optional[str] = None
    iin: Optional[str] = None


class OpenDateSubmitRequest(BaseModel):
    pilgrims: List[OpenDatePilgrimData]
    room_type: Optional[str] = None
    meal_type: Optional[str] = None
    price: Optional[str] = None
    departure_city: Optional[str] = None
    region: Optional[str] = None
    client_phone: str
    comment: Optional[str] = None
    manager_id: Optional[int] = None
    manager_name_text: Optional[str] = None


class ConvertToBookingRequest(BaseModel):
    open_date_id: int
    package_name: str
    sheet_name: str
    table_id: str
    selected_date: str


# === ENDPOINTS ===

@router.post("/submit")
async def submit_open_date(data: OpenDateSubmitRequest):
    """Создает OPEN DATE бронирование"""
    try:
        logger.info(f"📝 Создание OPEN DATE брони для {len(data.pilgrims)} паломников")

        manager_id = int(data.manager_id or 0)
        manager_name = (data.manager_name_text or "").strip() or "Manager"

        # Подготавливаем данные паломников
        pilgrim_data_list = [p.dict() for p in data.pilgrims]

        # Подготавливаем данные для Google Sheets
        booking_data = {
            "room_type": data.room_type,
            "meal_type": data.meal_type,
            "price": data.price,
            "region": data.region,
            "departure_city": data.departure_city,
            "client_phone": data.client_phone,
            "manager_name_text": manager_name,
            "comment": data.comment
        }

        # Записываем в Google Sheets Certificate 2025
        saved_rows = await write_open_date_to_certificate(pilgrim_data_list, booking_data)

        if not saved_rows:
            raise HTTPException(status_code=500, detail="Ошибка записи в Google Sheets")

        # Сохраняем в БД
        open_date_booking = await db.add_open_date_booking(
            manager_id=manager_id,
            manager_name_text=manager_name,
            pilgrim_data=pilgrim_data_list,
            room_type=data.room_type,
            meal_type=data.meal_type,
            price=data.price,
            region=data.region,
            departure_city=data.departure_city,
            client_phone=data.client_phone,
            comment=data.comment,
            google_sheet_row=saved_rows[0] if saved_rows else None  # Сохраняем первую строку
        )

        logger.info(f"✅ OPEN DATE бронь создана: ID={open_date_booking.id}")

        return {
            "success": True,
            "booking_id": open_date_booking.id,
            "message": "Паломники записаны в OPEN DATE"
        }

    except Exception as e:
        logger.error(f"❌ Ошибка создания OPEN DATE брони: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def get_open_date_list(manager_id: Optional[int] = None):
    """Получает список всех OPEN DATE бронирований"""
    try:
        bookings = await db.get_all_open_date_bookings(manager_id=manager_id)

        # Преобразуем в словари для JSON
        bookings_data = []
        for booking in bookings:
            bookings_data.append({
                "id": booking.id,
                "manager_id": booking.manager_id,
                "manager_name_text": booking.manager_name_text,
                "pilgrim_data": booking.pilgrim_data,
                "room_type": booking.room_type,
                "meal_type": booking.meal_type,
                "price": booking.price,
                "region": booking.region,
                "departure_city": booking.departure_city,
                "client_phone": booking.client_phone,
                "comment": booking.comment,
                "google_sheet_row": booking.google_sheet_row,
                "status": booking.status,
                "created_at": booking.created_at.isoformat() if booking.created_at else None,
                "updated_at": booking.updated_at.isoformat() if booking.updated_at else None
            })

        return {
            "success": True,
            "bookings": bookings_data
        }

    except Exception as e:
        logger.error(f"❌ Ошибка получения списка OPEN DATE: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{booking_id}")
async def get_open_date_booking(booking_id: int):
    """Получает конкретную OPEN DATE бронь по ID"""
    try:
        booking = await db.get_open_date_booking_by_id(booking_id)

        if not booking:
            raise HTTPException(status_code=404, detail="Бронь не найдена")

        return {
            "success": True,
            "booking": {
                "id": booking.id,
                "manager_id": booking.manager_id,
                "manager_name_text": booking.manager_name_text,
                "pilgrim_data": booking.pilgrim_data,
                "room_type": booking.room_type,
                "meal_type": booking.meal_type,
                "price": booking.price,
                "region": booking.region,
                "departure_city": booking.departure_city,
                "client_phone": booking.client_phone,
                "comment": booking.comment,
                "google_sheet_row": booking.google_sheet_row,
                "status": booking.status,
                "created_at": booking.created_at.isoformat() if booking.created_at else None,
                "updated_at": booking.updated_at.isoformat() if booking.updated_at else None
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка получения OPEN DATE брони: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_open_date(q: str):
    """Поиск OPEN DATE броней по запросу"""
    try:
        if not q or len(q) < 2:
            return {"success": True, "bookings": []}

        bookings = await db.search_open_date_bookings(q)

        # Преобразуем в словари
        bookings_data = []
        for booking in bookings:
            bookings_data.append({
                "id": booking.id,
                "manager_id": booking.manager_id,
                "manager_name_text": booking.manager_name_text,
                "pilgrim_data": booking.pilgrim_data,
                "room_type": booking.room_type,
                "meal_type": booking.meal_type,
                "price": booking.price,
                "client_phone": booking.client_phone,
                "created_at": booking.created_at.isoformat() if booking.created_at else None
            })

        return {
            "success": True,
            "bookings": bookings_data
        }

    except Exception as e:
        logger.error(f"❌ Ошибка поиска OPEN DATE: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/convert/{booking_id}")
async def convert_to_regular_booking(booking_id: int, data: ConvertToBookingRequest):
    """Конвертирует OPEN DATE бронь в обычную бронь"""
    try:
        logger.info(f"🔄 Конвертация OPEN DATE брони {booking_id} в обычную")

        # Получаем OPEN DATE бронь
        open_date_booking = await db.get_open_date_booking_by_id(booking_id)

        if not open_date_booking:
            raise HTTPException(status_code=404, detail="OPEN DATE бронь не найдена")

        if open_date_booking.status != "OPEN":
            raise HTTPException(status_code=400, detail="Бронь уже конвертирована")

        # Переносим паломников из Certificate 2025 в ИСПОЛЬЗОВАННЫЕ
        for pilgrim in open_date_booking.pilgrim_data:
            full_name = f"{pilgrim['last_name']} {pilgrim['first_name']}"
            success = await move_pilgrim_from_certificate_to_used(
                pilgrim_full_name=full_name,
                selected_date=data.selected_date,
                new_booking_data={
                    "package_name": data.package_name,
                    "sheet_name": data.sheet_name,
                    "table_id": data.table_id
                }
            )

            if not success:
                logger.warning(f"⚠️ Не удалось перенести паломника {full_name}")

        # Обновляем статус OPEN DATE брони
        await db.update_open_date_booking_status(booking_id, "CONVERTED")

        logger.info(f"✅ OPEN DATE бронь {booking_id} успешно конвертирована")

        return {
            "success": True,
            "message": "Бронь успешно конвертирована"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка конвертации OPEN DATE брони: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{booking_id}")
async def delete_open_date_booking(booking_id: int):
    try:
        success = await db.delete_open_date_booking(booking_id)

        if not success:
            raise HTTPException(status_code=404, detail="Бронь не найдена")

        return {
            "success": True,
            "message": "Бронь удалена"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка удаления OPEN DATE брони: {e}")
        raise HTTPException(status_code=500, detail=str(e))
