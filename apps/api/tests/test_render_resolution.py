from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from studio_api.media.audio import fake_narration_wav
from studio_api.modules.models.adapters.ffmpeg import FFmpegAdapter


@pytest.mark.asyncio
@pytest.mark.parametrize("width,height", [(1920, 1080), (1080, 1920)])
async def test_small_source_image_renders_full_hd(tmp_path: Path, width: int, height: int) -> None:
    adapter = FFmpegAdapter()
    if not adapter.available():
        pytest.skip("FFmpeg is not installed")
    image = tmp_path / "source.png"
    caption = tmp_path / "caption.png"
    audio = tmp_path / "narration.wav"
    output = tmp_path / "episode.mp4"
    Image.new("RGB", (32, 32), "navy").save(image)
    Image.new("RGBA", (width, height), (0, 0, 0, 0)).save(caption)
    audio.write_bytes(fake_narration_wav(1000))

    info = await adapter.assemble_episode([(image, audio, caption, 1000)], output, width, height)
    video = next(stream for stream in info["streams"] if stream["codec_type"] == "video")
    assert (video["width"], video["height"]) == (width, height)
    assert video["codec_name"] == "h264"
