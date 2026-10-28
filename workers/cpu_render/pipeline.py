from __future__ import annotations

import hashlib
import json
import wave
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.config import get_settings
from studio_api.core.db import SessionFactory
from studio_api.core.errors import ErrorCode, StudioError
from studio_api.core.notifications import send_telegram
from studio_api.media.audio import fake_narration_wav
from studio_api.modules.assets.models import Asset
from studio_api.modules.assets.service import upload_asset
from studio_api.modules.evaluation.models import EvalRun
from studio_api.modules.models.adapters.registry import get_adapter_registry
from studio_api.modules.models.adapters.source_image import fetch_nasa_source_image
from studio_api.modules.models.adapters.types import GenerationRequest
from studio_api.modules.projects.models import Episode
from studio_api.modules.scenes.models import Scene, SceneRevision
from studio_api.modules.workflows.models import JobStep, ProductionJob, SourceStory
from workers.cpu_render.render import render_job_media


async def run_job_async(job_id: UUID) -> bool:
    async with SessionFactory() as db:
        claimed = await db.execute(
            update(ProductionJob)
            .where(ProductionJob.id == job_id, ProductionJob.status == "claimed")
            .values(
                status="running",
                lease_expires_at=datetime.now(UTC) + timedelta(minutes=10),
            )
        )
        await db.commit()
        if claimed.rowcount != 1:
            return False
        steps = list(await db.scalars(select(JobStep).where(JobStep.job_id == job_id)))
        order = {"image": 0, "audio": 1, "video": 2, "export": 3}
        steps.sort(key=lambda item: (order[item.kind], str(item.id)))
    try:
        for step in steps:
            if step.status != "completed":
                if not await execute_step_async(step.id):
                    raise StudioError(
                        ErrorCode.INVALID_TRANSITION, "Step could not be claimed"
                    )
        async with SessionFactory() as db:
            job = await db.get(ProductionJob, job_id)
            if job is None or job.status == "cancelled":
                return False
            remaining = await db.scalar(
                select(JobStep.id)
                .where(JobStep.job_id == job_id, JobStep.status != "completed")
                .limit(1)
            )
            if remaining:
                raise StudioError(
                    ErrorCode.INVALID_TRANSITION, "Job has incomplete steps"
                )
            job.status = "completed"
            job.lease_expires_at = None
            source = await db.scalar(
                select(SourceStory).where(SourceStory.job_id == job.id).limit(1)
            )
            if source is not None:
                source.status = "completed"
                source.error_message = None
            episode = await db.get(Episode, job.episode_id)
            if (
                job.job_kind == "episode"
                and episode is not None
                and episode.revision == job.snapshot_revision
            ):
                episode.status = "completed"
            await db.commit()
        await send_telegram(
            f"✅ Job {job_id} render hoàn tất; cần kiểm tra QC trước khi đăng."
        )
        return True
    except Exception as exc:
        async with SessionFactory() as db:
            job = await db.get(ProductionJob, job_id)
            if job is not None and job.status != "cancelled":
                job.status = "failed"
                job.error_code = (
                    exc.code.value if isinstance(exc, StudioError) else "STEP_FAILED"
                )
                job.error_message = str(exc)[:500]
                job.lease_expires_at = None
                source = await db.scalar(
                    select(SourceStory).where(SourceStory.job_id == job.id).limit(1)
                )
                if source is not None:
                    source.status = "failed"
                    source.error_message = str(exc)[:500]
                await db.commit()
        await send_telegram(f"❌ Job {job_id} thất bại: {str(exc)[:200]}")
        raise


async def execute_step_async(step_id: UUID) -> bool:
    async with SessionFactory() as db:
        step = await db.get(JobStep, step_id)
        if step is None:
            return False
        if step.status == "completed":
            return True
        job = await db.get(ProductionJob, step.job_id)
        if (
            step.status not in {"pending", "retry"}
            or job is None
            or job.status != "running"
        ):
            return False
        step.status = "running"
        step.attempts += 1
        step.lease_expires_at = datetime.now(UTC) + timedelta(minutes=10)
        job.lease_expires_at = step.lease_expires_at
        await db.commit()
        try:
            if step.kind == "image":
                asset = await _generate_image(db, job, step)
                step.output_manifest_id = asset.id
            elif step.kind == "audio":
                asset = await _generate_audio(db, job, step)
                step.output_manifest_id = asset.id
            elif step.kind == "video":
                asset = await render_job_media(db, job)
                step.output_manifest_id = asset.id
            elif step.kind == "export":
                await _evaluate_job(db, job)
            else:
                raise StudioError(
                    ErrorCode.POLICY_REJECTED, f"Unknown step: {step.kind}"
                )
            step.status = "completed"
            step.lease_expires_at = None
            await db.commit()
            return True
        except Exception as exc:
            step.status = "failed"
            step.error_code = (
                exc.code.value if isinstance(exc, StudioError) else "STEP_FAILED"
            )
            step.lease_expires_at = None
            await db.commit()
            raise


