from __future__ import annotations

import asyncio
import math
import shutil
import subprocess
import wave
from array import array
from io import BytesIO
from pathlib import Path
from uuid import UUID

import pytest
from httpx import AsyncClient
from PIL import Image, ImageDraw, ImageFilter
from sqlalchemy import select

from studio_api.core.db import SessionFactory
from studio_api.modules.assets.models import Asset
from studio_api.modules.assets.service import upload_asset
from studio_api.modules.evaluation.auto_qc import (
    check_audio_quality,
    check_content_safety,
    check_image_quality,
    check_media_rights,
    run_episode_qc,
)
from studio_api.modules.workflows.models import JobStep, ProductionJob


def test_sharp_image_passes_and_blurred_image_fails(tmp_path: Path) -> None:
    image = Image.new("RGB", (256, 256), "white")
    draw = ImageDraw.Draw(image)
    for y in range(0, 256, 16):
        for x in range(0, 256, 16):
            if (x + y) // 16 % 2:
                draw.rectangle((x, y, x + 15, y + 15), fill="black")
    sharp = tmp_path / "sharp.png"
    blurred = tmp_path / "blurred.png"
    image.save(sharp)
    image.filter(ImageFilter.GaussianBlur(8)).save(blurred)
    assert check_image_quality(sharp).passed
    result = check_image_quality(blurred)
    assert not result.passed
    assert "blurred" in result.reason


def _write_tone(path: Path, *, gap_seconds: int = 0) -> None:
    rate = 48000
    samples = array("h")
    for second in range(3 + gap_seconds):
        for index in range(rate):
            value = (
                0
                if 1 <= second < 1 + gap_seconds
                else round(12000 * math.sin(2 * math.pi * 440 * index / rate))
            )
            samples.append(value)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(samples.tobytes())


def test_long_silence_gap_fails(tmp_path: Path) -> None:
    path = tmp_path / "gap.wav"
    _write_tone(path, gap_seconds=3)
    result = check_audio_quality(path)
    assert not result.passed
    assert "Silence gap" in result.reason


def test_normalized_audio_passes(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("FFmpeg is not installed")
    source = tmp_path / "tone.wav"
    normalized = tmp_path / "normalized.wav"
    _write_tone(source)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-af",
            "loudnorm=I=-14:TP=-1.5:LRA=11",
            str(normalized),
        ],
        check=True,
    )
    result = check_audio_quality(normalized)
    assert result.passed, result.reason
    assert "LUFS" in result.reason


def test_safety_and_rights_require_explicit_clearance() -> None:
    assert not check_content_safety("Con rồng muốn giết tất cả").passed
    assert check_content_safety("Chú thỏ trắng sống trong khu rừng xanh").passed
    asset = Asset(rights_declaration={"source": "original", "commercial_use": True})
    assert check_media_rights(asset).passed
    asset.rights_declaration = {
        "source": "edge-tts",
        "commercial_use": True,
        "lineage": {"rights_review_required": True},
    }
    assert not check_media_rights(asset).passed


@pytest.mark.asyncio
async def test_full_qc_passes_with_six_unique_cleared_assets(
    client: AsyncClient, owner: dict[str, str], tmp_path: Path
) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("FFmpeg is not installed")
    project = await client.post("/api/v1/projects", headers=owner, json={"title": "QC good assets"})
    episode = await client.post(
        f"/api/v1/projects/{project.json()['id']}/episodes",
        headers=owner,
        json={"title": "QC story", "execution_mode": "automation"},
    )
    episode_id = episode.json()["id"]
    script = await client.post(
        f"/api/v1/episodes/{episode_id}/script/generate",
        headers=owner,
        json={"topic": "lá xanh trong rừng"},
    )
    assert script.status_code == 202
    started = await client.post(
        f"/api/v1/episodes/{episode_id}/production/start", headers=owner, json={}
    )
    assert started.status_code == 202
    tone = tmp_path / "tone.wav"
    normalized = tmp_path / "normalized.wav"
    _write_tone(tone)
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(tone),
        "-af",
        "loudnorm=I=-14:TP=-1.5:LRA=11",
        str(normalized),
    )
    assert await process.wait() == 0
    workspace_id = UUID(owner["x-workspace-id"])
    async with SessionFactory() as db:
        job = await db.get_one(ProductionJob, UUID(started.json()["id"]))
        steps = list(await db.scalars(select(JobStep).where(JobStep.job_id == job.id)))
        audio = await upload_asset(
            db,
            workspace_id,
            normalized.read_bytes(),
            "audio/wav",
            {"source": "original", "commercial_use": True},
        )
        for index, step in enumerate(step for step in steps if step.kind == "image"):
            image = Image.new("RGB", (256, 256), "white")
            draw = ImageDraw.Draw(image)
            for y in range(0, 256, 16):
                for x in range(0, 256, 16):
                    if (x + y) // 16 % 2:
                        draw.rectangle((x, y, x + 15, y + 15), fill="black")
            draw.text((index * 12 + 10, 10), str(index), fill="red")
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            asset = await upload_asset(
                db,
                workspace_id,
                buffer.getvalue(),
                "image/png",
                {"source": "original", "commercial_use": True},
            )
            step.output_manifest_id = asset.id
        for step in (step for step in steps if step.kind == "audio"):
            step.output_manifest_id = audio.id
        subtitle = await upload_asset(
            db,
            workspace_id,
            b"1\n00:00:00,000 --> 00:00:03,000\nXin chao\n",
            "text/plain",
            {"source": "original", "commercial_use": True},
        )
        await db.commit()
        report = await run_episode_qc(db, job, {"srt": str(subtitle.id)})
    assert report.passed, report.failed_checks
    assert not report.blocking
    assert len(report.checks) >= 26
