
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid

from .base import Base


class ManifestValidation(Base):
    __tablename__ = 'manifest_validations'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Связь с туром
    tour_id = Column(UUID(as_uuid=True), ForeignKey('tours.id', ondelete='CASCADE'), nullable=False, index=True)

    # Статистика парсинга
    total_in_manifest = Column(Integer, nullable=False)
    matched_count = Column(Integer, nullable=False)
    missing_in_db_count = Column(Integer, nullable=False)
    missing_in_manifest_count = Column(Integer, nullable=False)
    errors_count = Column(Integer, default=0)

    # Детальные данные (JSON)
    # missing_in_db: [{last_name, first_name, passport, ...}]
    missing_in_db = Column(JSONB, nullable=True)

    # missing_in_manifest: [{pilgrim_id, last_name, ...}]
    missing_in_manifest = Column(JSONB, nullable=True)

    # errors: [{row, error_message, ...}]
    errors = Column(JSONB, nullable=True)

    # Метаданные
    validated_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<ManifestValidation(id={self.id}, tour_id={self.tour_id}, matched={self.matched_count})>"

    @property
    def validation_summary(self):
        """Краткая сводка валидации"""
        return {
            "total": self.total_in_manifest,
            "matched": self.matched_count,
            "missing_in_db": self.missing_in_db_count,
            "missing_in_manifest": self.missing_in_manifest_count,
            "errors": self.errors_count
        }
