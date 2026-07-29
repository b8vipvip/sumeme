from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    openai_relay_base_url: str
    openai_relay_api_key: SecretStr
    openai_chat_model: str = ""
    openai_memory_model: str = ""
    relay_timeout_seconds: float = 600

    gateway_api_key: SecretStr
    gateway_admin_token: SecretStr
    sumeme_user_id: str = "default"
    memory_recall_limit: int = Field(default=6, ge=1, le=30)
    memory_context_max_chars: int = Field(default=24000, ge=1000, le=200000)
    store_assistant_verbatim: bool = True

    mempalace_enabled: bool = True
    mempalace_recall_limit: int = Field(default=6, ge=1, le=30)

    letta_enabled: bool = True
    letta_base_url: str = "http://letta:8283"
    letta_server_password: SecretStr = SecretStr("")
    letta_agent_id: str = ""
    letta_agent_name: str = "sumeme-personal-memory"
    letta_model: str = ""
    letta_embedding: str = ""
    letta_timeout_seconds: float = 180

    log_level: str = "INFO"

    @property
    def relay_chat_url(self) -> str:
        return f"{self.openai_relay_base_url.rstrip('/')}/chat/completions"

    @property
    def relay_models_url(self) -> str:
        return f"{self.openai_relay_base_url.rstrip('/')}/models"


@lru_cache
def get_settings() -> Settings:
    return Settings()
