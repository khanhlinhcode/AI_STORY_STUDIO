from __future__ import annotations

import pytest
from httpx import AsyncClient

from studio_api.core.config import get_settings
from studio_api.modules.models.adapters.registry import get_adapter_registry
from studio_api.modules.models.adapters.types import CapabilityReport


@pytest.mark.asyncio
async def test_runtime_reports_selected_edge_and_replicate_modes(
    client: AsyncClient, owner: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_voice_mode", "edge")
    monkeypatch.setattr(settings, "ai_adapter_mode", "replicate")
    registry = get_adapter_registry()

    async def ready_ollama() -> CapabilityReport:
        return CapabilityReport(
            backend_id="ollama",
            available=True,
            task_types=["script"],
            model_ids=[settings.ollama_model],
        )

    async def ready_edge() -> CapabilityReport:
        return CapabilityReport(backend_id="edge-tts", available=True, task_types=["audio"])

    async def unavailable_replicate() -> CapabilityReport:
        return CapabilityReport(backend_id="replicate", available=False, task_types=["image"])

    monkeypatch.setattr(registry.ollama, "probe", ready_ollama)
    monkeypatch.setattr(registry.edge_tts, "probe", ready_edge)
    monkeypatch.setattr(registry.replicate, "probe", unavailable_replicate)
    response = await client.get("/api/v1/models/runtime", headers=owner)
    assert response.status_code == 200
    result = response.json()
    assert result["image_backend"] == "replicate"
    assert result["image_ready"] is False
    assert result["voice_backend"] == "Edge Vietnamese preview"
    assert result["voice_ready"] is True
    assert result["voice_rights_cleared"] is False
