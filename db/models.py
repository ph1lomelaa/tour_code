"""
Таблицы:
  users, tours, pilgrims, tour_offers, dispatch_jobs, system_settings
"""
from datetime import datetime
import enum
import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey,
    Integer, JSON, String, Text,
)
from sqlalchemy.orm import relationship

from .base import Base


def _uuid():
    return str(uuid.uuid4())

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    OPERATOR = "operator"


class TourStatus(str, enum.Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    QUEUED = "queued"
    PROCESSING = "processing"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DispatchJobStatus(str, enum.Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"


# ── 1. users ─────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.OPERATOR)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)

    tours = relationship("Tour", back_populates="creator", foreign_keys="Tour.created_by")

    def __repr__(self):
        return f"<User {self.email}>"


# ── 2. tours ─────────────────────────────────────────────

class Tour(Base):
    __tablename__ = "tours"

    id = Column(String(36), primary_key=True, default=_uuid)

    # Google Sheets
    spreadsheet_id = Column(String(255), nullable=True)
    spreadsheet_name = Column(String(255), nullable=True)
    sheet_name = Column(String(255), nullable=True)

    # Даты и продолжительность
    date_start = Column(String(20), nullable=False)          # "17.02.2026"
    date_end = Column(String(20), nullable=False)            # "24.02.2026"
    days = Column(Integer, nullable=False)                    # 7

    # Маршрут / рейс
    route = Column(String(50), nullable=True, index=True)    # "ALA-JED"
    departure_city = Column(String(100), nullable=True)      # "Almaty"
    airlines = Column(String(50), nullable=True)             # "DV"

    # Выбор оператора
    country = Column(String(100), nullable=True)             # "Саудовская Аравия"
    country_en = Column(String(100), nullable=True)          # "Saudi Arabia"
    hotel = Column(String(255), nullable=True)               # "Hilton Makkah..."
    remark = Column(Text, nullable=True)

    # Манифест
    manifest_filename = Column(String(255), nullable=True)

    # Статус
    status = Column(Enum(TourStatus), default=TourStatus.DRAFT, index=True)

    # Кто создал
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # relationships
    creator = relationship("User", back_populates="tours", foreign_keys=[created_by])
    pilgrims = relationship("Pilgrim", back_populates="tour", cascade="all, delete-orphan")
    offers = relationship("TourOffer", back_populates="tour", cascade="all, delete-orphan",
                          order_by="TourOffer.offer_index")
    dispatch_jobs = relationship("DispatchJob", back_populates="tour")

    def __repr__(self):
        return f"<Tour {self.date_start}-{self.date_end} {self.route}>"


# ── 3. pilgrims ──────────────────────────────────────────

class Pilgrim(Base):
    __tablename__ = "pilgrims"

    id = Column(String(36), primary_key=True, default=_uuid)
    tour_id = Column(String(36), ForeignKey("tours.id", ondelete="CASCADE"), nullable=False, index=True)
    surname = Column(String(100), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    document = Column(String(50), nullable=True, index=True)          # c_doc_number
    package_name = Column(String(255), nullable=True, index=True)
    tour_code = Column(String(64), nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    tour = relationship("Tour", back_populates="pilgrims")

    @property
    def full_name(self):
        return f"{self.surname} {self.name}".strip()

    def __repr__(self):
        return f"<Pilgrim {self.surname} {self.name} | {self.document} | {self.tour_code}>"


# ── 4. tour_offers (сегменты перелётов) ──────────────────

class TourOffer(Base):
    __tablename__ = "tour_offers"

    id = Column(String(36), primary_key=True, default=_uuid)
    tour_id = Column(String(36), ForeignKey("tours.id", ondelete="CASCADE"),
                     nullable=False, index=True)

    offer_index = Column(Integer, nullable=False, default=0)           # 0, 1, 2…
    offer_type = Column(String(50), nullable=False, default="flight")  # offertype_N
    date_from = Column(String(20), nullable=True)                      # o_date_from_N
    date_to = Column(String(20), nullable=True)                        # o_date_to_N
    airlines = Column(String(50), nullable=True)                       # o_airlines_N
    airport = Column(String(10), nullable=True)                        # o_airport_N
    country = Column(String(100), nullable=True)                       # o_country_N

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    tour = relationship("Tour", back_populates="offers")

    def __repr__(self):
        return f"<TourOffer #{self.offer_index} {self.airlines} {self.airport}>"


# ── 5. dispatch_jobs (outbox) ────────────────────────────

class DispatchJob(Base):
    __tablename__ = "dispatch_jobs"

    id = Column(String(36), primary_key=True, default=_uuid)
    tour_id = Column(String(36), ForeignKey("tours.id", ondelete="SET NULL"),
                     nullable=True, index=True)

    status = Column(Enum(DispatchJobStatus), nullable=False,
                    default=DispatchJobStatus.DRAFT, index=True)

    payload = Column(JSON, nullable=False)                             # снимок формы
    prepared_payload = Column(JSON, nullable=True)                     # payload для QAMQOR
    response_payload = Column(JSON, nullable=True)                     # ответ API

    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=5)
    next_attempt_at = Column(DateTime, nullable=True, index=True)
    last_attempt_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True, index=True)

    celery_task_id = Column(String(128), nullable=True, index=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tour = relationship("Tour", back_populates="dispatch_jobs")

    def __repr__(self):
        return f"<DispatchJob {self.id} {self.status}>"


# ── 6. system_settings ─────────────────────────────────

class SystemSettings(Base):
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    def __repr__(self):
        return f"<SystemSettings {self.key}>"
