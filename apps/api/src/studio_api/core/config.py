from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_name: str = "AI Story Studio"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = Field(default=False, validation_alias="STUDIO_DEBUG")
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000"]

    database_url: str = "sqlite+aiosqlite:///./studio.db"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = Field(default="development-only-secret-change-me-32chars", min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    studio_internal_key: str = "development-internal-key"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "studio-minio"
    minio_secret_key: str = "studio-minio-change-me"
    minio_secure: bool = False
    minio_asset_bucket: str = "studio-assets"
    asset_backend: Literal["local", "minio"] = "local"
    local_asset_root: Path = Path("./local-data/assets")

    ai_adapter_mode: Literal["fake", "native"] = "fake"
    ai_story_mode: Literal["fake", "ollama"] = "fake"
    ai_voice_mode: Literal["fake", "macos", "native"] = "fake"
    ollama_base_url: str = "http://localhost:11434"
    comfyui_base_url: str = "http://localhost:8188"
    vieneu_base_url: str = "http://localhost:7860"
    macos_tts_base_url: str = "http://localhost:7861"
    ollama_model: str = "qwen3:4b"
    active_lora_name: str = ""
    request_timeout_seconds: float = 5.0

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    blocked_keywords_vi: list[str] = ["tự tử", "ma túy", "khiêu dâm", "chặt đầu"]

    @property
    def is_test(self) -> bool:
        return self.environment == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
