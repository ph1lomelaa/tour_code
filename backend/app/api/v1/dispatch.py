
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.services.document_rules import normalize_document
from db.models import (
    DispatchJob, DispatchJobStatus,
    Tour, TourStatus, Pilgrim, TourOffer,
)
from app.queue.tasks.dispatch import process_dispatch_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dispatch", tags=["dispatch"])


class DispatchPerson(BaseModel):
    surname: str = ""
    name: str = ""
    document: str = ""
    package_name: str = ""
    tour_name: str = ""


class DispatchTourSnapshot(BaseModel):
    spreadsheet_id: str = ""
    spreadsheet_name: str = ""
    sheet_name: str = ""
    date_start: str = ""
    date_end: str = ""
    days: int = 0
    route: str = ""
    departure_city: str = ""


class DispatchSelectionSnapshot(BaseModel):
    country: str = ""
    hotel: str = ""
    flight: str = ""
    remark: str = ""


class DispatchOverridesSnapshot(BaseModel):
    filialid: str = ""
    firmid: str = ""
    firmname: str = ""
    q_touragent: str = ""
    q_touragent_bin: str = ""


class DispatchResultsSnapshot(BaseModel):
    matched: List[DispatchPerson] = Field(default_factory=list)
    in_sheet_not_in_manifest: List[DispatchPerson] = Field(default_factory=list)
    in_manifest_not_in_sheet: List[DispatchPerson] = Field(default_factory=list)


class DispatchEnqueueRequest(BaseModel):
    tour: DispatchTourSnapshot
    selection: DispatchSelectionSnapshot
    dispatch_overrides: DispatchOverridesSnapshot = Field(default_factory=DispatchOverridesSnapshot)
    results: DispatchResultsSnapshot
    manifest_filename: str = ""
    max_attempts: Optional[int] = None


class DispatchJobResponse(BaseModel):
    id: str
    status: str
    attempt_count: int
    max_attempts: int
    celery_task_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    next_attempt_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    platform_mode: Optional[str] = None
    items_total: int = 0
    items_sent: int = 0
    progress_percent: int = 0


class DispatchJobsListResponse(BaseModel):
    jobs: List[DispatchJobResponse]


class DispatchJobDebugResponse(BaseModel):
    id: str
    status: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    prepared_payload: Dict[str, Any] = Field(default_factory=dict)
    response_payload: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    attempt_count: int
    max_attempts: int
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime] = None


def _save_normalized(db: Session, request: "DispatchEnqueueRequest") -> Tour:
    """Создаёт Tour, Pilgrim и TourOffer записи из снапшота."""
    t = request.tour
    s = request.selection

    tour = Tour(
        spreadsheet_id=t.spreadsheet_id,
        spreadsheet_name=t.spreadsheet_name,
        sheet_name=t.sheet_name,
        date_start=t.date_start,
        date_end=t.date_end,
        days=t.days,
        route=t.route or s.flight,
        departure_city=t.departure_city,
        airlines=settings.DISPATCH_DEFAULT_AIRLINE,
        country=s.country,
        hotel=s.hotel,
        remark=s.remark or None,
        manifest_filename=request.manifest_filename or None,
        status=TourStatus.QUEUED,
    )
    db.add(tour)
    db.flush()

    # --- Pilgrims ---
    def _add_pilgrims(persons: List[DispatchPerson]):
        for p in persons:
            pilgrim = Pilgrim(
                tour_id=tour.id,
                surname=(p.surname or "").strip().upper(),
                name=(p.name or "").strip().upper(),
                document=normalize_document((p.document or "").strip().upper()) or None,
                package_name=p.package_name or None,
                tour_code=None,
            )
            db.add(pilgrim)

    _add_pilgrims(request.results.matched)

    # --- Offers (outbound + return) ---
    route = (t.route or s.flight or "").strip().upper()
    if "-" in route:
        dep, arr = route.split("-", 1)
        airline = settings.DISPATCH_DEFAULT_AIRLINE
        db.add(TourOffer(
            tour_id=tour.id, offer_index=0, offer_type="flight",
            date_from=t.date_start, date_to=t.date_start,
            airlines=airline, airport=arr.strip(), country=s.country,
        ))
        db.add(TourOffer(
            tour_id=tour.id, offer_index=1, offer_type="flight",
            date_from=t.date_end, date_to=t.date_end,
            airlines=airline, airport=dep.strip(), country="Kazakhstan",
        ))

    db.flush()
    return tour


