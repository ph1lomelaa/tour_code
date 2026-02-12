"""
Модель рейсов для паломнических туров
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from .base import Base


class Flight(Base):
    __tablename__ = 'flights'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route = Column(String(50), unique=True, nullable=False, index=True)  # ALA-JED
    departure_city = Column(String(100), nullable=False)  # Almaty
    arrival_city = Column(String(100), nullable=False)  # Jeddah
    airline = Column(String(100), nullable=True)

    # Дополнительная информация
    flight_number = Column(String(20), nullable=True)
    duration_hours = Column(Integer, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Flight(id={self.id}, route={self.route}, airline={self.airline})>"
