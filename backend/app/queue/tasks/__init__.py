"""Celery tasks registered in queue package."""

from app.queue.tasks.dispatch import process_dispatch_job

__all__ = ["process_dispatch_job"]
