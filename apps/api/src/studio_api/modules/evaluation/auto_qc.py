from __future__ import annotations

import asyncio
import math
import re
import shutil
import subprocess
import tempfile
import wave
from array import array
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.config import get_settings
from studio_api.modules.assets.models import Asset
from studio_api.modules.assets.service import read_asset
from studio_api.modules.scenes.models import SceneRevision
from studio_api.modules.workflows.models import JobStep, ProductionJob


@dataclass(slots=True)
class CheckResult:
    passed: bool
    reason: str
    score: float = 0


def check_image_quality(path: Path) -> CheckResult:
    """A lightweight edge/detail check; this is not a BRISQUE score."""
    try:
        with Image.open(path) as image:
            grayscale = image.convert("L")
            grayscale.thumbnail((512, 512))
            if grayscale.width < 32 or grayscale.height < 32:
                return CheckResult(False, "Image is too small")
            contrast = ImageStat.Stat(grayscale).var[0]
            edges = grayscale.filter(ImageFilter.FIND_EDGES).crop(
                (8, 8, grayscale.width - 8, grayscale.height - 8)
            )
            detail = ImageStat.Stat(edges).var[0]
    except (OSError, UnidentifiedImageError):
        return CheckResult(False, "Cannot read image")
    if contrast < 5 or detail < 30:
        return CheckResult(False, f"Image is blank or blurred (detail={detail:.1f})", detail)
    return CheckResult(True, f"Image detail={detail:.1f}", detail)


def check_audio_quality(path: Path) -> CheckResult:
    """Check WAV duration, long silence, and measured integrated loudness."""
    try:
        with wave.open(str(path), "rb") as wav:
            rate = wav.getframerate()
            channels = wav.getnchannels()
            duration = wav.getnframes() / rate
            if wav.getsampwidth() != 2 or channels not in {1, 2}:
                return CheckResult(False, "Unsupported WAV sample format")
            samples = array("h", wav.readframes(wav.getnframes()))
    except (OSError, wave.Error, ZeroDivisionError):
        return CheckResult(False, "Cannot read WAV audio")
    if duration < 2 or duration > 120:
        return CheckResult(False, f"Audio duration {duration:.1f}s is outside 2–120s", duration)
    frame_samples = max(channels, round(rate * channels * 0.1))
    max_silence = current_silence = 0
    for offset in range(0, len(samples), frame_samples):
        frame = samples[offset : offset + frame_samples]
        if not frame:
            continue
        rms = math.sqrt(sum(sample * sample for sample in frame) / len(frame)) / 32768
        current_silence = current_silence + 1 if rms < 0.004 else 0
        max_silence = max(max_silence, current_silence)
    if max_silence * 0.1 > 2:
        return CheckResult(False, f"Silence gap {max_silence * 0.1:.1f}s", duration)
    if shutil.which("ffmpeg") is None:
        return CheckResult(False, "FFmpeg loudness measurement is unavailable")
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-af",
            "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    match = re.search(r'"input_i"\s*:\s*"([^"]+)"', result.stderr)
    if result.returncode or match is None:
        return CheckResult(False, "Cannot measure audio loudness")
    loudness = float(match.group(1))
    if not math.isfinite(loudness) or abs(loudness + 14) > 3:
        return CheckResult(False, f"Loudness {loudness:.1f} LUFS is outside -14±3", loudness)
    return CheckResult(True, f"Audio {duration:.1f}s, {loudness:.1f} LUFS", loudness)


def check_content_safety(text: str) -> CheckResult:
    blocked = set(get_settings().blocked_keywords_vi) | {
        "giết",
        "máu",
        "bạo lực",
        "rượu",
        "thuốc lá",
        "cờ bạc",
        "kill",
        "blood",
        "violent",
        "drugs",
        "alcohol",
        "gambling",
    }
    matches = sorted(
        term
        for term in blocked
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.IGNORECASE)
    )
    return CheckResult(
        not matches,
        f"Blocked terms: {', '.join(matches)}" if matches else "Safe text",
        len(matches),
    )


def check_media_rights(asset: Asset) -> CheckResult:
    rights = asset.rights_declaration or {}
    lineage = rights.get("lineage") or {}
    if lineage.get("fixture_only") or lineage.get("adapter_id") == "fake":
        return CheckResult(False, "Fixture media is preview only")
    source = rights.get("source") or rights.get("source_url")
    if not source:
        return CheckResult(False, "Rights source is not declared")
    review_required = rights.get(
        "review_required",
        rights.get("rights_review_required", lineage.get("rights_review_required", False)),
    )
    if review_required and not rights.get("reviewed_at"):
        return CheckResult(False, "Rights review is pending")
    if rights.get("commercial_use") is not True:
        return CheckResult(False, "Commercial use is not confirmed")
    return CheckResult(True, f"Rights verified: {source}", 1)


@dataclass(slots=True)
class QCReport:
    passed: bool
    failed_checks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    score: int = 100
    blocking: bool = False
    checks: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "failed_checks": self.failed_checks,
            "warnings": self.warnings,
            "score": self.score,
            "blocking": self.blocking,
            "checks": self.checks,
        }


