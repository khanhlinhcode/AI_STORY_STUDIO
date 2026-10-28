from __future__ import annotations

import asyncio
import hashlib
import tempfile
from pathlib import Path

import edge_tts
import httpx

from studio_api.core.config import get_settings
from studio_api.core.errors import ErrorCode, StudioError
from studio_api.modules.models.adapters.types import (
    ArtifactManifest,
    CapabilityReport,
    GenerationRequest,
    ResourceEstimate,
)


class EdgeTTSAdapter:
    """Vietnamese preview voice; output rights require separate verification."""

    backend_id = "edge-tts"
    voices = {"vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"}

    def __init__(self) -> None:
        self.settings = get_settings()

    async def probe(self) -> CapabilityReport:
        try:
            available = {
                voice["ShortName"]
                for voice in await edge_tts.list_voices()
                if voice.get("Locale") == "vi-VN"
            }
            selected = sorted(available & self.voices)
            return CapabilityReport(
                backend_id=self.backend_id,
                available=bool(selected),
                task_types=["audio"],
                model_ids=selected,
                supported_formats=["audio/wav"],
                license_flags=["commercial-rights-unverified", "preview-only"],
                unavailable_reason=None if selected else "No Vietnamese Edge voice is available",
            )
        except Exception as exc:
            return CapabilityReport(
                backend_id=self.backend_id,
                available=False,
                task_types=["audio"],
                unavailable_reason=str(exc),
            )

    async def estimate(self, request: GenerationRequest) -> ResourceEstimate:
        return ResourceEstimate(ram_mb=128, disk_mb=16, duration_seconds=20)

    async def generate(self, request: GenerationRequest) -> ArtifactManifest:
        voice = str(request.parameters.get("voice", "vi-VN-HoaiMyNeural"))
        if request.task_type != "audio" or not request.prompt.strip() or voice not in self.voices:
            raise StudioError(ErrorCode.POLICY_REJECTED, "Invalid Edge TTS request")
        with tempfile.TemporaryDirectory(prefix="studio-edge-tts-") as folder:
            mp3 = Path(folder) / "narration.mp3"
            wav = Path(folder) / "narration.wav"
            try:
                await edge_tts.Communicate(
                    request.prompt, voice=voice, rate="-10%", pitch="+5Hz"
                ).save(str(mp3))
                process = await asyncio.create_subprocess_exec(
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(mp3),
                    "-af",
                    "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-ar",
                    "48000",
                    "-ac",
                    "1",
                    str(wav),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await process.communicate()
            except (OSError, edge_tts.exceptions.EdgeTTSException) as exc:
                raise StudioError(ErrorCode.MODEL_UNAVAILABLE, "Edge TTS is unavailable") from exc
            if process.returncode != 0:
                raise StudioError(
                    ErrorCode.MODEL_UNAVAILABLE,
                    f"Edge TTS audio conversion failed: {stderr.decode(errors='replace')[:200]}",
                )
            content = wav.read_bytes()
        if len(content) < 100 or content[:4] != b"RIFF" or content[8:12] != b"WAVE":
            raise StudioError(ErrorCode.MODEL_UNAVAILABLE, "Edge TTS returned invalid WAV")
        digest = hashlib.sha256(content).hexdigest()
        destination = self.settings.local_asset_root / "edge-voice" / f"{digest}.wav"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return ArtifactManifest(
            sha256=digest,
            mime_type="audio/wav",
            size_bytes=len(content),
            storage_key=str(destination),
            lineage={
                "input_hashes": [hashlib.sha256(request.prompt.encode()).hexdigest()],
                "adapter_id": self.backend_id,
                "voice": voice,
                "rights_review_required": True,
            },
        )

    async def cancel(self, operation_id: str) -> bool:
        return False


class VieNeuTTSAdapter:
    backend_id = "vieneu-tts"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.settings = get_settings()
        self.client = client or httpx.AsyncClient(timeout=180)

    async def probe(self) -> CapabilityReport:
        try:
            response = await self.client.get(f"{self.settings.vieneu_base_url}/config")
            response.raise_for_status()
            return CapabilityReport(
                backend_id=self.backend_id,
                available=True,
                task_types=["audio"],
                model_ids=["vieneu-v3-turbo"],
                supported_formats=["audio/wav"],
                license_flags=["verify-voice-rights"],
            )
        except httpx.HTTPError as exc:
            return CapabilityReport(
                backend_id=self.backend_id,
                available=False,
                task_types=["audio"],
                unavailable_reason=str(exc),
            )

    async def estimate(self, request: GenerationRequest) -> ResourceEstimate:
        return ResourceEstimate(ram_mb=2048, disk_mb=16, duration_seconds=20)

    async def generate(self, request: GenerationRequest) -> ArtifactManifest:
        response = await self.client.post(
            f"{self.settings.vieneu_base_url}/api/predict",
            json={
                "data": [
                    request.prompt,
                    request.parameters.get("voice", "vi-VN-HoaiMyNeural"),
                    request.parameters.get("speed", 0.9),
                ]
            },
        )
        response.raise_for_status()
        remote_path = response.json().get("data", [None])[0]
        if not remote_path:
            raise StudioError(ErrorCode.MODEL_UNAVAILABLE, "VieNeu returned no audio")
        download = await self.client.get(str(remote_path))
        download.raise_for_status()
        content = download.content
        digest = hashlib.sha256(content).hexdigest()
        output = self.settings.local_asset_root / "vieneu" / f"{digest}.wav"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)
        return ArtifactManifest(
            sha256=digest,
            mime_type="audio/wav",
            size_bytes=len(content),
            storage_key=str(output),
            lineage={"input_hashes": [], "adapter_id": self.backend_id},
        )

    async def cancel(self, operation_id: str) -> bool:
        return False


