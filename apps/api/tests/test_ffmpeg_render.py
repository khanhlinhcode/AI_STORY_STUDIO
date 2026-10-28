from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from studio_api.media.audio import fake_narration_wav
from studio_api.modules.models.adapters.ffmpeg import FFmpegAdapter


@pytest.mark.asyncio
async def test_ffmpeg_assembles_decodable_h264_aac_clip(tmp_path: Path) -> None:
    adapter = FFmpegAdapter()
    if not adapter.available():
        pytest.skip("FFmpeg is not installed on this test host")
    image = tmp_path / "image.png"
    caption = tmp_path / "caption.png"
    audio = tmp_path / "audio.wav"
    output = tmp_path / "render" / "episode.mp4"
    Image.new("RGB", (320, 180), "navy").save(image)
    Image.new("RGBA", (320, 180), (0, 0, 0, 0)).save(caption)
    audio.write_bytes(fake_narration_wav(1000))

    result = await adapter.assemble_episode([(image, audio, caption, 1000)], output, 320, 180)

    assert output.exists()
    assert {stream["codec_name"] for stream in result["streams"]} >= {"h264", "aac"}
    assert abs(float(result["format"]["duration"]) - 1.0) < 0.05
