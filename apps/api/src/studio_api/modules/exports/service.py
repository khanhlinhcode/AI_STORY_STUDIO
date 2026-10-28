from __future__ import annotations

import io
import json
import zipfile
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.errors import ErrorCode, StudioError
from studio_api.modules.assets.models import Asset
from studio_api.modules.assets.service import read_asset, upload_asset
from studio_api.modules.evaluation.models import EvalRun, ReviewTask
from studio_api.modules.exports.models import Export
from studio_api.modules.narrative.models import ScriptRevision
from studio_api.modules.projects.models import Episode
from studio_api.modules.workflows.models import JobStep, ProductionJob

PRESET_ASSETS = {"16:9": ("16x9", "horizontal.mp4"), "9:16": ("9x16", "vertical.mp4")}
MAX_BUNDLE_BYTES = 450 * 1024 * 1024


async def create_export(
    db: AsyncSession, episode: Episode, presets: list[str], approved_by: UUID | None
) -> Export:
    if not presets or len(set(presets)) != len(presets) or any(
        preset not in PRESET_ASSETS for preset in presets
    ):
        raise StudioError(ErrorCode.POLICY_REJECTED, "Select one or more valid export presets")
    job = await db.scalar(
        select(ProductionJob)
        .where(ProductionJob.episode_id == episode.id, ProductionJob.job_kind == "episode")
        .order_by(ProductionJob.created_at.desc())
        .limit(1)
    )
    if job is None or job.status != "completed":
        raise StudioError(ErrorCode.POLICY_REJECTED, "A completed production job is required")
    if job.snapshot_revision != episode.revision:
        raise StudioError(
            ErrorCode.ASSET_STALE, "Episode changed after the production job", status_code=409
        )
    qc = await db.scalar(
        select(EvalRun).where(EvalRun.job_id == job.id).order_by(EvalRun.created_at.desc()).limit(1)
    )
    if qc is None or not qc.passed or qc.report.get("blocking", False):
        raise StudioError(ErrorCode.POLICY_REJECTED, "Export is blocked by quality checks")
    if episode.execution_mode == "studio":
        script = await db.scalar(
            select(ScriptRevision)
            .where(ScriptRevision.episode_id == episode.id)
            .order_by(ScriptRevision.created_at.desc())
            .limit(1)
        )
        review = await db.scalar(
            select(ReviewTask)
            .where(
                ReviewTask.episode_id == episode.id,
                ReviewTask.episode_revision == episode.revision,
            )
            .order_by(ReviewTask.created_at.desc())
            .limit(1)
        )
        if (
            script is None
            or not script.is_approved
            or review is None
            or review.status != "approved"
        ):
            raise StudioError(
                ErrorCode.POLICY_REJECTED, "Studio export requires approved script and review"
            )
    video_step = await db.scalar(
        select(JobStep).where(JobStep.job_id == job.id, JobStep.kind == "video")
    )
    manifest_asset = (
        await db.get(Asset, video_step.output_manifest_id)
        if video_step and video_step.output_manifest_id
        else None
    )
    if manifest_asset is None or manifest_asset.workspace_id != job.workspace_id:
        raise StudioError(ErrorCode.ASSET_STALE, "Rendered manifest is missing")
    manifest = json.loads(await read_asset(manifest_asset))
    if (
        manifest.get("fixture_only")
        or manifest.get("job_id") != str(job.id)
        or manifest.get("episode_revision") != episode.revision
    ):
        raise StudioError(ErrorCode.ASSET_STALE, "Rendered manifest is stale or only a fixture")

    asset_files = {
        PRESET_ASSETS[preset][1]: manifest.get("videos", {}).get(PRESET_ASSETS[preset][0])
        for preset in presets
    }
    asset_files.update(
        {"captions.srt": manifest.get("srt"), "thumbnail.jpg": manifest.get("thumbnail")}
    )
    assets: dict[str, Asset] = {}
    for filename, raw_id in asset_files.items():
        try:
            asset = await db.get(Asset, UUID(str(raw_id)))
        except (ValueError, TypeError):
            asset = None
        if asset is None or asset.workspace_id != job.workspace_id:
            raise StudioError(ErrorCode.ASSET_STALE, f"Missing export asset: {filename}")
        assets[filename] = asset

    export_id = uuid4()
    files = {
        filename: {"asset_id": str(asset.id), "sha256": asset.sha256}
        for filename, asset in assets.items()
    }
    metadata = {
        "export_id": str(export_id),
        "episode_id": str(episode.id),
        "episode_revision": episode.revision,
        "job_id": str(job.id),
        "files": files,
        "validation": qc.report,
        "publish_package": generate_publish_package(episode, export_id),
    }
    bundle = io.BytesIO()
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_STORED) as archive:
        for filename, asset in assets.items():
            if bundle.tell() + asset.size_bytes > MAX_BUNDLE_BYTES:
                raise StudioError(ErrorCode.POLICY_REJECTED, "Export bundle exceeds 450 MB")
            archive.writestr(filename, await read_asset(asset))
        archive.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
    if bundle.tell() > MAX_BUNDLE_BYTES:
        raise StudioError(ErrorCode.POLICY_REJECTED, "Export bundle exceeds 450 MB")
    bundle_asset = await upload_asset(
        db,
        job.workspace_id,
        bundle.getvalue(),
        "application/zip",
        {"kind": "export", "episode_id": str(episode.id), "export_id": str(export_id)},
    )
    export = Export(
        id=export_id,
        episode_id=episode.id,
        episode_revision=episode.revision,
        status="ready",
        manifest={"presets": presets, "assets": files, "bundle_asset_id": str(bundle_asset.id)},
        validation=qc.report,
        approved_by=approved_by,
    )
    db.add(export)
    await db.commit()
    await db.refresh(export)
    return export


def generate_publish_package(episode: Episode, export: Export | UUID) -> dict[str, Any]:
    caption = f"{episode.title} #truyenthieunhi"
    export_id = export.id if isinstance(export, Export) else export
    return {
        "export_id": str(export_id),
        "youtube": {
            "title": episode.title,
            "description": f"{episode.title} — truyện thiếu nhi tiếng Việt.",
            "tags": ["truyện thiếu nhi", "kể chuyện", "tiếng Việt"],
            "made_for_kids": True,
            "category_id": 22,
        },
        "tiktok": {"caption": caption[:150], "hashtags": ["#truyenthieunhi"]},
        "checklist": [
            "Made for Kids verified",
            "No copyrighted music",
            "Character rights declared",
            "Ready to publish manually",
        ],
    }
