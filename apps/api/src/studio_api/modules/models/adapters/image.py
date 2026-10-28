from __future__ import annotations

import asyncio
import hashlib
from typing import Any
from uuid import uuid4

import httpx

from studio_api.core.config import get_settings
from studio_api.core.errors import ErrorCode, StudioError
from studio_api.modules.models.adapters.types import (
    ArtifactManifest,
    CapabilityReport,
    GenerationRequest,
    ResourceEstimate,
)


def build_flux_workflow(request: GenerationRequest) -> dict[str, Any]:
    workflow: dict[str, Any] = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": request.model_id or "flux2-klein-4b.safetensors"},
        },
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": request.prompt, "clip": ["1", 1]}},
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": request.negative_prompt, "clip": ["1", 1]},
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": request.width, "height": request.height, "batch_size": 1},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
                "seed": request.seed,
                "steps": 20,
                "cfg": 3.5,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
            },
        },
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {
            "class_type": "SaveImage",
            "inputs": {"images": ["6", 0], "filename_prefix": "studio"},
        },
    }
    if request.lora_path:
        workflow["8"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model": ["1", 0],
                "clip": ["1", 1],
                "lora_name": request.lora_path,
                "strength_model": 0.8,
                "strength_clip": 0.8,
            },
        }
        workflow["5"]["inputs"]["model"] = ["8", 0]
        workflow["2"]["inputs"]["clip"] = ["8", 1]
        workflow["3"]["inputs"]["clip"] = ["8", 1]
    return workflow


class ComfyUIAdapter:
    backend_id = "comfyui"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.settings = get_settings()
        self.client = client or httpx.AsyncClient(timeout=30)

    async def probe(self) -> CapabilityReport:
        try:
            response = await self.client.get(f"{self.settings.comfyui_base_url}/system_stats")
            response.raise_for_status()
            return CapabilityReport(
                backend_id=self.backend_id,
                available=True,
                task_types=["image"],
                model_ids=["flux2-klein-4b"],
                supported_formats=["image/png"],
                max_width=2048,
                max_height=2048,
                hardware=response.json(),
                license_flags=["verify-exact-checkpoint"],
            )
        except (httpx.HTTPError, ValueError) as exc:
            return CapabilityReport(
                backend_id=self.backend_id,
                available=False,
                task_types=["image"],
                unavailable_reason=str(exc),
            )

    async def estimate(self, request: GenerationRequest) -> ResourceEstimate:
        return ResourceEstimate(ram_mb=8192, vram_mb=8192, disk_mb=64, duration_seconds=120)

    async def generate(self, request: GenerationRequest) -> ArtifactManifest:
        client_id = str(uuid4())
        response = await self.client.post(
            f"{self.settings.comfyui_base_url}/prompt",
            json={"prompt": build_flux_workflow(request), "client_id": client_id},
        )
        response.raise_for_status()
        prompt_id = response.json()["prompt_id"]
        history: dict[str, Any] | None = None
        for _ in range(300):
            result = await self.client.get(f"{self.settings.comfyui_base_url}/history/{prompt_id}")
            result.raise_for_status()
            payload = result.json()
            if prompt_id in payload:
                history = payload[prompt_id]
                break
            await asyncio.sleep(1)
        if history is None:
            raise StudioError(ErrorCode.MODEL_UNAVAILABLE, "ComfyUI image generation timed out")
        images = history.get("outputs", {}).get("7", {}).get("images", [])
        if not images:
            raise StudioError(ErrorCode.MODEL_UNAVAILABLE, "ComfyUI returned no image")
        descriptor = images[0]
        download = await self.client.get(
            f"{self.settings.comfyui_base_url}/view", params=descriptor
        )
        download.raise_for_status()
        content = download.content
        digest = hashlib.sha256(content).hexdigest()
        output = self.settings.local_asset_root / "comfyui" / f"{digest}.png"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)
        return ArtifactManifest(
            sha256=digest,
            mime_type="image/png",
            size_bytes=len(content),
            storage_key=str(output),
            lineage={"input_hashes": [], "adapter_id": self.backend_id, "seed": request.seed},
        )

    async def cancel(self, operation_id: str) -> bool:
        response = await self.client.post(f"{self.settings.comfyui_base_url}/interrupt")
        return response.is_success


class MFLUXAdapter(ComfyUIAdapter):
    backend_id = "mflux"

    async def probe(self) -> CapabilityReport:
        report = await super().probe()
        report.backend_id = self.backend_id
        report.hardware["runtime"] = "mlx-native-bridge"
        return report
