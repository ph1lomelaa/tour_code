"""Queue package (Celery app + background tasks)."""

from app.queue.celery_app import celery_app

__all__ = ["celery_app"]
