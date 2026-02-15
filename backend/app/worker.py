from app.queue.celery_app import celery_app
from app.queue.tasks import dispatch

all = [celery_app, dispatch]