async def _scene_revision(
    db: AsyncSession, step: JobStep
) -> tuple[SceneRevision, Scene]:
    revision = await db.get(SceneRevision, step.scene_revision_id)
    if revision is None:
        raise StudioError(ErrorCode.ASSET_STALE, "Scene revision is missing")
    scene = await db.get(Scene, revision.scene_id)
    if scene is None:
        raise StudioError(ErrorCode.ASSET_STALE, "Scene is missing")
    return revision, scene


async def _generate_image(db: AsyncSession, job: ProductionJob, step: JobStep) -> Asset:
    revision, _ = await _scene_revision(db, step)
    source = await db.scalar(
        select(SourceStory).where(SourceStory.episode_id == job.episode_id).limit(1)
    )
    if (
        source is not None
        and source.image_url
        and get_settings().ai_adapter_mode == "fake"
    ):
        previous = await db.scalar(
            select(Asset)
            .join(JobStep, JobStep.output_manifest_id == Asset.id)
            .where(
                JobStep.job_id == job.id,
                JobStep.kind == "image",
                JobStep.status == "completed",
            )
            .limit(1)
        )
        if previous is not None:
            return previous
        content, mime_type = await fetch_nasa_source_image(source.image_url)
        return await upload_asset(
            db,
            job.workspace_id,
            content,
            mime_type,
            {
                "kind": "source_photo_preview",
                "source_url": source.source_url,
                "image_url": source.image_url,
                "credit": "NASA Earth Observatory",
                "rights_review_required": True,
                "lineage": {"adapter_id": "nasa-source-image", "fixture_only": False},
            },
        )
    manifest = (
        await get_adapter_registry()
        .get_image_adapter()
        .generate(
            GenerationRequest(
                task_type="image",
                prompt=revision.prompt,
                seed=revision.seed,
                lora_path=get_settings().active_lora_name or None,
            )
        )
    )
    content = Path(manifest.storage_key).read_bytes()
    if hashlib.sha256(content).hexdigest() != manifest.sha256:
        raise StudioError(ErrorCode.POLICY_REJECTED, "Image manifest hash mismatch")
    return await upload_asset(
        db,
        job.workspace_id,
        content,
        manifest.mime_type,
        {
            "kind": "generated",
            "scene_revision_id": str(revision.id),
            "lineage": manifest.lineage,
        },
    )


async def _generate_audio(db: AsyncSession, job: ProductionJob, step: JobStep) -> Asset:
    revision, scene = await _scene_revision(db, step)
    if get_settings().ai_voice_mode == "fake":
        content = fake_narration_wav(scene.duration_ms)
        lineage = {"adapter_id": "fake", "fixture_only": True}
    else:
        manifest = (
            await get_adapter_registry()
            .get_tts_adapter()
            .generate(GenerationRequest(task_type="audio", prompt=revision.narration))
        )
        content = Path(manifest.storage_key).read_bytes()
        lineage = manifest.lineage
        if get_settings().ai_voice_mode == "macos":
            with wave.open(str(manifest.storage_key), "rb") as wav:
                duration_ms = round(wav.getnframes() / wav.getframerate() * 1000)
            scene.duration_ms = min(60_000, max(3000, duration_ms + 500))
    return await upload_asset(
        db,
        job.workspace_id,
        content,
        "audio/wav",
        {
            "kind": "generated",
            "scene_revision_id": str(revision.id),
            "lineage": lineage,
        },
    )


async def _evaluate_job(db: AsyncSession, job: ProductionJob) -> EvalRun:
    video_step = await db.scalar(
        select(JobStep).where(JobStep.job_id == job.id, JobStep.kind == "video")
    )
    if video_step is None or not video_step.output_manifest_id:
        raise StudioError(ErrorCode.ASSET_STALE, "Rendered video manifest is missing")
    manifest_asset = await db.get(Asset, video_step.output_manifest_id)
    from studio_api.modules.assets.service import read_asset

    manifest = json.loads(await read_asset(manifest_asset))
    episode = await db.get(Episode, job.episode_id)
    reasons = []
    if manifest["fixture_only"]:
        reasons.append("Preview media is not publishable content")
    if episode is None or episode.revision != job.snapshot_revision:
        reasons.append("Episode revision changed during rendering")
    if not manifest["fixture_only"]:
        reasons.append(
            "Image quality, child safety, and voice rights await verified QC"
        )
    report = {
        "blocking": True,
        "blocking_issues": reasons,
        "technical_checks": [
            "h264",
            "aac",
            "duration_drift_under_5_percent",
            "decoded_frame",
            "srt_no_overlap",
        ],
        "manifest_asset_id": str(manifest_asset.id),
    }
    evaluation = EvalRun(
        job_id=job.id,
        model_ref=get_settings().ai_adapter_mode,
        score=0,
        passed=False,
        report=report,
    )
    db.add(evaluation)
    await db.commit()
    await db.refresh(evaluation)
    return evaluation
