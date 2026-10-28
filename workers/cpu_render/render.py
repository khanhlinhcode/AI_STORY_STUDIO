from __future__ import annotations

import io
import json
import shutil
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.config import get_settings
from studio_api.core.errors import ErrorCode, StudioError
from studio_api.media.subtitles import build_srt
from studio_api.modules.assets.models import Asset
from studio_api.modules.assets.service import read_asset, upload_asset
from studio_api.modules.evaluation.auto_qc import validate_srt
from studio_api.modules.models.adapters.ffmpeg import FFmpegAdapter
from studio_api.modules.models.adapters.source_image import nasa_source_card
from studio_api.modules.scenes.models import Scene, SceneRevision
from studio_api.modules.workflows.models import JobStep, ProductionJob
from studio_api.modules.workflows.models import SourceStory


async def render_job_media(db: AsyncSession, job: ProductionJob) -> Asset:
    if shutil.disk_usage(tempfile.gettempdir()).free < 1_000_000_000:
        raise StudioError(
            ErrorCode.INSUFFICIENT_STORAGE, "Less than 1 GB temporary storage"
        )
    steps = list(await db.scalars(select(JobStep).where(JobStep.job_id == job.id)))
    image_steps = {
        step.scene_revision_id: step for step in steps if step.kind == "image"
    }
    audio_steps = {
        step.scene_revision_id: step for step in steps if step.kind == "audio"
    }
    scenes: list[tuple[Scene, SceneRevision, Asset, Asset]] = []
    for revision_id, image_step in image_steps.items():
        audio_step = audio_steps.get(revision_id)
        if (
            not audio_step
            or not image_step.output_manifest_id
            or not audio_step.output_manifest_id
        ):
            raise StudioError(ErrorCode.ASSET_STALE, "Scene media is incomplete")
        revision = await db.get(SceneRevision, revision_id)
        scene = await db.get(Scene, revision.scene_id) if revision else None
        image = await db.get(Asset, image_step.output_manifest_id)
        audio = await db.get(Asset, audio_step.output_manifest_id)
        if scene is None or revision is None or image is None or audio is None:
            raise StudioError(ErrorCode.ASSET_STALE, "Scene media lineage is missing")
        scenes.append((scene, revision, image, audio))
    scenes.sort(key=lambda item: item[0].order_index)
    if not scenes:
        raise StudioError(ErrorCode.POLICY_REJECTED, "No scene media to render")
    srt = build_srt(
        [(revision.narration, scene.duration_ms) for scene, revision, _, _ in scenes]
    )
    if not validate_srt(srt).passed:
        raise StudioError(ErrorCode.POLICY_REJECTED, "Generated SRT is invalid")
    settings = get_settings()
    ffmpeg = FFmpegAdapter()
    with tempfile.TemporaryDirectory(prefix="studio-render-") as folder:
        root = Path(folder)
        srt_path = root / "captions.srt"
        srt_path.write_text(srt, encoding="utf-8")
        inputs: list[tuple[Path, Path, int]] = []
        for index, (scene, _, image, audio) in enumerate(scenes):
            image_path = root / f"image-{index:02}.png"
            audio_path = root / f"audio-{index:02}.wav"
            image_path.write_bytes(await read_asset(image))
            audio_path.write_bytes(await read_asset(audio))
            inputs.append((image_path, audio_path, scene.duration_ms))
        source = await db.scalar(
            select(SourceStory).where(SourceStory.episode_id == job.episode_id).limit(1)
        )
        presets = (
            [("16x9", 640, 360), ("9x16", 360, 640)]
            if settings.ai_adapter_mode == "fake"
            else [("16x9", 1920, 1080), ("9x16", 1080, 1920)]
        )
        videos: dict[str, str] = {}
        for name, width, height in presets:
            output_path = root / name / "episode.mp4"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            source_card: Path | None = None
            if (
                source is not None
                and source.image_url
                and settings.ai_adapter_mode == "fake"
            ):
                source_card = output_path.parent / "source-card.png"
                source_card.write_bytes(
                    nasa_source_card(await read_asset(scenes[0][2]), width, height)
                )
            captioned: list[tuple[Path, Path, Path, int]] = []
            for index, (image_path, audio_path, duration) in enumerate(inputs):
                caption_path = output_path.parent / f"caption-{index:02}.png"
                _make_caption(scenes[index][1].narration, caption_path, width, height)
                captioned.append(
                    (source_card or image_path, audio_path, caption_path, duration)
                )
            await ffmpeg.assemble_episode(captioned, output_path, width, height)
            asset = await upload_asset(
                db,
                job.workspace_id,
                output_path.read_bytes(),
                "video/mp4",
                {"kind": "generated", "job_id": str(job.id), "preset": name},
            )
            videos[name] = str(asset.id)
        subtitle = await upload_asset(
            db,
            job.workspace_id,
            srt.encode(),
            "text/plain",
            {"kind": "generated", "job_id": str(job.id), "format": "srt"},
        )
        with Image.open(inputs[0][0]) as image:
            thumbnail = ImageOps.fit(image.convert("RGB"), (1280, 720))
            buffer = io.BytesIO()
            thumbnail.save(buffer, format="JPEG", quality=90)
        thumb = await upload_asset(
            db,
            job.workspace_id,
            buffer.getvalue(),
            "image/jpeg",
            {"kind": "generated", "job_id": str(job.id), "format": "thumbnail"},
        )
    source = await db.scalar(
        select(SourceStory).where(SourceStory.episode_id == job.episode_id).limit(1)
    )
    fixture_only = any(
        asset.rights_declaration.get("lineage", {}).get("fixture_only", False)
        or asset.rights_declaration.get("lineage", {}).get("adapter_id") == "fake"
        for _, _, image, audio in scenes
        for asset in (image, audio)
    )
    manifest = {
        "schema_version": "1.0",
        "job_id": str(job.id),
        "episode_id": str(job.episode_id),
        "episode_revision": job.snapshot_revision,
        "videos": videos,
        "srt": str(subtitle.id),
        "thumbnail": str(thumb.id),
        "fixture_only": fixture_only,
        "source_url": source.source_url if source is not None else None,
        "source_image_url": source.image_url if source is not None else None,
        "source_scene_revision_ids": [str(revision.id) for _, revision, _, _ in scenes],
    }
    return await upload_asset(
        db,
        job.workspace_id,
        json.dumps(manifest, sort_keys=True).encode(),
        "application/json",
        {"kind": "generated", "job_id": str(job.id), "format": "render_manifest"},
    )


def _make_caption(text: str, destination: Path, width: int, height: int) -> None:
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font_size = max(14, round(width / 36))
    font_paths = [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    font_path = next((path for path in font_paths if Path(path).exists()), None)
    font = (
        ImageFont.truetype(font_path, font_size)
        if font_path
        else ImageFont.load_default()
    )
    max_width = width - 44
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    lines = lines[:7]
    if len(lines) == 7 and len(text.split()) > len(" ".join(lines).split()):
        lines[-1] = lines[-1].rstrip(". ") + "…"
    line_height = font_size + 8
    box_height = len(lines) * line_height + 26
    top = height - box_height - max(18, round(height * 0.045))
    draw.rounded_rectangle(
        (16, top, width - 16, top + box_height), radius=12, fill=(12, 18, 30, 200)
    )
    for index, line in enumerate(lines):
        bounds = draw.textbbox((0, 0), line, font=font)
        x = (width - (bounds[2] - bounds[0])) / 2
        draw.text((x, top + 12 + index * line_height), line, fill="white", font=font)
    overlay.save(destination)
