"""
Модель для журнала всех действий (audit log)
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from datetime import datetime
import uuid

from .base import Base


class AuditLog(Base):
    __tablename__ = 'audit_log'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Кто совершил действие
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    user_email = Column(String(255), nullable=True)

    # Что было сделано
    action = Column(String(100), nullable=False, index=True)  # create_tour, upload_manifest, etc.
    entity_type = Column(String(50), nullable=False, index=True)  # tour, pilgrim, user
    entity_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Данные до и после
    old_data = Column(JSONB, nullable=True)
    new_data = Column(JSONB, nullable=True)

    # Дополнительная информация
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)

    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, entity_type={self.entity_type})>"
