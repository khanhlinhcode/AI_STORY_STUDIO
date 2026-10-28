from __future__ import annotations

from functools import lru_cache

from studio_api.core.config import get_settings
from studio_api.modules.models.adapters.fake import FakeAdapter
from studio_api.modules.models.adapters.image import ComfyUIAdapter, MFLUXAdapter
from studio_api.modules.models.adapters.ollama import OllamaAdapter
from studio_api.modules.models.adapters.replicate_image import ReplicateImageAdapter
from studio_api.modules.models.adapters.tts import EdgeTTSAdapter, MacOSTTSAdapter, VieNeuTTSAdapter
from studio_api.modules.models.adapters.types import BaseAdapter, CapabilityReport
from studio_api.modules.models.adapters.video import Wan22Adapter


class AdapterRegistry:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.fake = FakeAdapter()
        self.ollama = OllamaAdapter()
        self.comfyui = ComfyUIAdapter()
        self.mflux = MFLUXAdapter()
        self.replicate = ReplicateImageAdapter()
        self.tts = VieNeuTTSAdapter()
        self.macos_tts = MacOSTTSAdapter()
        self.edge_tts = EdgeTTSAdapter()
        self.wan = Wan22Adapter()

    def get_story_adapter(self):
        return self.fake if self.settings.ai_story_mode == "fake" else self.ollama

    def get_image_adapter(self) -> BaseAdapter:
        if self.settings.ai_adapter_mode == "replicate":
            return self.replicate
        return self.fake if self.settings.ai_adapter_mode == "fake" else self.mflux

    def get_tts_adapter(self) -> BaseAdapter:
        if self.settings.ai_voice_mode == "edge":
            return self.edge_tts
        if self.settings.ai_voice_mode == "macos":
            return self.macos_tts
        if self.settings.ai_voice_mode == "native":
            return self.tts
        return self.fake

    async def capabilities(self) -> list[CapabilityReport]:
        if self.settings.ai_adapter_mode == "fake":
            return [
                await self.fake.probe(),
                await self.ollama.probe(),
                await self.macos_tts.probe(),
                await self.edge_tts.probe(),
                await self.wan.probe(),
            ]
        return [
            await self.ollama.probe(),
            await self.replicate.probe(),
            await self.comfyui.probe(),
            await self.mflux.probe(),
            await self.tts.probe(),
            await self.macos_tts.probe(),
            await self.edge_tts.probe(),
            await self.wan.probe(),
        ]


@lru_cache
def get_adapter_registry() -> AdapterRegistry:
    return AdapterRegistry()
