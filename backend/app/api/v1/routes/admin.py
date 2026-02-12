import os
import json
from datetime import datetime

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, FileResponse

from bull_project.bull_bot.api.utils import resolve_passport_path
from bull_project.bull_bot.config.constants import ABS_UPLOADS_DIR
from bull_project.bull_bot.database.requests import (
    get_full_analytics,
    get_manager_detailed_stats,
    get_all_managers_list,
    search_packages_by_date,
    get_all_bookings_for_period,
)


router = APIRouter()


@router.get("/api/admin/analytics")
async def get_admin_analytics(
    start_date: str = Query(..., description="Дата начала (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Дата конца (YYYY-MM-DD)")
):
    try:
        # Парсим даты
        d1 = datetime.strptime(start_date, "%Y-%m-%d").date()
        d2 = datetime.strptime(end_date, "%Y-%m-%d").date()
        stats = await get_full_analytics(d1, d2)

        return {
            "ok": True,
            **stats
        }

    except Exception as e:
        print(f"❌ Ошибка получения аналитики: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )


@router.get("/api/admin/managers")
async def get_all_managers():
    try:
        managers = await get_all_managers_list()
        managers_data = []
        for m in managers:
            managers_data.append({
                "telegram_id": m.telegram_id,
                "full_name": m.full_name,
                "username": m.username,
                "role": m.role
            })

        return {
            "ok": True,
            "managers": managers_data
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )


@router.get("/api/admin/manager/{manager_id}")
async def get_manager_stats(
    manager_id: int,
    start_date: str = Query(...),
    end_date: str = Query(...)
):
    try:
        d1 = datetime.strptime(start_date, "%Y-%m-%d").date()
        d2 = datetime.strptime(end_date, "%Y-%m-%d").date()

        stats = await get_manager_detailed_stats(manager_id, d1, d2)

        bookings_data = []
        for b in stats['bookings']:
            passport_path = await resolve_passport_path(b)
            bookings_data.append({
                "id": b.id,
                "guest_last_name": b.guest_last_name,
                "guest_first_name": b.guest_first_name,
                "package_name": b.package_name,
                "sheet_name": b.sheet_name,
                "price": b.price,
                "status": b.status,
                "passport_image_path": passport_path,
                "created_at": b.created_at.isoformat() if b.created_at else None
            })

        return {
            "ok": True,
            "total": stats['total'],
            "active": stats['active'],
            "cancelled": stats['cancelled'],
            "top_packages": stats['top_packages'],
            "package_rollup": stats.get('package_rollup', []),
            "bookings": bookings_data
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )


@router.get("/api/admin/search/packages")
async def search_packages_endpoint(date: str = Query(..., description="Дата для поиска (ДД.ММ)")):
    try:
        results = await search_packages_by_date(date)

        packages_data = []
        for sheet, pkg, cnt in results:
            packages_data.append({
                "sheet_name": sheet,
                "package_name": pkg,
                "count": cnt
            })

        return {
            "ok": True,
            "packages": packages_data
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )


@router.get("/api/admin/bookings")
async def get_all_bookings(
    start_date: str = Query(..., description="Дата начала (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Дата конца (YYYY-MM-DD)")
):
    """
    Получение списка всех броней за период
    """
    try:
        d1 = datetime.strptime(start_date, "%Y-%m-%d").date()
        d2 = datetime.strptime(end_date, "%Y-%m-%d").date()

        bookings = await get_all_bookings_for_period(d1, d2)

        bookings_data = []
        for b in bookings:
            passport_path = await resolve_passport_path(b)
            group_members = []
            if b.group_members:
                try:
                    group_members = json.loads(b.group_members)
                except Exception:
                    group_members = []
            bookings_data.append({
                "id": b.id,
                "table_id": b.table_id,
                "guest_last_name": b.guest_last_name,
                "guest_first_name": b.guest_first_name,
                "gender": b.gender,
                "date_of_birth": b.date_of_birth,
                "guest_iin": b.guest_iin,
                "passport_num": b.passport_num,
                "passport_expiry": b.passport_expiry,
                "passport_image_path": passport_path,
                "client_phone": b.client_phone,
                "package_name": b.package_name,
                "sheet_name": b.sheet_name,
                "sheet_row_number": b.sheet_row_number,
                "room_type": b.room_type,
                "placement_type": b.placement_type,
                "meal_type": b.meal_type,
                "visa_status": b.visa_status,
                "avia": b.avia,
                "train": b.train,
                "departure_city": b.departure_city,
                "region": b.region,
                "source": b.source,
                "price": b.price,
                "amount_paid": b.amount_paid,
                "status": b.status,
                "manager_name": b.manager_name_text or "-",
                "created_at": b.created_at.isoformat() if b.created_at else None,
                "updated_at": b.updated_at.isoformat() if b.updated_at else None,
                "comment": b.comment or "",
                "group_members": group_members
            })

        return {
            "ok": True,
            "bookings": bookings_data
        }

    except Exception as e:
        print(f"❌ Ошибка получения броней: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )


@router.get("/api/admin/download-all-passports")
async def download_all_passports():
    """
    Скачать все паспорта из volume в виде ZIP архива
    ВАЖНО: Используйте этот эндпоинт только для резервного копирования!
    """
    try:
        import zipfile
        import tempfile

        print(f"📦 Запрос на скачивание всех паспортов из {ABS_UPLOADS_DIR}")

        # Проверяем что директория существует
        if not os.path.exists(ABS_UPLOADS_DIR):
            return JSONResponse(
                status_code=404,
                content={"ok": False, "error": f"Директория {ABS_UPLOADS_DIR} не найдена"}
            )

        # Получаем список всех файлов
        all_files = []
        for root, dirs, files in os.walk(ABS_UPLOADS_DIR):
            for file in files:
                # Пропускаем временные файлы
                if file.endswith(('_preprocessed.jpg', '_temp.jpg', '_temp_ocr.jpg')):
                    continue
                full_path = os.path.join(root, file)
                all_files.append(full_path)

        if not all_files:
            return JSONResponse(
                status_code=404,
                content={"ok": False, "error": "Паспортов не найдено"}
            )

        print(f"✅ Найдено {len(all_files)} файлов")

        # Создаем временный ZIP файл
        temp_zip = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
        temp_zip_path = temp_zip.name
        temp_zip.close()

        # Упаковываем все файлы в ZIP
        with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in all_files:
                # Получаем относительный путь для архива
                arcname = os.path.relpath(file_path, ABS_UPLOADS_DIR)
                zipf.write(file_path, arcname)
                print(f"  ✅ Добавлен: {arcname}")

        zip_size = os.path.getsize(temp_zip_path)
        print(f"📦 ZIP архив создан: {zip_size / 1024 / 1024:.2f} MB")

        # Возвращаем ZIP файл
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"passports_backup_{timestamp}.zip"

        return FileResponse(
            temp_zip_path,
            media_type='application/zip',
            filename=filename,
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            },
            background=None  # Не удаляем файл автоматически, удалим вручную после отправки
        )

    except Exception as e:
        print(f"❌ Ошибка создания архива: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )


@router.get("/api/admin/system-check")
async def system_check():
    """
    Проверка системы: OCR, директории, память
    """
    try:
        import sys
        import psutil

        result = {
            "ok": True,
            "timestamp": datetime.now().isoformat(),
            "checks": {}
        }

        # Проверка 1: Директория uploads
        result["checks"]["uploads_dir"] = {
            "path": ABS_UPLOADS_DIR,
            "exists": os.path.exists(ABS_UPLOADS_DIR),
            "writable": os.access(ABS_UPLOADS_DIR, os.W_OK) if os.path.exists(ABS_UPLOADS_DIR) else False
        }

        # Проверка 2: EasyOCR
        try:
            import easyocr
            result["checks"]["easyocr"] = {
                "installed": True,
                "version": getattr(easyocr, '__version__', 'unknown')
            }

            # Пробуем загрузить модели
            try:
                reader = easyocr.Reader(['en'], gpu=False, verbose=False)
                result["checks"]["easyocr"]["models_loaded"] = True
                result["checks"]["easyocr"]["status"] = "✅ Работает"
            except Exception as e:
                result["checks"]["easyocr"]["models_loaded"] = False
                result["checks"]["easyocr"]["error"] = str(e)
                result["checks"]["easyocr"]["status"] = f"❌ Ошибка загрузки моделей: {str(e)[:100]}"
        except ImportError:
            result["checks"]["easyocr"] = {
                "installed": False,
                "status": "❌ Не установлен"
            }

        # Проверка 3: Память
        try:
            memory = psutil.virtual_memory()
            result["checks"]["memory"] = {
                "total_mb": round(memory.total / 1024 / 1024, 2),
                "available_mb": round(memory.available / 1024 / 1024, 2),
                "used_percent": memory.percent,
                "status": "✅ OK" if memory.percent < 90 else "⚠️ Мало памяти"
            }
        except Exception:
            result["checks"]["memory"] = {"status": "❌ Не удалось проверить"}

        # Проверка 4: Torch (для EasyOCR)
        try:
            import torch
            result["checks"]["torch"] = {
                "installed": True,
                "version": torch.__version__,
                "cuda_available": torch.cuda.is_available()
            }
        except ImportError:
            result["checks"]["torch"] = {
                "installed": False,
                "status": "❌ Не установлен (требуется для EasyOCR)"
            }

        # Проверка 5: Python
        result["checks"]["python"] = {
            "version": sys.version,
            "executable": sys.executable
        }

        return result

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )


@router.get("/api/admin/passports-stats")
async def get_passports_stats():
    """
    Получить статистику по файлам паспортов
    """
    try:
        if not os.path.exists(ABS_UPLOADS_DIR):
            return {
                "ok": True,
                "total_files": 0,
                "total_size_mb": 0,
                "directory": ABS_UPLOADS_DIR,
                "exists": False
            }

        # Подсчитываем файлы
        total_files = 0
        total_size = 0
        file_types = {}

        for root, dirs, files in os.walk(ABS_UPLOADS_DIR):
            for file in files:
                # Пропускаем временные файлы
                if file.endswith(('_preprocessed.jpg', '_temp.jpg', '_temp_ocr.jpg')):
                    continue

                full_path = os.path.join(root, file)
                file_size = os.path.getsize(full_path)

                total_files += 1
                total_size += file_size

                # Группируем по расширениям
                ext = os.path.splitext(file)[1].lower()
                if ext not in file_types:
                    file_types[ext] = {"count": 0, "size": 0}
                file_types[ext]["count"] += 1
                file_types[ext]["size"] += file_size

        return {
            "ok": True,
            "total_files": total_files,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "file_types": file_types,
            "directory": ABS_UPLOADS_DIR,
            "exists": True
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )
