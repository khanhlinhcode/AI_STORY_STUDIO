from __future__ import annotations

import io
from pathlib import Path

import httpx
import pytest
from PIL import Image

from studio_api.core.errors import ErrorCode, StudioError
from studio_api.modules.models.adapters.replicate_image import ReplicateImageAdapter
from studio_api.modules.models.adapters.types import GenerationRequest


@pytest.mark.asyncio
async def test_replicate_probe_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = ReplicateImageAdapter()
    monkeypatch.setattr(adapter.settings, "replicate_api_token", "")
    report = await adapter.probe()
    assert report.available is False
    assert report.backend_id == "replicate"


@pytest.mark.asyncio
async def test_replicate_prediction_downloads_valid_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = io.BytesIO()
    Image.new("RGB", (128, 192), "teal").save(image, format="PNG")
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(
                201,
                json={
                    "id": "prediction-123",
                    "status": "succeeded",
                    "output": ["https://replicate.delivery/example/image.png"],
                },
            )
        return httpx.Response(200, content=image.getvalue(), headers={"content-type": "image/png"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        adapter = ReplicateImageAdapter(client)
        monkeypatch.setattr(adapter.settings, "replicate_api_token", "test-token")
        monkeypatch.setattr(adapter.settings, "local_asset_root", tmp_path)
        manifest = await adapter.generate(
            GenerationRequest(
                task_type="image", prompt="Vietnamese storybook forest", width=832, height=1216
            )
        )
    assert len(requests) == 2
    assert requests[0].url.path.endswith("/models/black-forest-labs/flux-schnell/predictions")
    assert requests[0].headers["authorization"] == "Bearer test-token"
    assert requests[1].url.host == "replicate.delivery"
    with Image.open(manifest.storage_key) as saved:
        assert saved.size == (832, 1216)
    assert manifest.sha256
    assert manifest.lineage["prediction_id"] == "prediction-123"


@pytest.mark.asyncio
async def test_replicate_rejects_untrusted_output_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def respond(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201,
            json={"status": "succeeded", "output": ["https://example.com/image.png"]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        adapter = ReplicateImageAdapter(client)
        monkeypatch.setattr(adapter.settings, "replicate_api_token", "test-token")
        monkeypatch.setattr(adapter.settings, "local_asset_root", tmp_path)
        with pytest.raises(StudioError) as failure:
            await adapter.generate(GenerationRequest(task_type="image", prompt="forest"))
    assert failure.value.code == ErrorCode.MODEL_UNAVAILABLE
