"""
Модель паломников - центральная таблица с данными о людях
"""
from sqlalchemy import Column, String, Date, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from datetime import datetime
import uuid

from .base import Base


class Pilgrim(Base):
    __tablename__ = 'pilgrims'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    last_name = Column(String(100), nullable=False, index=True)
    first_name = Column(String(100), nullable=False, index=True)
    middle_name = Column(String(100), nullable=True)
    passport_number = Column(String(50), unique=True, nullable=False, index=True)
    date_of_birth = Column(Date, nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    manager = Column(String(100), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    full_name_search = Column(TSVECTOR, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Pilgrim(id={self.id}, name={self.last_name} {self.first_name}, passport={self.passport_number})>"

    @property
    def full_name(self):
       
        parts = [self.last_name, self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        return " ".join(parts)
