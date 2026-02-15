from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.services.document_rules import normalize_document
from db.models import Pilgrim


router = APIRouter(prefix="/pilgrims", tags=["pilgrims"])


class PilgrimListItem(BaseModel):
    id: str
    surname: str
    name: str
    document: str = ""
    package_name: str = ""
    tour_code: str = ""
    tour_id: str
    tour_name: str = ""
    tour_route: str = ""
    date_start: str = ""
    date_end: str = ""


class PilgrimListResponse(BaseModel):
    items: List[PilgrimListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


@router.get("", response_model=PilgrimListResponse)
def list_pilgrims(
    surname: str = Query(default="", description="Фамилия (частичное совпадение)"),
    name: str = Query(default="", description="Имя (частичное совпадение)"),
    document: str = Query(default="", description="Номер документа (частичное совпадение)"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Pilgrim).options(joinedload(Pilgrim.tour))

    surname_filter = surname.strip()
    if surname_filter:
        query = query.filter(
            func.upper(Pilgrim.surname).contains(surname_filter.upper())
        )

    name_filter = name.strip()
    if name_filter:
        query = query.filter(
            func.upper(Pilgrim.name).contains(name_filter.upper())
        )

    document_filter = normalize_document(document.strip())
    if document_filter:
        query = query.filter(
            func.upper(func.coalesce(Pilgrim.document, "")).contains(document_filter.upper())
        )

    total = query.count()
    total_pages = (total + page_size - 1) // page_size if total else 0
    offset = (page - 1) * page_size

    rows = (
        query.order_by(Pilgrim.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    items = []
    for row in rows:
        tour = row.tour
        items.append(
            PilgrimListItem(
                id=str(row.id),
                surname=row.surname,
                name=row.name,
                document=normalize_document(row.document or ""),
                package_name=row.package_name or "",
                tour_code=row.tour_code or "",
                tour_id=str(row.tour_id),
                tour_name=(tour.sheet_name if tour else "") or "",
                tour_route=(tour.route if tour else "") or "",
                date_start=(tour.date_start if tour else "") or "",
                date_end=(tour.date_end if tour else "") or "",
            )
        )

    return PilgrimListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
