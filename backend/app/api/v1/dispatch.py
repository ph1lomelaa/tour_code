
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from db.models import (
    DispatchJob, DispatchJobStatus,
    Tour, TourStatus, Pilgrim, TourOffer,
)
from app.tasks.dispatch import process_dispatch_job

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


class DispatchResultsSnapshot(BaseModel):
    matched: List[DispatchPerson] = Field(default_factory=list)
    in_sheet_not_in_manifest: List[DispatchPerson] = Field(default_factory=list)
    in_manifest_not_in_sheet: List[DispatchPerson] = Field(default_factory=list)


class DispatchEnqueueRequest(BaseModel):
    tour: DispatchTourSnapshot
    selection: DispatchSelectionSnapshot
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


class DispatchJobsListResponse(BaseModel):
    jobs: List[DispatchJobResponse]


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
                document=(p.document or "").strip().upper() or None,
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
