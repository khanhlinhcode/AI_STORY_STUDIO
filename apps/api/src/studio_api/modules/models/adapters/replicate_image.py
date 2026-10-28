"""Cloud image generation through Replicate's official model prediction API."""

from __future__ import annotations

import asyncio
import hashlib
import io
from urllib.parse import urlsplit

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError

from studio_api.core.config import get_settings
from studio_api.core.errors import ErrorCode, StudioError
from studio_api.modules.models.adapters.types import (
    ArtifactManifest,
    CapabilityReport,
    GenerationRequest,
    ResourceEstimate,
)

MODEL = "black-forest-labs/flux-schnell"
API_BASE = "https://api.replicate.com/v1"
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024


def _aspect_ratio(width: int, height: int) -> str:
    ratio = width / height
    return min(
        ("1:1", "2:3", "3:2", "9:16", "16:9"),
        key=lambda value: abs(ratio - int(value.split(":")[0]) / int(value.split(":")[1])),
    )


def _replicate_url(value: str, *, delivery: bool = False) -> str:
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    allowed = (
        (host == "replicate.delivery" or host.endswith(".replicate.delivery"))
        if delivery
        else host == "api.replicate.com"
    )
    if parsed.scheme != "https" or not allowed or parsed.username or parsed.password:
        raise StudioError(ErrorCode.MODEL_UNAVAILABLE, "Replicate returned an unsafe URL")
    return value


class ReplicateImageAdapter:
    backend_id = "replicate"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.settings = get_settings()
        self.client = client or httpx.AsyncClient(timeout=60)

    def _headers(self) -> dict[str, str]:
        if not self.settings.replicate_api_token:
            raise StudioError(ErrorCode.MODEL_UNAVAILABLE, "Replicate API token is not configured")
        return {"Authorization": f"Bearer {self.settings.replicate_api_token}"}

    async def probe(self) -> CapabilityReport:
        try:
            response = await self.client.get(f"{API_BASE}/models/{MODEL}", headers=self._headers())
            response.raise_for_status()
            return CapabilityReport(
                backend_id=self.backend_id,
                available=True,
                task_types=["image"],
                model_ids=[MODEL],
                supported_formats=["image/png"],
                max_width=2048,
                max_height=2048,
                hardware={"runtime": "replicate-cloud"},
                license_flags=["verify-provider-terms-before-export"],
            )
        except (httpx.HTTPError, StudioError) as exc:
            return CapabilityReport(
                backend_id=self.backend_id,
                available=False,
                task_types=["image"],
                unavailable_reason=str(exc),
            )

    async def estimate(self, request: GenerationRequest) -> ResourceEstimate:
        return ResourceEstimate(disk_mb=20, duration_seconds=30)

    async def generate(self, request: GenerationRequest) -> ArtifactManifest:
        if request.task_type != "image" or request.width < 64 or request.height < 64:
            raise StudioError(ErrorCode.POLICY_REJECTED, "Invalid image generation request")
        if request.model_id and request.model_id != MODEL:
            raise StudioError(ErrorCode.MODEL_UNAVAILABLE, "Unsupported Replicate model")
        if request.lora_path:
            raise StudioError(ErrorCode.MODEL_UNAVAILABLE, "This model does not support LoRA")
        body = {
            "input": {
                "prompt": request.prompt,
                "aspect_ratio": _aspect_ratio(request.width, request.height),
                "num_outputs": 1,
                "num_inference_steps": 4,
                "output_format": "png",
                "seed": request.seed,
            }
        }
        try:
            submitted = await self.client.post(
                f"{API_BASE}/models/{MODEL}/predictions",
                headers=self._headers(),
                json=body,
            )
            submitted.raise_for_status()
            prediction = submitted.json()
            for _ in range(90):
                status = prediction.get("status")
                if status == "succeeded":
                    break
                if status in {"failed", "canceled"}:
                    raise StudioError(
                        ErrorCode.MODEL_UNAVAILABLE, "Replicate image generation failed"
                    )
                poll_url = prediction.get("urls", {}).get("get")
                if not isinstance(poll_url, str):
                    raise StudioError(
                        ErrorCode.MODEL_UNAVAILABLE, "Replicate omitted prediction URL"
                    )
                await asyncio.sleep(2)
                result = await self.client.get(_replicate_url(poll_url), headers=self._headers())
                result.raise_for_status()
                prediction = result.json()
            else:
                raise StudioError(
                    ErrorCode.MODEL_UNAVAILABLE, "Replicate image generation timed out"
                )
            outputs = prediction.get("output")
            output_url = outputs[0] if isinstance(outputs, list) and outputs else outputs
            if not isinstance(output_url, str):
                raise StudioError(ErrorCode.MODEL_UNAVAILABLE, "Replicate returned no image URL")
            download = await self.client.get(_replicate_url(output_url, delivery=True))
            download.raise_for_status()
            if len(download.content) > MAX_DOWNLOAD_BYTES:
                raise StudioError(ErrorCode.POLICY_REJECTED, "Replicate image exceeds 20 MB")
        except (httpx.HTTPError, ValueError) as exc:
            raise StudioError(ErrorCode.MODEL_UNAVAILABLE, "Replicate API request failed") from exc

        try:
            with Image.open(io.BytesIO(download.content)) as image:
                image.load()
                native_size = image.size
                resized = ImageOps.fit(image.convert("RGB"), (request.width, request.height))
                buffer = io.BytesIO()
                resized.save(buffer, format="PNG")
        except (UnidentifiedImageError, OSError) as exc:
            raise StudioError(
                ErrorCode.MODEL_UNAVAILABLE, "Replicate returned invalid image data"
            ) from exc
        content = buffer.getvalue()
        digest = hashlib.sha256(content).hexdigest()
        path = self.settings.local_asset_root / "replicate" / f"{digest}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return ArtifactManifest(
            sha256=digest,
            mime_type="image/png",
            size_bytes=len(content),
            storage_key=str(path),
            lineage={
                "input_hashes": [hashlib.sha256(request.prompt.encode()).hexdigest()],
                "adapter_id": self.backend_id,
                "model_id": MODEL,
                "model_hash": hashlib.sha256(MODEL.encode()).hexdigest(),
                "seed": request.seed,
                "native_size": list(native_size),
                "requested_size": [request.width, request.height],
                "prediction_id": prediction.get("id"),
                "rights_review_required": True,
            },
        )

    async def cancel(self, operation_id: str) -> bool:
        if not operation_id or not operation_id.replace("-", "").isalnum():
            return False
        try:
            response = await self.client.post(
                f"{API_BASE}/predictions/{operation_id}/cancel", headers=self._headers()
            )
            return response.is_success
        except (httpx.HTTPError, StudioError):
            return False
