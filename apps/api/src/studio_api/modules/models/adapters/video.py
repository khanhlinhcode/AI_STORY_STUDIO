from __future__ import annotations

import shutil

from studio_api.core.errors import ErrorCode, StudioError
from studio_api.modules.models.adapters.types import (
    ArtifactManifest,
    CapabilityReport,
    GenerationRequest,
    ResourceEstimate,
)


class Wan22Adapter:
    backend_id = "wan2.2"

    async def probe(self) -> CapabilityReport:
        available = shutil.which("nvidia-smi") is not None
        return CapabilityReport(
            backend_id=self.backend_id,
            available=False,
            task_types=["video"],
            model_ids=["wan2.2-ti2v-5b"],
            supported_formats=["video/mp4"],
            license_flags=["verify-exact-checkpoint"],
            unavailable_reason=(
                "NVIDIA probe is unavailable; Wan2.2 requires a registered worker "
                "with at least 24 GB VRAM"
                if not available
                else "VRAM verification bridge is not configured"
            ),
        )

    async def estimate(self, request: GenerationRequest) -> ResourceEstimate:
        return ResourceEstimate(ram_mb=16384, vram_mb=24576, disk_mb=4096, duration_seconds=600)

    async def generate(self, request: GenerationRequest) -> ArtifactManifest:
        raise StudioError(
            ErrorCode.INSUFFICIENT_MEMORY,
            "Wan2.2 requires a registered NVIDIA worker with at least 24 GB VRAM",
        )

    async def cancel(self, operation_id: str) -> bool:
        return False
