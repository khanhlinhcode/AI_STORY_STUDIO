from __future__ import annotations

from studio_api.media.subtitles import build_srt
from studio_api.modules.evaluation.auto_qc import validate_srt
from studio_api.modules.models.adapters.image import build_flux_workflow
from studio_api.modules.models.adapters.types import GenerationRequest


def test_lora_is_injected_into_comfyui_workflow() -> None:
    request = GenerationRequest(
        task_type="image", prompt="Mimi in a forest", lora_path="mimi-v1.safetensors"
    )
    workflow = build_flux_workflow(request)
    assert workflow["8"]["class_type"] == "LoraLoader"
    assert workflow["5"]["inputs"]["model"] == ["8", 0]


def test_generated_srt_has_no_overlap() -> None:
    subtitle = build_srt([("Xin chào", 3200), ("Chúng mình cùng đi nhé!", 4100)])
    report = validate_srt(subtitle)
    assert report.passed
    assert not report.blocking
