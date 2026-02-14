from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from db.models import DispatchJob, DispatchJobStatus, Pilgrim, Tour


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardStatsResponse(BaseModel):
    total_tours: int
    total_pilgrims: int
    sent_jobs: int
    queued_jobs: int
    failed_jobs: int


class RecentTourItem(BaseModel):
    id: str
    sheet_name: str = ""
    route: str = ""
    date_start: str = ""
    date_end: str = ""
    pilgrims_count: int = 0
    dispatch_status: Optional[str] = None
    created_at: datetime


class RecentJobItem(BaseModel):
    id: str
    tour_sheet_name: str = ""
    status: str
    attempt_count: int
    max_attempts: int
    error_message: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None


class DashboardRecentResponse(BaseModel):
    recent_tours: List[RecentTourItem]
    recent_jobs: List[RecentJobItem]


@router.get("/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_tours = db.query(func.count(Tour.id)).scalar() or 0
    total_pilgrims = db.query(func.count(Pilgrim.id)).scalar() or 0
    sent_jobs = (
        db.query(func.count(DispatchJob.id))
        .filter(DispatchJob.status == DispatchJobStatus.SENT)
        .scalar()
        or 0
    )
    queued_jobs = (
        db.query(func.count(DispatchJob.id))
        .filter(DispatchJob.status.in_([DispatchJobStatus.QUEUED, DispatchJobStatus.SENDING]))
        .scalar()
        or 0
    )
    failed_jobs = (
        db.query(func.count(DispatchJob.id))
        .filter(DispatchJob.status == DispatchJobStatus.FAILED)
        .scalar()
        or 0
    )

    return DashboardStatsResponse(
        total_tours=int(total_tours),
        total_pilgrims=int(total_pilgrims),
        sent_jobs=int(sent_jobs),
        queued_jobs=int(queued_jobs),
        failed_jobs=int(failed_jobs),
    )


@router.get("/recent", response_model=DashboardRecentResponse)
def get_dashboard_recent(db: Session = Depends(get_db)):
    tours_with_counts = (
        db.query(Tour, func.count(Pilgrim.id).label("pilgrims_count"))
        .outerjoin(Pilgrim, Pilgrim.tour_id == Tour.id)
        .group_by(Tour.id)
        .order_by(desc(Tour.created_at))
        .limit(5)
        .all()
    )

    recent_tours: list[RecentTourItem] = []
    for tour, pilgrims_count in tours_with_counts:
        latest_job = (
            db.query(DispatchJob)
            .filter(DispatchJob.tour_id == tour.id)
            .order_by(desc(DispatchJob.created_at))
            .first()
        )
        dispatch_status = None
        if latest_job:
            dispatch_status = latest_job.status.value if hasattr(latest_job.status, "value") else str(latest_job.status)

        recent_tours.append(RecentTourItem(
            id=str(tour.id),
            sheet_name=tour.sheet_name or "",
            route=tour.route or "",
            date_start=tour.date_start or "",
            date_end=tour.date_end or "",
            pilgrims_count=int(pilgrims_count or 0),
            dispatch_status=dispatch_status,
            created_at=tour.created_at,
        ))

    recent_jobs_rows = (
        db.query(DispatchJob)
        .order_by(desc(DispatchJob.created_at))
        .limit(5)
        .all()
    )

    recent_jobs: list[RecentJobItem] = []
    for job in recent_jobs_rows:
        tour_sheet_name = ""
        if job.tour:
            tour_sheet_name = job.tour.sheet_name or job.tour.route or ""

        recent_jobs.append(RecentJobItem(
            id=str(job.id),
            tour_sheet_name=tour_sheet_name,
            status=job.status.value if hasattr(job.status, "value") else str(job.status),
            attempt_count=job.attempt_count,
            max_attempts=job.max_attempts,
            error_message=job.error_message,
            created_at=job.created_at,
            sent_at=job.sent_at,
        ))

    return DashboardRecentResponse(
        recent_tours=recent_tours,
        recent_jobs=recent_jobs,
    )
