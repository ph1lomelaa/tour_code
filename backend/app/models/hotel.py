
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid

from .base import Base


class Hotel(Base):
    __tablename__ = 'hotels'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False, index=True)  # Makkah, Madinah
    country = Column(String(100), nullable=False, default='Saudi Arabia')
    stars = Column(Integer, nullable=True)  # 1-5 звезд
    address = Column(Text, nullable=True)
    distance_to_haram = Column(Integer, nullable=True)  # Метры до Харама

    # Дополнительная информация
    description = Column(Text, nullable=True)
    amenities = Column(JSONB, nullable=True)  # {"wifi": true, "breakfast": true}

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Hotel(id={self.id}, name={self.name}, city={self.city})>"
