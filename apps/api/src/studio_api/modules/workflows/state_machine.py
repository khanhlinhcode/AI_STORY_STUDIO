from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.errors import ErrorCode, StudioError
from studio_api.modules.workflows.models import AuditEvent, JobStep, ProductionJob


class JobStatus(StrEnum):
    DRAFT = "draft"
    VALIDATED = "validated"
    QUEUED = "queued"
    CLAIMED = "claimed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_RESOURCE = "waiting_resource"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"
    CANCELLED = "cancelled"


JOB_TRANSITIONS = {
    JobStatus.DRAFT: {JobStatus.VALIDATED, JobStatus.CANCELLED},
    JobStatus.VALIDATED: {JobStatus.QUEUED, JobStatus.CANCELLED},
    JobStatus.QUEUED: {JobStatus.CLAIMED, JobStatus.CANCELLED, JobStatus.WAITING_RESOURCE},
    JobStatus.WAITING_RESOURCE: {JobStatus.QUEUED, JobStatus.CANCELLED},
    JobStatus.CLAIMED: {JobStatus.RUNNING, JobStatus.QUEUED, JobStatus.CANCELLED},
    JobStatus.RUNNING: {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED},
    JobStatus.FAILED: {JobStatus.QUEUED, JobStatus.CANCELLED},
    JobStatus.COMPLETED: set(),
    JobStatus.CANCELLED: set(),
}

STEP_TRANSITIONS = {
    StepStatus.PENDING: {StepStatus.RUNNING, StepStatus.CANCELLED},
    StepStatus.RUNNING: {
        StepStatus.COMPLETED,
        StepStatus.FAILED,
        StepStatus.RETRY,
        StepStatus.CANCELLED,
    },
    StepStatus.RETRY: {StepStatus.RUNNING, StepStatus.FAILED, StepStatus.CANCELLED},
    StepStatus.FAILED: {StepStatus.RETRY, StepStatus.CANCELLED},
    StepStatus.COMPLETED: set(),
    StepStatus.CANCELLED: set(),
}


def _hash_state(payload: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


async def transition_job(
    db: AsyncSession,
    job: ProductionJob,
    target: JobStatus,
    *,
    actor_id: UUID | None = None,
) -> None:
    current = JobStatus(job.status)
    if target not in JOB_TRANSITIONS[current]:
        raise StudioError(
            ErrorCode.INVALID_TRANSITION,
            f"Cannot transition job from {current} to {target}",
            status_code=409,
        )
    before = _hash_state({"status": current})
    job.status = target.value
    db.add(
        AuditEvent(
            workspace_id=job.workspace_id,
            actor_id=actor_id,
            action="job.status.changed",
            subject_type="production_job",
            subject_id=job.id,
            before_hash=before,
            after_hash=_hash_state({"status": target}),
            details={"from": current, "to": target},
        )
    )


async def transition_step(db: AsyncSession, step: JobStep, target: StepStatus) -> None:
    current = StepStatus(step.status)
    if target not in STEP_TRANSITIONS[current]:
        raise StudioError(
            ErrorCode.INVALID_TRANSITION,
            f"Cannot transition step from {current} to {target}",
            status_code=409,
        )
    step.status = target.value
    job = await db.get(ProductionJob, step.job_id)
    db.add(
        AuditEvent(
            workspace_id=job.workspace_id if job else None,
            actor_id=None,
            action="job_step.status.changed",
            subject_type="job_step",
            subject_id=step.id,
            details={"from": current, "to": target},
        )
    )
