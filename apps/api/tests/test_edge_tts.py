from __future__ import annotations

import asyncio
import shutil
import wave
from pathlib import Path

import pytest

from studio_api.modules.models.adapters import tts
from studio_api.modules.models.adapters.types import GenerationRequest


@pytest.mark.asyncio
async def test_edge_tts_converts_to_valid_wav_with_rights_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg is not installed")
    sample_mp3 = tmp_path / "sample.mp3"
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=2",
        str(sample_mp3),
    )
    assert await process.wait() == 0

    class FakeCommunicate:
        def __init__(self, text: str, **kwargs: str) -> None:
            assert text == "Ngày xưa có một chú thỏ trắng nhỏ."
            assert kwargs["voice"] == "vi-VN-HoaiMyNeural"

        async def save(self, path: str) -> None:
            Path(path).write_bytes(sample_mp3.read_bytes())

    monkeypatch.setattr(tts.edge_tts, "Communicate", FakeCommunicate)
    adapter = tts.EdgeTTSAdapter()
    monkeypatch.setattr(adapter.settings, "local_asset_root", tmp_path)
    manifest = await adapter.generate(
        GenerationRequest(task_type="audio", prompt="Ngày xưa có một chú thỏ trắng nhỏ.")
    )
    with wave.open(manifest.storage_key, "rb") as wav:
        assert wav.getnframes() / wav.getframerate() > 1.0
        assert wav.getframerate() == 48000
    assert manifest.lineage["rights_review_required"] is True
    assert manifest.mime_type == "audio/wav"


@pytest.mark.asyncio
async def test_edge_tts_probe_reports_unverified_rights(monkeypatch: pytest.MonkeyPatch) -> None:
    async def voices() -> list[dict[str, str]]:
        return [{"ShortName": "vi-VN-HoaiMyNeural", "Locale": "vi-VN"}]

    monkeypatch.setattr(tts.edge_tts, "list_voices", voices)
    report = await tts.EdgeTTSAdapter().probe()
    assert report.available is True
    assert "commercial-rights-unverified" in report.license_flags
