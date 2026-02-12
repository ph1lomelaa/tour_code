from datetime import datetime, timedelta
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from bull_project.bull_bot.core.google_sheets.writer import (
    clear_booking_in_sheets,
    write_cancelled_booking_red,
    write_rescheduled_booking_red,
    save_group_booking,
)
from bull_project.bull_bot.database.requests import (
    get_pending_requests,
    get_booking_by_id,
    get_approval_request,
    update_approval_status,
    delete_admin_request_inbox,
    mark_booking_cancelled,
    mark_booking_rescheduled,
    update_booking_fields,
    update_booking_row,
)


router = APIRouter()


async def _find_pilgrim_in_package_safe(table_id, sheet_name, package_name, guest_name):
    """
    Безопасный wrapper: не валим старт API, даже если функция не экспортируется из writer.
    """
    try:
        from bull_project.bull_bot.core.google_sheets import writer as _writer
        fn = getattr(_writer, "find_pilgrim_in_package", None)
        if fn:
            return await fn(table_id, sheet_name, package_name, guest_name)
    except Exception:
        pass
    return []


@router.get("/api/admin/requests")
async def admin_requests():
    try:
        pending = await get_pending_requests()
        result = []
        for req in pending:
            booking = await get_booking_by_id(req.booking_id)
            if not booking:
                continue
            group_members = booking.group_members if booking.group_members else []
            result.append({
                "id": req.id,
                "booking_id": booking.id,
                "request_type": req.request_type,
                "status": req.status,
                "created_at": req.created_at.isoformat() if req.created_at else None,
                "initiator_id": req.initiator_id,
                "comment": req.comment,
                "booking": {
                    "package_name": booking.package_name,
                    "sheet_name": booking.sheet_name,
                    "table_id": booking.table_id,
                    "sheet_row_number": booking.sheet_row_number,
                    "guest_last_name": booking.guest_last_name,
                    "guest_first_name": booking.guest_first_name,
                    "client_phone": booking.client_phone,
                    "placement_type": booking.placement_type,
                    "room_type": booking.room_type,
                    "meal_type": booking.meal_type,
                    "price": booking.price,
                    "amount_paid": booking.amount_paid,
                    "region": booking.region,
                    "departure_city": booking.departure_city,
                    "source": booking.source,
                    "comment": booking.comment,
                    "manager_name_text": booking.manager_name_text,
                    "group_members": group_members,
                },
            })
        return {"ok": True, "data": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/api/admin/requests/history")
async def admin_requests_history(
    request_type: str = Query("all"),  # all | cancel | reschedule
    start_date: str = Query(None),     # YYYY-MM-DD
    end_date: str = Query(None),       # YYYY-MM-DD
):
    try:
        if request_type not in ("all", "cancel", "reschedule"):
            return JSONResponse(status_code=400, content={"ok": False, "error": "invalid request_type"})

        if start_date:
            dt_from = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            dt_from = datetime.now() - timedelta(days=30)
        if end_date:
            dt_to = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
        else:
            dt_to = datetime.now()

        types = ("cancel", "reschedule") if request_type == "all" else (request_type,)
        result = []
        for r_type in types:
            pending_rows = await get_pending_requests()
            rows = [
                r for r in pending_rows
                if r.request_type == r_type
                and r.created_at
                and dt_from <= r.created_at <= dt_to
            ]
            for req in rows:
                booking = await get_booking_by_id(req.booking_id)
                if not booking:
                    continue
                result.append({
                    "id": req.id,
                    "booking_id": booking.id,
                    "request_type": req.request_type,
                    "status": req.status,
                    "created_at": req.created_at.isoformat() if req.created_at else None,
                    "initiator_id": req.initiator_id,
                    "comment": req.comment,
                    "booking": {
                        "package_name": booking.package_name,
                        "sheet_name": booking.sheet_name,
                        "sheet_row_number": booking.sheet_row_number,
                        "guest_last_name": booking.guest_last_name,
                        "guest_first_name": booking.guest_first_name,
                        "client_phone": booking.client_phone,
                        "manager_name_text": booking.manager_name_text,
                    },
                })
        result.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return {"ok": True, "data": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.post("/api/admin/requests/{req_id}/approve")
async def admin_request_approve(req_id: int):
    try:
        req = await get_approval_request(req_id)
        if not req or req.status != "pending":
            return JSONResponse(status_code=404, content={"ok": False, "error": "not found"})
        booking = await get_booking_by_id(req.booking_id)
        if not booking:
            return JSONResponse(status_code=404, content={"ok": False, "error": "booking not found"})

        if req.request_type == "cancel":
            sheets_cleared = False
            guest_name = f"{booking.guest_last_name} {booking.guest_first_name}"
            has_sheet_data = booking.sheet_row_number and booking.table_id and booking.sheet_name

            if has_sheet_data:
                try:
                    sheets_cleared = await clear_booking_in_sheets(
                        booking.table_id,
                        booking.sheet_name,
                        booking.sheet_row_number,
                        booking.package_name,
                        expected_guest_name=guest_name,  # 🔒 Проверяем имя перед удалением
                    )
                    if not sheets_cleared:
                        print(f"⚠️ Не удалось очистить бронь #{booking.id} в таблице (возможно несовпадение имени)")
                        # 🔍 Ищем паломника по всему пакету
                        matches = await _find_pilgrim_in_package_safe(
                            booking.table_id,
                            booking.sheet_name,
                            booking.package_name,
                            guest_name
                        )
                        if matches:
                            # Нашли - возвращаем найденные строки
                            return JSONResponse(
                                status_code=400,
                                content={
                                    "ok": False,
                                    "error": "name_mismatch_found",
                                    "message": f"Имя на строке {booking.sheet_row_number} не совпадает, но паломник найден в другом месте",
                                    "expected_name": guest_name,
                                    "expected_row": booking.sheet_row_number,
                                    "found_rows": [{"row": row, "name": name} for row, name in matches]
                                }
                            )
                        else:
                            # Не нашли
                            return JSONResponse(
                                status_code=400,
                                content={
                                    "ok": False,
                                    "error": "name_mismatch_not_found",
                                    "message": f"Паломник '{guest_name}' не найден ни на указанной строке, ни в пакете. Возможно данные уже удалены.",
                                    "expected_name": guest_name,
                                    "expected_row": booking.sheet_row_number
                                }
                            )
                except Exception as e:
                    print(f"❌ Ошибка при очистке брони #{booking.id} в таблице: {e}")
                    return JSONResponse(
                        status_code=500,
                        content={"ok": False, "error": f"Ошибка очистки: {str(e)}"}
                    )

            red_written = False
            if booking.table_id and booking.sheet_name and booking.package_name:
                try:
                    red_written = await write_cancelled_booking_red(
                        booking.table_id,
                        booking.sheet_name,
                        booking.package_name,
                        guest_name,
                    )
                    if not red_written:
                        print(f"⚠️ Не удалось записать отменённую бронь #{booking.id} в красный список")
                except Exception as e:
                    print(f"❌ Ошибка при записи в красный список для брони #{booking.id}: {e}")
                    red_written = False

            await mark_booking_cancelled(booking.id)
            await update_approval_status(req_id, "approved")
            await delete_admin_request_inbox(req_id)
            return {"ok": True, "status": "cancelled", "sheets_cleared": sheets_cleared, "red_written": red_written}

        if req.request_type == "reschedule":
            old_ids = []
            new_ids = []
            manager_comment = None
            if req.comment:
                try:
                    import json as _json
                    parsed = _json.loads(req.comment)
                    if isinstance(parsed, dict) and ("old_booking_ids" in parsed or "new_booking_ids" in parsed):
                        old_ids = [int(x) for x in (parsed.get("old_booking_ids") or []) if int(x) > 0]
                        new_ids = [int(x) for x in (parsed.get("new_booking_ids") or []) if int(x) > 0]
                        manager_comment = (parsed.get("comment") or "").strip() or None
                except Exception:
                    pass
            if not new_ids:
                new_ids = [booking.id]
            if not old_ids and req.comment and req.comment.startswith("old:"):
                try:
                    old_ids = [int(req.comment.split("old:")[1])]
                except Exception:
                    old_ids = []

            # Записываем новую бронь/группу в Sheets
            common_data = {
                'table_id': booking.table_id,
                'sheet_name': booking.sheet_name,
                'package_name': booking.package_name,
                'room_type': booking.room_type,
                'meal_type': booking.meal_type,
                'price': booking.price,
                'amount_paid': booking.amount_paid,
                'exchange_rate': booking.exchange_rate,
                'discount': booking.discount,
                'contract_number': booking.contract_number,
                'region': booking.region,
                'departure_city': booking.departure_city,
                'source': booking.source,
                'comment': manager_comment or booking.comment,
                'manager_name_text': booking.manager_name_text,
                'train': booking.train,
                'visa_status': booking.visa_status,
                'avia': booking.avia,
            }
            persons = []
            for bid in new_ids:
                nb = await get_booking_by_id(bid)
                if not nb:
                    continue
                persons.append({
                    "Last Name": nb.guest_last_name,
                    "First Name": nb.guest_first_name,
                    "Gender": nb.gender,
                    "Date of Birth": nb.date_of_birth,
                    "Document Number": nb.passport_num,
                    "Document Expiration": nb.passport_expiry,
                    "IIN": nb.guest_iin,
                    "client_phone": nb.client_phone,
                    "passport_image_path": nb.passport_image_path,
                })
            saved_rows = await save_group_booking(persons, common_data, booking.placement_type or 'separate')
            if saved_rows:
                for i, bid in enumerate(new_ids):
                    if i < len(saved_rows):
                        await update_booking_row(bid, saved_rows[i])
                    await update_booking_fields(bid, {"status": "new"})
            else:
                return JSONResponse(status_code=500, content={"ok": False, "error": "sheet write failed"})

            # 🔄 УДАЛЯЕМ СТАРЫЕ БРОНИ ПРИ ПЕРЕНОСЕ
            failed_cleanups = []

            for idx, old_id in enumerate(old_ids):
                old_booking = await get_booking_by_id(old_id)
                if not old_booking:
                    continue
                old_guest_name = f"{old_booking.guest_last_name} {old_booking.guest_first_name}"

                if old_booking.sheet_row_number and old_booking.table_id and old_booking.sheet_name:
                    try:
                        cleared = await clear_booking_in_sheets(
                            old_booking.table_id,
                            old_booking.sheet_name,
                            old_booking.sheet_row_number,
                            old_booking.package_name,
                            expected_guest_name=old_guest_name,
                        )
                        if cleared:
                            print(f"✅ Старая бронь #{old_booking.id} очищена из таблицы")
                            # Записываем в красный список
                            try:
                                await write_rescheduled_booking_red(
                                    old_booking.table_id,
                                    old_booking.sheet_name,
                                    old_booking.package_name,
                                    old_guest_name
                                )
                            except:
                                pass
                            target_new = new_ids[idx] if idx < len(new_ids) else new_ids[0]
                            await mark_booking_rescheduled(old_booking.id, comment=f"Перенесено в #{target_new}")
                        else:
                            # 🔍 Ищем паломника по пакету
                            print(f"⚠️ Имя не совпадает, ищем по пакету...")
                            matches = await _find_pilgrim_in_package_safe(
                                old_booking.table_id,
                                old_booking.sheet_name,
                                old_booking.package_name,
                                old_guest_name
                            )
                            failed_cleanups.append({
                                "booking_id": old_booking.id,
                                "guest_name": old_guest_name,
                                "expected_row": old_booking.sheet_row_number,
                                "idx": idx,
                                "found_rows": [{"row": row, "name": name} for row, name in matches] if matches else []
                            })
                    except Exception as e:
                        print(f"❌ ОШИБКА при очистке старой брони #{old_booking.id}: {e}")
                        failed_cleanups.append({
                            "booking_id": old_booking.id,
                            "guest_name": old_guest_name,
                            "expected_row": old_booking.sheet_row_number,
                            "idx": idx,
                            "found_rows": [],
                            "error": str(e)
                        })
                else:
                    # Нет данных для очистки - просто отмечаем
                    target_new = new_ids[idx] if idx < len(new_ids) else new_ids[0]
                    await mark_booking_rescheduled(old_booking.id, comment=f"Перенесено в #{target_new}")

            # Если есть проблемы с очисткой - возвращаем их
            if failed_cleanups:
                return JSONResponse(
                    status_code=400,
                    content={
                        "ok": False,
                        "error": "cleanup_failed",
                        "message": "Новые брони созданы, но не удалось очистить старые",
                        "saved_rows": saved_rows,
                        "new_ids": new_ids,
                        "failed_cleanups": failed_cleanups
                    }
                )

            await update_approval_status(req_id, "approved")
            await delete_admin_request_inbox(req_id)
            return {"ok": True, "status": "rescheduled", "saved_rows": saved_rows}

        return JSONResponse(status_code=400, content={"ok": False, "error": "unknown type"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.post("/api/admin/requests/{req_id}/reject")
async def admin_request_reject(req_id: int):
    try:
        req = await get_approval_request(req_id)
        if not req or req.status != "pending":
            return JSONResponse(status_code=404, content={"ok": False, "error": "not found"})
        booking = await get_booking_by_id(req.booking_id)
        if req.request_type == "reschedule":
            old_id = None
            if req.comment and req.comment.startswith("old:"):
                try:
                    old_id = int(req.comment.split("old:")[1])
                except Exception:
                    old_id = None
            if booking:
                await update_booking_fields(booking.id, {"status": "cancelled"})
            if old_id:
                await update_booking_fields(old_id, {"status": "new"})
        else:
            if booking:
                await update_booking_fields(booking.id, {"status": "new"})
        await update_approval_status(req_id, "rejected")
        await delete_admin_request_inbox(req_id)
        return {"ok": True, "status": "rejected"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.post("/api/admin/requests/{req_id}/approve-at-row/{row_number}")
async def admin_request_approve_at_row(req_id: int, row_number: int):
    try:
        req = await get_approval_request(req_id)
        if not req or req.status != "pending":
            return JSONResponse(status_code=404, content={"ok": False, "error": "not found"})
        if req.request_type != "cancel":
            return JSONResponse(status_code=400, content={"ok": False, "error": "not a cancel request"})

        booking = await get_booking_by_id(req.booking_id)
        if not booking:
            return JSONResponse(status_code=404, content={"ok": False, "error": "booking not found"})

        guest_name = f"{booking.guest_last_name} {booking.guest_first_name}"

        # Очищаем по указанной строке БЕЗ проверки имени (уже проверили при поиске)
        sheets_cleared = False
        if booking.table_id and booking.sheet_name:
            try:
                sheets_cleared = await clear_booking_in_sheets(
                    booking.table_id,
                    booking.sheet_name,
                    row_number,
                    booking.package_name,
                    expected_guest_name=None,  # Не проверяем - уже нашли
                )
            except Exception as e:
                print(f"❌ Ошибка при очистке строки {row_number}: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"ok": False, "error": f"Ошибка очистки: {str(e)}"}
                )

        if not sheets_cleared:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": "clear_failed", "message": f"Не удалось очистить строку {row_number}"}
            )

        # Записываем в красный список
        red_written = False
        try:
            red_written = await write_cancelled_booking_red(
                booking.table_id,
                booking.sheet_name,
                booking.package_name,
                guest_name
            )
        except Exception as e:
            print(f"⚠️ Не удалось записать в красный список: {e}")

        # Обновляем номер строки в БД
        await update_booking_fields(booking.id, {"sheet_row_number": row_number})
        await mark_booking_cancelled(booking.id)
        await update_approval_status(req_id, "approved")
        await delete_admin_request_inbox(req_id)

        return {
            "ok": True,
            "status": "cancelled",
            "sheets_cleared": sheets_cleared,
            "red_written": red_written,
            "cleared_row": row_number,
            "message": f"Бронь отменена, очищена строка {row_number}"
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.post("/api/admin/requests/{req_id}/reschedule-clear-row")
async def admin_reschedule_clear_row(req_id: int, booking_id: int, row_number: int, idx: int = 0):
    try:
        req = await get_approval_request(req_id)
        if not req:
            return JSONResponse(status_code=404, content={"ok": False, "error": "not found"})

        booking = await get_booking_by_id(booking_id)
        if not booking:
            return JSONResponse(status_code=404, content={"ok": False, "error": "booking not found"})

        guest_name = f"{booking.guest_last_name} {booking.guest_first_name}"

        # Очищаем по указанной строке
        sheets_cleared = False
        if booking.table_id and booking.sheet_name:
            try:
                sheets_cleared = await clear_booking_in_sheets(
                    booking.table_id,
                    booking.sheet_name,
                    row_number,
                    booking.package_name,
                    expected_guest_name=None,
                )
            except Exception as e:
                print(f"❌ Ошибка при очистке строки {row_number}: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"ok": False, "error": f"Ошибка очистки: {str(e)}"}
                )

        if not sheets_cleared:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": "clear_failed", "message": f"Не удалось очистить строку {row_number}"}
            )

        # Записываем в красный список (перенос)
        try:
            await write_rescheduled_booking_red(
                booking.table_id,
                booking.sheet_name,
                booking.package_name,
                guest_name
            )
        except Exception as e:
            print(f"⚠️ Не удалось записать в красный список: {e}")

        # Получаем new_ids из комментария заявки
        new_ids = []
        if req.comment:
            try:
                import json as _json
                parsed = _json.loads(req.comment)
                if isinstance(parsed, dict):
                    new_ids = [int(x) for x in (parsed.get("new_booking_ids") or []) if int(x) > 0]
            except:
                pass
        if not new_ids:
            new_ids = [req.booking_id]

        # Обновляем номер строки и отмечаем как перенесённую
        await update_booking_fields(booking.id, {"sheet_row_number": row_number})
        target_new = new_ids[idx] if idx < len(new_ids) else new_ids[0]
        await mark_booking_rescheduled(booking.id, comment=f"Перенесено в #{target_new}")

        return {
            "ok": True,
            "status": "cleared",
            "cleared_row": row_number,
            "booking_id": booking_id,
            "message": f"Строка {row_number} очищена, бронь #{booking_id} отмечена как перенесённая"
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.post("/api/admin/requests/{req_id}/reschedule-skip")
async def admin_reschedule_skip_cleanup(req_id: int):
    """
    Пропустить очистку старых броней и завершить перенос.
    """
    try:
        req = await get_approval_request(req_id)
        if not req:
            return JSONResponse(status_code=404, content={"ok": False, "error": "not found"})

        await update_approval_status(req_id, "approved")
        await delete_admin_request_inbox(req_id)

        return {
            "ok": True,
            "status": "completed",
            "message": "Перенос завершён, очистка пропущена"
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
