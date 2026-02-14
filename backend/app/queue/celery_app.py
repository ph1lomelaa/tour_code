from celery import Celery

from app.core.config import settings


celery_app = Celery(
    "tour_code_dispatch",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.queue.tasks.dispatch"],
)

celery_app.conf.update(
    task_default_queue=settings.DISPATCH_QUEUE_NAME,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
celery_app.autodiscover_tasks(["app.queue"])
