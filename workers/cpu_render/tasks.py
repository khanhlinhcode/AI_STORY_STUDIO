from __future__ import annotations

from uuid import UUID

import studio_api.models  # noqa: F401
from studio_api.core.celery_app import celery_app
from studio_api.core.db import run_worker_coroutine
from workers.cpu_render.pipeline import execute_step_async, run_job_async


@celery_app.task(name="studio.run_job", acks_late=True)
def run_job(job_id: str) -> bool:
    return run_worker_coroutine(run_job_async(UUID(job_id)))


@celery_app.task(name="studio.execute_step", acks_late=True)
def execute_step(step_id: str) -> bool:
    return run_worker_coroutine(execute_step_async(UUID(step_id)))
