from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from db.models import DispatchJob, DispatchJobStatus, Pilgrim, Tour


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardStatsResponse(BaseModel):
    total_tours: int
    total_pilgrims: int
    sent_jobs: int


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

    return DashboardStatsResponse(
        total_tours=int(total_tours),
        total_pilgrims=int(total_pilgrims),
        sent_jobs=int(sent_jobs),
    )
