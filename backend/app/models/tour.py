"""
Модель туров (тур-кодов) - основная сущность системы
"""
from sqlalchemy import Column, String, Date, Integer, Text, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import enum

from .base import Base


class TourStatus(str, enum.Enum):
    """Статусы туров"""
    DRAFT = "draft"              # Черновик
    CONFIRMED = "confirmed"      # Подтверждён
    QUEUED = "queued"           # В очереди
    PROCESSING = "processing"    # Отправляется
    SUBMITTED = "submitted"      # Отправлено
    COMPLETED = "completed"      # Завершено
    FAILED = "failed"           # Ошибка
    CANCELLED = "cancelled"      # Отменён


class TourType(str, enum.Enum):
    """Типы туров"""
    AVIA = "авиа"
    BUS = "автобус"
    COMBINED = "комбинированный"


class Tour(Base):
    __tablename__ = 'tours'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Основная информация
    date_short = Column(String(10), nullable=True, index=True)  # "17.02"
    date_start = Column(Date, nullable=False, index=True)
    date_end = Column(Date, nullable=False, index=True)
    days = Column(Integer, nullable=False)  # Автоматически рассчитывается триггером

    # Маршрут и тип
    route = Column(String(50), nullable=True, index=True)  # ALA-JED
    type = Column(Enum(TourType), default=TourType.AVIA)

    # Связи с отелями и рейсами
    hotel_id = Column(UUID(as_uuid=True), ForeignKey('hotels.id', ondelete='SET NULL'), nullable=True)
    flight_id = Column(UUID(as_uuid=True), ForeignKey('flights.id', ondelete='SET NULL'), nullable=True)

    # Статус
    status = Column(Enum(TourStatus), default=TourStatus.DRAFT, index=True)

    # Google Sheets
    google_sheet_name = Column(String(100), nullable=True)
    google_sheet_url = Column(Text, nullable=True)

    # Манифест
    manifest_file_path = Column(Text, nullable=True)
    manifest_original_filename = Column(String(255), nullable=True)

    # Кто создал
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)

    # Метаданные госсайта (для будущей интеграции)
    gov_submission_id = Column(String(100), nullable=True)
    gov_site_response = Column(Text, nullable=True)
    screenshot_path = Column(Text, nullable=True)

    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    confirmed_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Tour(id={self.id}, date={self.date_start}, route={self.route}, status={self.status})>"

    @property
    def date_range_str(self):
        """Строка с диапазоном дат"""
        return f"{self.date_start.strftime('%d.%m.%Y')} - {self.date_end.strftime('%d.%m.%Y')}"
