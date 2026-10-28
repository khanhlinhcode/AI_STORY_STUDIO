from fastapi import APIRouter, Depends

from studio_api.core.config import get_settings
from studio_api.core.security import get_current_user
from studio_api.modules.models.adapters.registry import get_adapter_registry
from studio_api.modules.models.adapters.types import CapabilityReport

router = APIRouter(tags=["models"])


@router.get("/models/capabilities", response_model=list[CapabilityReport])
async def capabilities(_=Depends(get_current_user)) -> list[CapabilityReport]:
    return await get_adapter_registry().capabilities()


@router.get("/models/runtime")
async def runtime(_=Depends(get_current_user)) -> dict[str, object]:
    settings = get_settings()
    report = await get_adapter_registry().ollama.probe()
    voice_report = (
        await get_adapter_registry().macos_tts.probe()
        if settings.ai_voice_mode == "macos"
        else None
    )
    return {
        "story_backend": settings.ai_story_mode,
        "story_model": settings.ollama_model if settings.ai_story_mode == "ollama" else "fixture",
        "story_ready": settings.ai_story_mode == "fake"
        or (report.available and settings.ollama_model in report.model_ids),
        "media_backend": settings.ai_adapter_mode,
        "image_backend": (
            "NASA source photo / fixture" if settings.ai_adapter_mode == "fake" else "mflux-bridge"
        ),
        "voice_backend": {
            "fake": "fake",
            "macos": "Apple Linh vi_VN",
            "native": "vieneu-tts",
        }[settings.ai_voice_mode],
        "voice_ready": voice_report.available if voice_report is not None else True,
        "lora_name": settings.active_lora_name or None,
        "lora_trained_here": False,
    }
