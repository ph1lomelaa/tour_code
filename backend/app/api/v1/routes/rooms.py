from fastapi import APIRouter
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from bull_project.bull_bot.core.google_sheets.client import get_sheet_data
from bull_project.bull_bot.core.google_sheets.allocator import get_open_rooms_for_manual_selection
from bull_project.bull_bot.api.utils import normalize_sheet_and_package


router = APIRouter()


@router.get("/api/rooms")
async def api_rooms(
    table_id: str,
    sheet_name: str,
    package_name: str,
    count: int = 1,
    room_type: str = "Quad",
    gender: str = "M",
):
    """Получение списка свободных комнат."""
    s_name, p_name = normalize_sheet_and_package(sheet_name, package_name)
    try:
        all_rows = await run_in_threadpool(get_sheet_data, table_id, s_name)
        rooms = await run_in_threadpool(
            get_open_rooms_for_manual_selection,
            all_rows,
            p_name,
            count,
            room_type,
            gender,
        )
        return {"ok": True, "found": len(rooms) > 0, "rooms": rooms}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

