from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    recall_api_key: str = ""
    recall_api_base_url: str = "https://us-west-2.recall.ai/api/v1"
    recall_webhook_secret: str = ""
    recall_skip_webhook_verify: bool = False

    backend_url: str = "http://127.0.0.1:8001"
    frontend_url: str = "http://127.0.0.1:5175"
    cors_allowed_origins: str = (
        "http://127.0.0.1:5175,http://localhost:5175,"
        "http://127.0.0.1:5176,http://localhost:5176"
    )
    admin_api_key: str = ""

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_realtime_model: str = "gpt-realtime"
    openai_realtime_voice: str = "alloy"
    openai_realtime_vad_threshold: float = 0.4
    openai_realtime_vad_silence_ms: int = 600
    openai_realtime_vad_prefix_padding_ms: int = 450
    openai_realtime_interrupt_response: bool = False
    indexer_llm_model: str = "gpt-4o"

    realtime_provider: Literal["auto", "openai", "gemini"] = "auto"
    gemini_api_key: str = ""
    gemini_live_model: str = "gemini-2.5-flash-native-audio-preview-12-2025"
    gemini_live_voice: str = "Kore"
    indexer_provider: Literal["auto", "openai", "gemini"] = "auto"
    gemini_vision_model: str = "gemini-2.5-flash"

    gcs_bucket: str = ""
    gcs_signed_url_ttl_minutes: int = 30
    gcs_prefix: str = "v2"

    database_url: str = ""
    redis_url: str = ""
    redis_key_prefix: str = "v2"

    max_upload_bytes: int = 52428800
    session_ttl_seconds: int = 86400
    session_cleanup_interval_seconds: int = 60
    presentations_root: str = "./data/presentations"
    indexer_vision_concurrency: int = 3
    soffice_path: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


def effective_realtime_provider(settings: Settings | None = None) -> Literal["openai", "gemini"]:
    s = settings or get_settings()
    if s.realtime_provider == "gemini":
        return "gemini" if s.gemini_api_key else "openai"
    if s.realtime_provider == "openai":
        return "openai"
    return "gemini" if s.gemini_api_key else "openai"


def effective_indexer_provider(settings: Settings | None = None) -> Literal["openai", "gemini"]:
    s = settings or get_settings()
    if s.indexer_provider == "gemini":
        return "gemini" if s.gemini_api_key else "openai"
    if s.indexer_provider == "openai":
        return "openai"
    return "gemini" if s.gemini_api_key else "openai"