def _as_job_response(job: DispatchJob) -> DispatchJobResponse:
    raw_payload = job.payload if isinstance(job.payload, dict) else {}
    prepared_payload = job.prepared_payload if isinstance(job.prepared_payload, dict) else {}
    response_payload = job.response_payload if isinstance(job.response_payload, dict) else {}

    platform_mode = response_payload.get("mode") or prepared_payload.get("mode")

    progress_raw = response_payload.get("progress")
    if not isinstance(progress_raw, dict):
        progress_raw = {}

    def _to_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    items_total = _to_int(progress_raw.get("total_items"))
    items_sent = _to_int(progress_raw.get("sent_items"))

    if items_total <= 0:
        # Fallback 1: counters that worker writes during sending.
        items_total = max(items_total, _to_int(response_payload.get("json_items_total")))
        items_sent = max(items_sent, _to_int(response_payload.get("json_items_sent")))
        items_total = max(items_total, _to_int(response_payload.get("save_items_total")))
        items_sent = max(items_sent, _to_int(response_payload.get("save_items_sent")))

        # Fallback 2: original enqueue snapshot.
        payload_results = raw_payload.get("results") if isinstance(raw_payload, dict) else {}
        if isinstance(payload_results, dict):
            payload_matched = payload_results.get("matched")
            if isinstance(payload_matched, list):
                items_total = max(items_total, len(payload_matched))

        # Fallback 3: prebuilt payload shape by mode.
        if platform_mode == "test":
            items_total = max(items_total, len(prepared_payload.get("json_items") or []))
            items_sent = max(items_sent, _to_int(response_payload.get("json_items_sent")))
        elif platform_mode == "prod":
            items_total = max(items_total, len(prepared_payload.get("save_items") or []))
            items_sent = max(items_sent, _to_int(response_payload.get("save_items_sent")))
        elif platform_mode == "dry_run":
            items_total = max(items_total, _to_int(response_payload.get("items_total")))
            items_sent = max(items_sent, items_total)

    if job.status == DispatchJobStatus.SENT:
        if items_total <= 0 and items_sent > 0:
            items_total = items_sent
        if items_total > 0:
            items_sent = max(items_sent, items_total)

    if items_total > 0:
        progress_percent = int(round((items_sent / items_total) * 100))
        progress_percent = max(0, min(100, progress_percent))
    else:
        progress_percent = 0

    return DispatchJobResponse(
        id=str(job.id),
        status=job.status.value if hasattr(job.status, "value") else str(job.status),
        attempt_count=job.attempt_count,
        max_attempts=job.max_attempts,
        celery_task_id=job.celery_task_id,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
        next_attempt_at=job.next_attempt_at,
        sent_at=job.sent_at,
        platform_mode=str(platform_mode) if platform_mode else None,
        items_total=items_total,
        items_sent=items_sent,
        progress_percent=progress_percent,
    )


@router.post("/jobs/enqueue", response_model=DispatchJobResponse)
def enqueue_dispatch_job(request: DispatchEnqueueRequest, db: Session = Depends(get_db)):
    try:
        max_attempts = request.max_attempts or settings.DISPATCH_MAX_ATTEMPTS
        if max_attempts < 1:
            raise HTTPException(status_code=400, detail="max_attempts must be >= 1")

        # Сохраняем в нормализованные таблицы (tours, pilgrims, tour_offers)
        tour = _save_normalized(db, request)

        job = DispatchJob(
            tour_id=tour.id,
            status=DispatchJobStatus.QUEUED,
            payload=request.model_dump(),
            max_attempts=max_attempts,
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

        logger.info("🧾 Dispatch job queued: %s", job.id)
        return _as_job_response(job)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Ошибка enqueue dispatch job: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось поставить задачу в очередь: {e}")


@router.get("/jobs/{job_id}", response_model=DispatchJobResponse)
def get_dispatch_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(DispatchJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    return _as_job_response(job)


@router.get("/jobs", response_model=DispatchJobsListResponse)
def list_dispatch_jobs(limit: int = 20, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 100))
    rows = (
        db.query(DispatchJob)
        .order_by(desc(DispatchJob.created_at))
        .limit(limit)
        .all()
    )
    return DispatchJobsListResponse(jobs=[_as_job_response(row) for row in rows])


@router.get("/jobs/{job_id}/debug", response_model=DispatchJobDebugResponse)
def get_dispatch_job_debug(job_id: str, db: Session = Depends(get_db)):
    job = db.get(DispatchJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    return DispatchJobDebugResponse(
        id=str(job.id),
        status=job.status.value if hasattr(job.status, "value") else str(job.status),
        payload=job.payload if isinstance(job.payload, dict) else {},
        prepared_payload=job.prepared_payload if isinstance(job.prepared_payload, dict) else {},
        response_payload=job.response_payload if isinstance(job.response_payload, dict) else {},
        error_message=job.error_message,
        attempt_count=job.attempt_count,
        max_attempts=job.max_attempts,
        created_at=job.created_at,
        updated_at=job.updated_at,
        sent_at=job.sent_at,
    )


@router.post("/jobs/{job_id}/retry", response_model=DispatchJobResponse)
def retry_dispatch_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(DispatchJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    if job.status == DispatchJobStatus.SENT:
        raise HTTPException(status_code=400, detail="Задача уже отправлена")

    job.status = DispatchJobStatus.QUEUED
    job.error_message = None
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
        raise HTTPException(status_code=503, detail="Broker недоступен, повторная постановка не удалась")

    return _as_job_response(job)
