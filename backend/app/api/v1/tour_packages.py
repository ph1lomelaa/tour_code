from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.queue.tasks.dispatch import process_dispatch_job
from db.models import DispatchJob, DispatchJobStatus, Pilgrim, Tour


router = APIRouter(prefix="/tour-packages", tags=["tour-packages"])


class TourPackageSummary(BaseModel):
    id: str
    sheet_name: str = ""
    date_start: str = ""
    date_end: str = ""
    route: str = ""
    departure_city: str = ""
    pilgrims_count: int
    created_at: datetime


class TourPackageListResponse(BaseModel):
    items: List[TourPackageSummary]
    total: int


class MatchedPilgrimRow(BaseModel):
    id: str
    surname: str
    name: str
    document: str = ""
    package_name: str = ""
    tour_code: str = ""


class ComparePilgrimRow(BaseModel):
    surname: str
    name: str
    document: str = ""
    package_name: str = ""
    tour_name: str = ""


class DispatchOverridesResponse(BaseModel):
    filialid: str = ""
    firmid: str = ""
    firmname: str = ""
    q_touragent: str = ""
    q_touragent_bin: str = ""


class TourPackageDetailResponse(BaseModel):
    id: str
    spreadsheet_id: str = ""
    spreadsheet_name: str = ""
    sheet_name: str = ""
    date_start: str = ""
    date_end: str = ""
    days: int = 0
    route: str = ""
    departure_city: str = ""
    country: str = ""
    hotel: str = ""
    remark: str = ""
    manifest_filename: str = ""
    dispatch_overrides: DispatchOverridesResponse = Field(default_factory=DispatchOverridesResponse)
    matched: List[MatchedPilgrimRow]
    in_sheet_not_in_manifest: List[ComparePilgrimRow]
    in_manifest_not_in_sheet: List[ComparePilgrimRow]


class AddMatchedPilgrimRequest(BaseModel):
    full_name: str
    document: str = ""
    package_name: str = ""


class DispatchSinglePerson(BaseModel):
    surname: str
    name: str = ""
    document: str = ""
    package_name: str = ""
    tour_name: str = ""


class DispatchSingleOverrides(BaseModel):
    filialid: str = ""
    firmid: str = ""
    firmname: str = ""
    q_touragent: str = ""
    q_touragent_bin: str = ""


class EnqueueSingleDispatchRequest(BaseModel):
    person: DispatchSinglePerson
    dispatch_overrides: DispatchSingleOverrides = Field(default_factory=DispatchSingleOverrides)


class EnqueueSingleDispatchResponse(BaseModel):
    id: str
    status: str
    attempt_count: int
    max_attempts: int
    celery_task_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


def _parse_compare_rows(raw_rows: object) -> List[ComparePilgrimRow]:
    if not isinstance(raw_rows, list):
        return []

    rows: List[ComparePilgrimRow] = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        rows.append(
            ComparePilgrimRow(
                surname=str(raw.get("surname") or "").strip().upper(),
                name=str(raw.get("name") or "").strip().upper(),
                document=str(raw.get("document") or "").strip().upper(),
                package_name=str(raw.get("package_name") or "").strip(),
                tour_name=str(raw.get("tour_name") or "").strip(),
            )
        )
    return rows


def _split_full_name(full_name: str) -> tuple[str, str]:
    cleaned = " ".join((full_name or "").strip().split())
    if not cleaned:
        raise HTTPException(status_code=400, detail="Введите ФИО")

    parts = cleaned.split(" ")
    surname = parts[0].upper()
    name = " ".join(parts[1:]).upper() if len(parts) > 1 else ""
    if not name:
        raise HTTPException(status_code=400, detail="Введите ФИО в формате: Фамилия Имя")
    return surname, name


