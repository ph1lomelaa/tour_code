"""
Модель связи туров и паломников (many-to-many)
"""
from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import enum

from .base import Base


class TourPilgrimStatus(str, enum.Enum):
    """Статусы паломника в туре"""
    PENDING = "pending"      # Ожидает
    SUBMITTED = "submitted"  # Отправлен
    CONFIRMED = "confirmed"  # Подтверждён
    REJECTED = "rejected"    # Отклонён


class PilgrimSource(str, enum.Enum):
    """Откуда добавлен паломник"""
    MANIFEST = "manifest"  # Из манифеста
    MANUAL = "manual"      # Вручную
    IMPORT = "import"      # Импорт


class TourPilgrim(Base):
    __tablename__ = 'tour_pilgrims'
    __table_args__ = (
        UniqueConstraint('tour_id', 'pilgrim_id', name='tour_pilgrims_unique'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Связи
    tour_id = Column(UUID(as_uuid=True), ForeignKey('tours.id', ondelete='CASCADE'), nullable=False, index=True)
    pilgrim_id = Column(UUID(as_uuid=True), ForeignKey('pilgrims.id', ondelete='CASCADE'), nullable=False, index=True)

    # Данные на момент добавления в тур
    flight_date = Column(Date, nullable=True)

    # Откуда был добавлен
    added_from = Column(Enum(PilgrimSource), default=PilgrimSource.MANIFEST)

    # Статус в этом туре
    status = Column(Enum(TourPilgrimStatus), default=TourPilgrimStatus.PENDING, index=True)

    # Метаданные
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    added_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)

    def __repr__(self):
        return f"<TourPilgrim(tour_id={self.tour_id}, pilgrim_id={self.pilgrim_id}, status={self.status})>"
