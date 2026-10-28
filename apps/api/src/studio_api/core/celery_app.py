from __future__ import annotations

from celery import Celery  # type: ignore[import-untyped]
from celery.schedules import crontab  # type: ignore[import-untyped]

from studio_api.core.config import get_settings

settings = get_settings()
celery_app = Celery("studio", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Ho_Chi_Minh",
    beat_schedule={
        "reconcile-expired-leases": {
            "task": "studio.reconcile_expired_leases",
            "schedule": 60.0,
            "options": {"queue": "dispatcher"},
        },
        "dispatch-outbox": {
            "task": "studio.dispatch_outbox",
            "schedule": 5.0,
            "options": {"queue": "dispatcher"},
        },
        "discover-nasa-earth-daily": {
            "task": "studio.discover_daily",
            "schedule": crontab(hour=7, minute=0),
            "options": {"queue": "dispatcher"},
        },
    },
    imports=("workers.dispatcher.tasks", "workers.cpu_render.tasks"),
)