def _as_enqueue_single_dispatch_response(job: DispatchJob) -> EnqueueSingleDispatchResponse:
    return EnqueueSingleDispatchResponse(
        id=str(job.id),
        status=job.status.value if hasattr(job.status, "value") else str(job.status),
        attempt_count=job.attempt_count,
        max_attempts=job.max_attempts,
        celery_task_id=job.celery_task_id,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("", response_model=TourPackageListResponse)
def list_tour_packages(db: Session = Depends(get_db)):
    rows = (
        db.query(
            Tour,
            func.count(Pilgrim.id).label("pilgrims_count"),
        )
        .outerjoin(Pilgrim, Pilgrim.tour_id == Tour.id)
        .group_by(Tour.id)
        .order_by(desc(Tour.created_at))
        .all()
    )

    items = [
        TourPackageSummary(
            id=str(tour.id),
            sheet_name=tour.sheet_name or "",
            date_start=tour.date_start or "",
            date_end=tour.date_end or "",
            route=tour.route or "",
            departure_city=tour.departure_city or "",
            pilgrims_count=int(pilgrims_count or 0),
            created_at=tour.created_at,
        )
        for tour, pilgrims_count in rows
    ]

    return TourPackageListResponse(items=items, total=len(items))


@router.get("/{tour_id}", response_model=TourPackageDetailResponse)
def get_tour_package(tour_id: str, db: Session = Depends(get_db)):
    tour = db.get(Tour, tour_id)
    if tour is None:
        raise HTTPException(status_code=404, detail="Тур не найден")

    matched_rows_db = (
        db.query(Pilgrim)
        .filter(Pilgrim.tour_id == tour.id)
        .order_by(Pilgrim.surname.asc(), Pilgrim.name.asc(), Pilgrim.created_at.asc())
        .all()
    )
    matched = [
        MatchedPilgrimRow(
            id=str(row.id),
            surname=row.surname,
            name=row.name,
            document=row.document or "",
            package_name=row.package_name or "",
            tour_code=row.tour_code or "",
        )
        for row in matched_rows_db
    ]

    all_jobs = (
        db.query(DispatchJob)
        .filter(DispatchJob.tour_id == tour.id)
        .order_by(desc(DispatchJob.created_at))
        .all()
    )

    latest_job = all_jobs[0] if all_jobs else None
    snapshot_job = None
    for candidate in all_jobs:
        payload = candidate.payload if isinstance(candidate.payload, dict) else {}
        if payload.get("is_incremental_dispatch"):
            continue
        snapshot_job = candidate
        break
    if snapshot_job is None:
        snapshot_job = latest_job

    payload_results = {}
    payload_dispatch_overrides = {}
    if snapshot_job and isinstance(snapshot_job.payload, dict):
        payload_results = snapshot_job.payload.get("results") or {}
        payload_dispatch_overrides = snapshot_job.payload.get("dispatch_overrides") or {}
    if not isinstance(payload_dispatch_overrides, dict):
        payload_dispatch_overrides = {}

    in_sheet_not_in_manifest = _parse_compare_rows(
        payload_results.get("in_sheet_not_in_manifest") if isinstance(payload_results, dict) else []
    )
    in_manifest_not_in_sheet = _parse_compare_rows(
        payload_results.get("in_manifest_not_in_sheet") if isinstance(payload_results, dict) else []
    )

    return TourPackageDetailResponse(
        id=str(tour.id),
        spreadsheet_id=tour.spreadsheet_id or "",
        spreadsheet_name=tour.spreadsheet_name or "",
        sheet_name=tour.sheet_name or "",
        date_start=tour.date_start or "",
        date_end=tour.date_end or "",
        days=int(tour.days or 0),
        route=tour.route or "",
        departure_city=tour.departure_city or "",
        country=tour.country or "",
        hotel=tour.hotel or "",
        remark=tour.remark or "",
        manifest_filename=tour.manifest_filename or "",
        dispatch_overrides=DispatchOverridesResponse(
            filialid=str(payload_dispatch_overrides.get("filialid") or "").strip(),
            firmid=str(payload_dispatch_overrides.get("firmid") or "").strip(),
            firmname=str(payload_dispatch_overrides.get("firmname") or "").strip(),
            q_touragent=str(payload_dispatch_overrides.get("q_touragent") or "").strip(),
            q_touragent_bin=str(payload_dispatch_overrides.get("q_touragent_bin") or "").strip(),
        ),
        matched=matched,
        in_sheet_not_in_manifest=in_sheet_not_in_manifest,
        in_manifest_not_in_sheet=in_manifest_not_in_sheet,
    )


@router.post("/{tour_id}/dispatch-single", response_model=EnqueueSingleDispatchResponse)
def enqueue_tour_dispatch_single(
    tour_id: str,
    payload: EnqueueSingleDispatchRequest,
    db: Session = Depends(get_db),
):
    tour = db.get(Tour, tour_id)
    if tour is None:
        raise HTTPException(status_code=404, detail="Тур не найден")

    surname = (payload.person.surname or "").strip().upper()
    name = (payload.person.name or "").strip().upper()
    document = (payload.person.document or "").strip().upper()
    package_name = (payload.person.package_name or "").strip()
    tour_name = (payload.person.tour_name or tour.sheet_name or "").strip()
    if not surname:
        raise HTTPException(status_code=400, detail="Фамилия обязательна")
    if not document:
        raise HTTPException(status_code=400, detail="Паспорт обязателен")

    snapshot_payload = {
        "tour": {
            "spreadsheet_id": tour.spreadsheet_id or "",
            "spreadsheet_name": tour.spreadsheet_name or "",
            "sheet_name": tour.sheet_name or "",
            "date_start": tour.date_start or "",
            "date_end": tour.date_end or "",
            "days": int(tour.days or 0),
            "route": tour.route or "",
            "departure_city": tour.departure_city or "",
        },
        "selection": {
            "country": tour.country or "",
            "hotel": tour.hotel or "",
            "flight": tour.route or "",
            "remark": tour.remark or "",
        },
        "dispatch_overrides": {
            "filialid": (payload.dispatch_overrides.filialid or "").strip(),
            "firmid": (payload.dispatch_overrides.firmid or "").strip(),
            "firmname": (payload.dispatch_overrides.firmname or "").strip(),
            "q_touragent": (payload.dispatch_overrides.q_touragent or "").strip(),
            "q_touragent_bin": (payload.dispatch_overrides.q_touragent_bin or "").strip(),
        },
        "results": {
            "matched": [
                {
                    "surname": surname,
                    "name": name,
                    "document": document,
                    "package_name": package_name,
                    "tour_name": tour_name,
                }
            ],
            "in_sheet_not_in_manifest": [],
            "in_manifest_not_in_sheet": [],
        },
        "manifest_filename": tour.manifest_filename or "",
        "is_incremental_dispatch": True,
    }

    job = DispatchJob(
        tour_id=tour.id,
        status=DispatchJobStatus.QUEUED,
        payload=snapshot_payload,
        max_attempts=settings.DISPATCH_MAX_ATTEMPTS,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        async_result = process_dispatch_job.delay(str(job.id))
        job.celery_task_id = async_result.id
        db.commit()
        db.refresh(job)
    except Exception as queue_error:
        job.status = DispatchJobStatus.FAILED
        job.error_message = f"Broker enqueue failed: {queue_error}"
        db.commit()
        db.refresh(job)
        raise HTTPException(status_code=503, detail="Broker недоступен, задача не поставлена в очередь")

    return _as_enqueue_single_dispatch_response(job)


@router.post("/{tour_id}/pilgrims", response_model=MatchedPilgrimRow)
def add_pilgrim_to_tour(
    tour_id: str,
    payload: AddMatchedPilgrimRequest,
    db: Session = Depends(get_db),
):
    tour = db.get(Tour, tour_id)
    if tour is None:
        raise HTTPException(status_code=404, detail="Тур не найден")

    surname, name = _split_full_name(payload.full_name)
    document = (payload.document or "").strip().upper()
    package_name = (payload.package_name or "").strip()

    existing = None
    if document:
        existing = (
            db.query(Pilgrim)
            .filter(Pilgrim.tour_id == tour.id, func.upper(func.coalesce(Pilgrim.document, "")) == document)
            .first()
        )
    if existing is None:
        existing = (
            db.query(Pilgrim)
            .filter(
                Pilgrim.tour_id == tour.id,
                Pilgrim.surname == surname,
                Pilgrim.name == name,
                func.upper(func.coalesce(Pilgrim.document, "")) == document,
            )
            .first()
        )

    if existing:
        if package_name and not existing.package_name:
            existing.package_name = package_name
            db.commit()
            db.refresh(existing)
        return MatchedPilgrimRow(
            id=str(existing.id),
            surname=existing.surname,
            name=existing.name,
            document=existing.document or "",
            package_name=existing.package_name or "",
            tour_code=existing.tour_code or "",
        )

    row = Pilgrim(
        tour_id=str(tour.id),
        surname=surname,
        name=name,
        document=document or None,
        package_name=package_name or None,
        tour_code=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return MatchedPilgrimRow(
        id=str(row.id),
        surname=row.surname,
        name=row.name,
        document=row.document or "",
        package_name=row.package_name or "",
        tour_code=row.tour_code or "",
    )
