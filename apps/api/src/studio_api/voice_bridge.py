"""Local macOS speech service for the Docker renderer.

Start on the Mac with: PYTHONPATH=apps/api/src uv run --project apps/api
uvicorn studio_api.voice_bridge:app --host 127.0.0.1 --port 7861
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

app = FastAPI(title="AI Story Studio macOS voice bridge")


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


@app.get("/health")
def health() -> dict[str, object]:
    ready = shutil.which("say") is not None and shutil.which("ffmpeg") is not None
    return {"ready": ready, "voice": "Linh", "language": "vi_VN"}


def _synthesize(text: str) -> bytes:
    if not health()["ready"]:
        raise RuntimeError("macOS say or FFmpeg is unavailable")
    with tempfile.TemporaryDirectory(prefix="story-voice-") as folder:
        aiff = Path(folder) / "voice.aiff"
        wav = Path(folder) / "voice.wav"
        subprocess.run(
            ["say", "-v", "Linh", "-r", "180", "-o", str(aiff), text],
            check=True,
            timeout=120,
            capture_output=True,
        )
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(aiff),
                "-ac",
                "1",
                "-ar",
                "24000",
                str(wav),
            ],
            check=True,
            timeout=120,
            capture_output=True,
        )
        return wav.read_bytes()


@app.post("/speak")
async def speak(request: SpeechRequest) -> Response:
    try:
        content = await asyncio.to_thread(_synthesize, request.text)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        raise HTTPException(503, "Local voice synthesis failed") from exc
    return Response(content, media_type="audio/wav")
