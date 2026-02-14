from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List
import logging

from app.google_sheet_parser.manifest_parser import manifest_parser
from app.google_sheet_parser.sheet_pilgrim_parser import sheet_pilgrim_parser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/manifest", tags=["manifest"])


class Pilgrim(BaseModel):
    surname: str
    name: str
    document: str = ""
    iin: str = ""
    manager: str = ""


class CompareRequest(BaseModel):
    spreadsheet_id: str
    sheet_name: str
    manifest_pilgrims: List[Pilgrim]


class CompareResponse(BaseModel):
    success: bool
    # Те кто есть и в манифесте и в таблице
    matched: List[Pilgrim]
    # Есть в таблице, но НЕТ в манифесте
    in_sheet_not_in_manifest: List[Pilgrim]
    # Есть в манифесте, но НЕТ в таблице
    in_manifest_not_in_sheet: List[Pilgrim]
    message: str = ""


@router.post("/upload")
async def upload_manifest(file: UploadFile = File(...)):
    try:
        # Проверяем расширение файла
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(
                status_code=400,
                detail="Неверный формат файла. Поддерживаются только .xlsx и .xls"
            )

        logger.info(f"Загрузка манифеста: {file.filename}")

        # Читаем содержимое файла
        content = await file.read()

        # Парсим манифест
        pilgrims = manifest_parser.parse_manifest(content, file.filename)

        return {
            "success": True,
            "pilgrims": pilgrims,
            "count": len(pilgrims),
            "message": f"Загружено {len(pilgrims)} паломников"
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка загрузки манифеста: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка обработки файла: {str(e)}"
        )


@router.post("/compare", response_model=CompareResponse)
async def compare_with_sheet(request: CompareRequest):
    try:
        logger.info(
            f"Сравнение манифеста с листом '{request.sheet_name}' "
            f"(манифест: {len(request.manifest_pilgrims)} чел.)"
        )

        # Парсим паломников из Google Sheets
        sheet_pilgrims = sheet_pilgrim_parser.parse_sheet_pilgrims(
            request.spreadsheet_id,
            request.sheet_name
        )

        # Создаём множества для быстрого поиска (по номеру паспорта)
        manifest_docs = {p.document.upper() for p in request.manifest_pilgrims if p.document}
        sheet_docs_map = {
            p["document"].upper(): p
            for p in sheet_pilgrims
            if p.get("document")
        }

        # Те кто есть и в манифесте и в таблице
        matched = []
        for mp in request.manifest_pilgrims:
            doc = mp.document.upper()
            if doc in sheet_docs_map:
                sp = sheet_docs_map[doc]
                matched.append(Pilgrim(
                    surname=sp["surname"],
                    name=sp["name"],
                    document=sp["document"],
                    iin=sp.get("iin", ""),
                    manager=sp["manager"]
                ))

        # Есть в таблице, но НЕТ в манифесте
        in_sheet_not_in_manifest = []
        for doc, sp in sheet_docs_map.items():
            if doc not in manifest_docs:
                in_sheet_not_in_manifest.append(Pilgrim(
                    surname=sp["surname"],
                    name=sp["name"],
                    document=sp["document"],
                    iin=sp.get("iin", ""),
                    manager=sp["manager"]
                ))

        # Есть в манифесте, но НЕТ в таблице
        in_manifest_not_in_sheet = []
        for mp in request.manifest_pilgrims:
            doc = mp.document.upper()
            if not doc or doc not in sheet_docs_map:
                in_manifest_not_in_sheet.append(mp)

        logger.info(
            f"✅ Сравнение завершено: "
            f"совпадений={len(matched)}, "
            f"только в таблице={len(in_sheet_not_in_manifest)}, "
            f"только в манифесте={len(in_manifest_not_in_sheet)}"
        )

        return CompareResponse(
            success=True,
            matched=matched,
            in_sheet_not_in_manifest=in_sheet_not_in_manifest,
            in_manifest_not_in_sheet=in_manifest_not_in_sheet,
            message="Сравнение завершено успешно"
        )

    except Exception as e:
        logger.error(f"Ошибка сравнения: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка сравнения: {str(e)}"
        )
