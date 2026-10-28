from __future__ import annotations

import hashlib
import json

from PIL import Image, ImageDraw

from studio_api.core.config import get_settings
from studio_api.modules.models.adapters.types import (
    ArtifactManifest,
    CapabilityReport,
    GenerationRequest,
    ResourceEstimate,
)


class FakeAdapter:
    backend_id = "fake"

    async def probe(self) -> CapabilityReport:
        return CapabilityReport(
            backend_id=self.backend_id,
            available=True,
            task_types=["script", "image", "audio", "video"],
            model_ids=["deterministic-fixture-v1"],
            supported_formats=["application/json", "image/png"],
            max_width=2048,
            max_height=2048,
            license_flags=["test-only"],
        )

    async def estimate(self, request: GenerationRequest) -> ResourceEstimate:
        pixels = request.width * request.height
        return ResourceEstimate(
            ram_mb=64, disk_mb=max(1, pixels // 1_000_000), duration_seconds=0.01
        )

    async def generate(self, request: GenerationRequest) -> ArtifactManifest:
        root = get_settings().local_asset_root / "fake"
        root.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        path = root / f"{key}.png"
        if not path.exists():
            image = Image.new(
                "RGB",
                (request.width, request.height),
                (20 + request.seed % 40, 29 + request.seed % 30, 47 + request.seed % 35),
            )
            draw = ImageDraw.Draw(image)
            draw.rectangle(
                (24, 24, request.width - 24, request.height - 24), outline=(103, 232, 249), width=8
            )
            draw.text((48, 48), request.prompt[:120], fill=(248, 250, 252))
            draw.text((48, 88), f"Fixture seed: {request.seed}", fill=(103, 232, 249))
            image.save(path, format="PNG")
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        return ArtifactManifest(
            sha256=digest,
            mime_type="image/png",
            size_bytes=len(content),
            storage_key=str(path),
            lineage={
                "input_hashes": [hashlib.sha256(request.prompt.encode()).hexdigest()],
                "adapter_id": self.backend_id,
                "model_hash": hashlib.sha256(b"deterministic-fixture-v1").hexdigest(),
                "seed": request.seed,
            },
        )

    async def cancel(self, operation_id: str) -> bool:
        return bool(operation_id)

    async def generate_script(
        self, topic: str, style: str = "storybook", source_context: dict[str, str] | None = None
    ) -> dict[str, object]:
        characters = [
            {"name": "Mimi", "description": "thỏ trắng mặc yếm xanh"},
            {"name": "Tí", "description": "chú sóc nâu hiền lành"},
        ]
        scenes = []
        camera = ["slow_zoom_in", "slow_pan_right", "static", "slow_pan_left"]
        for index in range(6):
            scenes.append(
                {
                    "schema_version": "1.0",
                    "id": f"untrusted-{index + 1}",
                    "image_desc": f"Vietnamese storybook scene {index + 1} about {topic}, {style}",
                    "narration": (
                        f"Cảnh {index + 1}: Mimi và Tí cùng khám phá {topic} bằng lòng tốt."
                    ),
                    "duration_ms": 3000,
                    "camera": camera[index % len(camera)],
                }
            )
        return {
            "schema_version": "1.0",
            "title": f"Mimi và {topic.strip().capitalize()}",
            "lesson": "Biết lắng nghe, chia sẻ và giúp đỡ bạn bè.",
            "characters": characters,
            "scenes": scenes,
        }

    def dump_fixture(self, topic: str) -> str:
        return json.dumps({"topic": topic}, ensure_ascii=False, sort_keys=True)