async def run_episode_qc(
    db: AsyncSession, job: ProductionJob, manifest: dict[str, Any]
) -> QCReport:
    """Evaluate actual scene media and rights before an episode can be exported."""
    report = QCReport(passed=True)
    steps = list(await db.scalars(select(JobStep).where(JobStep.job_id == job.id)))
    media_steps = [step for step in steps if step.kind in {"image", "audio"}]
    if len(media_steps) != 12:
        report.failed_checks.append("Expected six image and six audio assets")
    narration: list[str] = []
    image_hashes: set[str] = set()
    seen_rights: set[str] = set()
    with tempfile.TemporaryDirectory(prefix="studio-qc-") as folder:
        root = Path(folder)
        for step in media_steps:
            asset = (
                await db.get(Asset, step.output_manifest_id) if step.output_manifest_id else None
            )
            if asset is None:
                report.failed_checks.append(f"{step.kind} step {step.id}: asset is missing")
                continue
            if step.kind == "image":
                image_hashes.add(asset.sha256)
            extension = ".png" if step.kind == "image" else ".wav"
            path = root / f"{step.id}{extension}"
            path.write_bytes(await read_asset(asset))
            result = await asyncio.to_thread(
                check_image_quality if step.kind == "image" else check_audio_quality, path
            )
            report.checks.append(
                {
                    "kind": step.kind,
                    "asset_id": str(asset.id),
                    "passed": result.passed,
                    "reason": result.reason,
                    "score": result.score,
                }
            )
            if not result.passed:
                report.failed_checks.append(f"{step.kind} asset {asset.id}: {result.reason}")
            rights = check_media_rights(asset)
            report.checks.append(
                {
                    "kind": "rights",
                    "asset_id": str(asset.id),
                    "passed": rights.passed,
                    "reason": rights.reason,
                }
            )
            if not rights.passed and str(asset.id) not in seen_rights:
                report.failed_checks.append(f"rights asset {asset.id}: {rights.reason}")
            seen_rights.add(str(asset.id))
            if step.kind == "audio" and step.scene_revision_id:
                revision = await db.get(SceneRevision, step.scene_revision_id)
                if revision is not None:
                    narration.append(revision.narration)
        safety = check_content_safety(" ".join(narration))
        if len(image_hashes) < 6:
            report.failed_checks.append(f"Only {len(image_hashes)} unique images for six scenes")
        report.checks.append({"kind": "safety", "passed": safety.passed, "reason": safety.reason})
        if not safety.passed:
            report.failed_checks.append(f"safety: {safety.reason}")
        subtitle_id = manifest.get("srt")
        try:
            subtitle_uuid = UUID(str(subtitle_id)) if subtitle_id else None
        except ValueError:
            subtitle_uuid = None
        subtitle = await db.get(Asset, subtitle_uuid) if subtitle_uuid else None
        if subtitle is None:
            report.failed_checks.append("Subtitle asset is missing")
        else:
            subtitle_result = validate_srt((await read_asset(subtitle)).decode("utf-8"))
            report.checks.append(
                {
                    "kind": "subtitle",
                    "passed": subtitle_result.passed,
                    "reason": ", ".join(subtitle_result.failed_checks) or "SRT timing valid",
                }
            )
            report.failed_checks.extend(subtitle_result.failed_checks)
    report.passed = not report.failed_checks
    report.blocking = not report.passed
    report.score = max(0, 100 - len(report.failed_checks) * 10)
    return report


def check_image(path: Path, minimum: tuple[int, int] = (832, 1216)) -> QCReport:
    failures: list[str] = []
    warnings: list[str] = []
    try:
        with Image.open(path) as image:
            width, height = image.size
            if width < minimum[0] or height < minimum[1]:
                failures.append("resolution_below_minimum")
            grayscale = image.convert("L")
            if ImageStat.Stat(grayscale).var[0] < 2:
                failures.append("image_monochrome_or_blank")
            if ImageStat.Stat(grayscale).var[0] < 20:
                warnings.append("image_may_be_blurred")
    except (OSError, UnidentifiedImageError):
        failures.append("invalid_image")
    score = max(0, 100 - len(failures) * 35 - len(warnings) * 10)
    return QCReport(not failures, failures, warnings, score, bool(failures))


def validate_srt(text: str) -> QCReport:
    failures: list[str] = []
    previous_end = -1
    for block in [item for item in text.strip().split("\n\n") if item.strip()]:
        lines = block.splitlines()
        if len(lines) < 3 or " --> " not in lines[1]:
            failures.append("invalid_srt_block")
            continue
        start, end = lines[1].split(" --> ", maxsplit=1)
        start_ms = _srt_millis(start)
        end_ms = _srt_millis(end)
        if start_ms < previous_end or end_ms <= start_ms:
            failures.append("srt_overlap_or_invalid_duration")
        previous_end = end_ms
    return QCReport(not failures, failures, [], max(0, 100 - len(failures) * 40), bool(failures))


def _srt_millis(value: str) -> int:
    hours, minutes, rest = value.split(":")
    seconds, millis = rest.split(",")
    return ((int(hours) * 60 + int(minutes)) * 60 + int(seconds)) * 1000 + int(millis)
