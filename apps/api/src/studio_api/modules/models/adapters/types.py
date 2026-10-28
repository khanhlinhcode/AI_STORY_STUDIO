from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class CapabilityReport(BaseModel):
    backend_id: str
    available: bool
    task_types: list[str]
    model_ids: list[str] = Field(default_factory=list)
    supported_formats: list[str] = Field(default_factory=list)
    max_width: int | None = None
    max_height: int | None = None
    hardware: dict[str, Any] = Field(default_factory=dict)
    software_versions: dict[str, str] = Field(default_factory=dict)
    license_flags: list[str] = Field(default_factory=list)
    unavailable_reason: str | None = None


class GenerationRequest(BaseModel):
    task_type: str
    prompt: str
    negative_prompt: str = ""
    width: int = 832
    height: int = 1216
    seed: int = 42
    model_id: str | None = None
    lora_path: str | None = None
    input_paths: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)


class ResourceEstimate(BaseModel):
    ram_mb: int = 0
    vram_mb: int = 0
    disk_mb: int = 0
    duration_seconds: float = 0


class ArtifactManifest(BaseModel):
    schema_version: str = "1.0"
    sha256: str
    mime_type: str
    size_bytes: int
    storage_key: str
    duration_ms: int | None = None
    lineage: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class BaseAdapter(Protocol):
    backend_id: str

    async def probe(self) -> CapabilityReport: ...

    async def estimate(self, request: GenerationRequest) -> ResourceEstimate: ...

    async def generate(self, request: GenerationRequest) -> ArtifactManifest: ...

    async def cancel(self, operation_id: str) -> bool: ...
