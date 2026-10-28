from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageStat, UnidentifiedImageError


@dataclass(slots=True)
class QCReport:
    passed: bool
    failed_checks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    score: int = 100
    blocking: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "failed_checks": self.failed_checks,
            "warnings": self.warnings,
            "score": self.score,
            "blocking": self.blocking,
        }


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
