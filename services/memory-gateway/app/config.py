from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
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
    memory_provider: str = "mempalace-letta"
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

    supermemory_base_url: str = ""
    supermemory_api_key: SecretStr = SecretStr("")
    supermemory_documents_path: str = "/v3/documents"
    supermemory_search_path: str = "/v4/search"
    supermemory_container_prefix: str = "sumeme"
    supermemory_search_mode: str = "hybrid"
    supermemory_search_threshold: float = Field(default=0.6, ge=0, le=1)
    supermemory_rerank: bool = False
    supermemory_timeout_seconds: float = 180

    log_level: str = "INFO"

    @model_validator(mode="after")
    def validate_memory_provider(self) -> Settings:
        aliases = {
            "mempalace+letta": "mempalace-letta",
            "mempalace_letta": "mempalace-letta",
            "default": "mempalace-letta",
            "super-memory": "supermemory",
        }
        normalized = self.memory_provider.strip().lower()
        normalized = aliases.get(normalized, normalized)
        if normalized not in {"mempalace-letta", "supermemory"}:
            raise ValueError(
                "MEMORY_PROVIDER must be mempalace-letta or supermemory"
            )
        self.memory_provider = normalized

        if normalized == "supermemory":
            if not self.supermemory_base_url.strip():
                raise ValueError(
                    "SUPERMEMORY_BASE_URL is required when MEMORY_PROVIDER=supermemory"
                )
            if not self.supermemory_api_key.get_secret_value().strip():
                raise ValueError(
                    "SUPERMEMORY_API_KEY is required when MEMORY_PROVIDER=supermemory"
                )

        if self.supermemory_search_mode not in {"hybrid", "memories", "documents"}:
            raise ValueError(
                "SUPERMEMORY_SEARCH_MODE must be hybrid, memories, or documents"
            )
        return self

    @property
    def relay_chat_url(self) -> str:
        return self._join_url(self.openai_relay_base_url, "/chat/completions")

    @property
    def relay_models_url(self) -> str:
        return self._join_url(self.openai_relay_base_url, "/models")

    @property
    def supermemory_documents_url(self) -> str:
        return self._join_url(
            self.supermemory_base_url,
            self.supermemory_documents_path,
        )

    @property
    def supermemory_search_url(self) -> str:
        return self._join_url(
            self.supermemory_base_url,
            self.supermemory_search_path,
        )

    @staticmethod
    def _join_url(base_url: str, path: str) -> str:
        return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
