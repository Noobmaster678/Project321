"""Celery application configuration for async ML processing."""
from celery import Celery

celery_app = Celery(
    "wildlife_worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "backend.worker.tasks.process_image_task": {"queue": "ml"},
        "backend.worker.tasks.process_batch_task": {"queue": "ml"},
    },
)

celery_app.autodiscover_tasks(["backend.worker"])
