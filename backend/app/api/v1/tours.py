
from fastapi import APIRouter, HTTPException
from typing import List
from pydantic import BaseModel
import logging

from app.google_sheet_parser.google_sheets_service import google_sheets_service
from app.google_sheet_parser.sheet_pilgrim_parser import sheet_pilgrim_parser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tours", tags=["tours"])
class SearchByDateRequest(BaseModel):
    date_short: str  # "17.02"

    class Config:
        json_schema_extra = {
            "example": {
                "date_short": "17.02"
            }
        }


class TourOption(BaseModel):
    spreadsheet_id: str
    spreadsheet_name: str
    sheet_name: str
    date_start: str  # "17.02.2026"
    date_end: str    # "24.02.2026"
    days: int        # 7
    route: str       # "ALA-JED"
    departure_city: str  # "Almaty"

    class Config:
        json_schema_extra = {
            "example": {
                "spreadsheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
                "spreadsheet_name": "Таблица 2026",
                "sheet_name": "17.02.2026 ALA-JED",
                "date_start": "17.02.2026",
                "date_end": "24.02.2026",
                "days": 7,
                "route": "ALA-JED",
                "departure_city": "Almaty"
            }
        }


class SearchByDateResponse(BaseModel):
    success: bool
    found_count: int
    tours: List[TourOption]
    message: str = ""


class SheetPilgrimsRequest(BaseModel):
    spreadsheet_id: str
    sheet_name: str

    class Config:
        json_schema_extra = {
            "example": {
                "spreadsheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
                "sheet_name": "17.02.2026-24.02.2026 ALA-JED"
            }
        }


class PilgrimInPackage(BaseModel):
    surname: str
    name: str
    document: str = ""
    iin: str = ""
    manager: str = ""
    room_type: str = ""
    meal_type: str = ""


class PackageInfo(BaseModel):
    package_name: str
    pilgrims: List[PilgrimInPackage]
    count: int


class SheetPilgrimsResponse(BaseModel):
    success: bool
    packages: List[PackageInfo]
    total_count: int
    message: str = ""

@router.post("/search-by-date", response_model=SearchByDateResponse)
async def search_tours_by_date(
    request: SearchByDateRequest,
):
    try:
        logger.info(f"Поиск туров по дате: {request.date_short}")

        # Ищем в Google Sheets
        sheets_results = google_sheets_service.find_sheets_by_date(request.date_short)

        if not sheets_results:
            return SearchByDateResponse(
                success=False,
                found_count=0,
                tours=[],
                message=f"Туры на дату {request.date_short} не найдены"
            )

        # Преобразуем результаты
        tours = []
        for item in sheets_results:
            # Определяем город вылета по маршруту
            route = item.get("route", "")
            departure_city = _get_departure_city(route)

            tours.append(TourOption(
                spreadsheet_id=item["spreadsheet_id"],
                spreadsheet_name=item["spreadsheet_name"],
                sheet_name=item["sheet_name"],
                date_start=item["date_start"],
                date_end=item["date_end"],
                days=item["days"],
                route=route or "Не указан",
                departure_city=departure_city
            ))

        logger.info(f"✅ Найдено {len(tours)} туров")

        return SearchByDateResponse(
            success=True,
            found_count=len(tours),
            tours=tours,
            message=f"Найдено {len(tours)} вариантов тура"
        )

    except Exception as e:
        logger.error(f"❌ Ошибка поиска туров: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка поиска туров: {str(e)}"
        )


def _get_departure_city(route: str) -> str:
    route_map = {
        "ALA-JED": "Almaty",
        "ALA-MED": "Almaty",
        "NQZ-JED": "Nur-Sultan",
        "NQZ-MED": "Nur-Sultan",
        "NQZ-ALA": "Nur-Sultan"
    }
    return route_map.get(route, "Не указан")


@router.get("/test")
async def test_google_sheets():
    try:
        tables = google_sheets_service.get_all_spreadsheets()
        return {
            "success": True,
            "tables_count": len(tables),
            "tables": list(tables.keys())[:5]  # Первые 5
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sheet-pilgrims", response_model=SheetPilgrimsResponse)
async def get_sheet_pilgrims(request: SheetPilgrimsRequest):
    try:
        logger.info(
            f"Запрос паломников из листа '{request.sheet_name}' "
            f"(spreadsheet: {request.spreadsheet_id})"
        )

        packages_raw = sheet_pilgrim_parser.parse_sheet_by_packages(
            request.spreadsheet_id,
            request.sheet_name
        )

        packages = []
        total = 0

        for pkg in packages_raw:
            pilgrims = [
                PilgrimInPackage(**p) for p in pkg["pilgrims"]
            ]
            packages.append(PackageInfo(
                package_name=pkg["package_name"],
                pilgrims=pilgrims,
                count=pkg["count"]
            ))
            total += pkg["count"]

        return SheetPilgrimsResponse(
            success=True,
            packages=packages,
            total_count=total,
            message=f"Найдено {len(packages)} пакетов, всего {total} паломников"
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка получения паломников: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения паломников: {str(e)}"
        )


@router.get("/debug/sheets/{table_name}")
async def debug_get_sheets(table_name: str):
    try:
        tables = google_sheets_service.get_all_spreadsheets()
        table_id = None
        for name, tid in tables.items():
            if table_name.lower() in name.lower():
                table_id = tid
                break

        if not table_id:
            raise HTTPException(status_code=404, detail=f"Таблица {table_name} не найдена")

        sheets = google_sheets_service.get_sheet_names(table_id)

        return {
            "success": True,
            "table_name": table_name,
            "sheets_count": len(sheets),
            "sheets": sheets[:20]  # Первые 20
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
