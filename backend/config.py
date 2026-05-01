from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    recall_api_key: str = ""
    recall_api_base_url: str = "https://us-west-2.recall.ai/api/v1"

    backend_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"
    cors_allowed_origins: str = (
        "http://127.0.0.1:5173,http://localhost:5173,"
        "http://127.0.0.1:5174,http://localhost:5174"
    )
    admin_api_key: str = ""

    customer_api_key: str = ""  # API key for customer-facing endpoints

    recall_webhook_secret: str = ""
    recall_skip_webhook_verify: bool = False

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_realtime_model: str = "gpt-4o-realtime-preview-2024-12-17"
    openai_realtime_voice: str = "alloy"
    openai_realtime_vad_threshold: float = 0.7
    openai_realtime_vad_silence_ms: int = 700
    openai_realtime_vad_prefix_padding_ms: int = 300
    openai_realtime_interrupt_response: bool = True
    voice_agent_mode: Literal["realtime", "webhook"] = "realtime"
    azure_search_endpoint: str = ""
    azure_search_key: str = ""
    azure_search_index_name: str = "overtone"
    azure_blob_account_url: str = ""
    azure_blob_account_key: str = ""
    azure_blob_container_name: str = "presentations"

    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""

    session_ttl_seconds: int = 86400
    session_cleanup_interval_seconds: int = 60
    webhook_dedupe_ttl_seconds: int = 3600
    max_upload_bytes: int = 52428800
    agents_db_path: str = "./data/agents.db"
    redis_url: str = ""
    redis_key_prefix: str = "voicenav"
    storage_backend: Literal["local", "dynamodb"] = "local"

    database_url: str = ""  # PostgreSQL URL for production, empty for SQLite local dev

    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    aws_dynamodb_presentations_table: str = "voicenav-presentations-meta"

    azure_blob_upload_sas_ttl_minutes: int = 30

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-5"
    indexer_llm_model: str = ""  # overrides anthropic_model for vision extraction if set

    pdftoppm_path: str = ""  # path to pdftoppm binary for PDF to image conversion


@lru_cache
def get_settings() -> Settings:
    return Settings()