class MacOSTTSAdapter:
    backend_id = "macos-say"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.settings = get_settings()
        self.client = client or httpx.AsyncClient(timeout=180)

    async def probe(self) -> CapabilityReport:
        try:
            response = await self.client.get(f"{self.settings.macos_tts_base_url}/health")
            response.raise_for_status()
            ready = response.json().get("ready") is True
            return CapabilityReport(
                backend_id=self.backend_id,
                available=ready,
                task_types=["audio"],
                model_ids=["Apple Linh vi_VN"] if ready else [],
                supported_formats=["audio/wav"],
                unavailable_reason=None if ready else "macOS say or FFmpeg is unavailable",
            )
        except (httpx.HTTPError, ValueError) as exc:
            return CapabilityReport(
                backend_id=self.backend_id,
                available=False,
                task_types=["audio"],
                unavailable_reason=str(exc),
            )

    async def estimate(self, request: GenerationRequest) -> ResourceEstimate:
        return ResourceEstimate(ram_mb=128, disk_mb=2, duration_seconds=10)

    async def generate(self, request: GenerationRequest) -> ArtifactManifest:
        try:
            response = await self.client.post(
                f"{self.settings.macos_tts_base_url}/speak", json={"text": request.prompt}
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise StudioError(
                ErrorCode.MODEL_UNAVAILABLE, "macOS voice bridge is unavailable"
            ) from exc
        content = response.content
        if len(content) < 100 or len(content) > 20_000_000 or content[:4] != b"RIFF":
            raise StudioError(ErrorCode.MODEL_UNAVAILABLE, "macOS voice returned invalid WAV")
        digest = hashlib.sha256(content).hexdigest()
        output = self.settings.local_asset_root / "macos-voice" / f"{digest}.wav"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)
        return ArtifactManifest(
            sha256=digest,
            mime_type="audio/wav",
            size_bytes=len(content),
            storage_key=str(output),
            lineage={
                "input_hashes": [hashlib.sha256(request.prompt.encode()).hexdigest()],
                "adapter_id": self.backend_id,
                "voice": "Apple Linh vi_VN",
            },
        )

    async def cancel(self, operation_id: str) -> bool:
        return False
