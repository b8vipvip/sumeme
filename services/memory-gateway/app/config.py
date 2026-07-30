from __future__ import annotations

import json
from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_SAFE_IDENTITY_ALGORITHMS = {
    "RS256",
    "RS384",
    "RS512",
    "PS256",
    "PS384",
    "PS512",
    "ES256",
    "ES384",
    "EdDSA",
}
_STORAGE_MODE_ALIASES = {
    "local": "local-only",
    "local_only": "local-only",
    "localonly": "local-only",
    "server": "cloud",
    "remote": "cloud",
    "mixed": "hybrid",
}


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
    openai_embedding_model: str = "text-embedding-3-small"
    relay_timeout_seconds: float = 600
    embedding_timeout_seconds: float = Field(default=120, ge=1, le=1800)

    gateway_api_key: SecretStr
    gateway_admin_token: SecretStr
    gateway_service_token: SecretStr = SecretStr("")
    sumeme_user_id: str = "default"
    memory_provider: str = "mempalace-letta"
    memory_recall_limit: int = Field(default=6, ge=1, le=30)
    memory_context_max_chars: int = Field(default=24000, ge=1000, le=200000)
    store_assistant_verbatim: bool = True

    vault_registry_path: str = "/data/gateway/vaults.sqlite3"
    default_storage_mode: str = "cloud"

    identity_mode: str = "legacy-client-asserted"
    identity_trusted_upstream_issuer: str = "lobehub-internal"
    identity_issuer: str = ""
    identity_audience: str = ""
    identity_jwks_url: str = ""
    identity_jwks_json: SecretStr = SecretStr("")
    identity_allowed_algorithms: str = "RS256,ES256,EdDSA"
    identity_vaults_claim: str = "sumeme_vaults"
    identity_default_vault_claim: str = "sumeme_default_vault"
    identity_clock_skew_seconds: int = Field(default=60, ge=0, le=600)
    identity_max_token_age_seconds: int = Field(default=3600, ge=60, le=604800)
    identity_max_token_chars: int = Field(default=16384, ge=1024, le=65536)
    identity_allow_insecure_jwks_url: bool = False

    mempalace_enabled: bool = True
    mempalace_recall_limit: int = Field(default=6, ge=1, le=30)
    mempalace_qdrant_url: str = "http://qdrant:6333"
    mempalace_qdrant_namespace: str = "sumeme"
    mempalace_remote_db_path: str = "/data/gateway/mempalace-remote.sqlite3"
    mempalace_embedding_max_chars: int = Field(default=12000, ge=256, le=100000)
    mempalace_qdrant_timeout_seconds: float = Field(default=30, ge=1, le=300)

    letta_enabled: bool = True
    letta_required: bool = True
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
    def validate_runtime_modes(self) -> Settings:
        self._validate_memory_provider()
        self._validate_storage()
        self._validate_identity()
        return self

    def _validate_memory_provider(self) -> None:
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

        if normalized == "mempalace-letta" and self.mempalace_enabled:
            if not self.openai_embedding_model.strip():
                raise ValueError(
                    "OPENAI_EMBEDDING_MODEL is required for remote MemPalace embeddings"
                )
            qdrant_url = self.mempalace_qdrant_url.strip().rstrip("/")
            if not qdrant_url.startswith(("http://", "https://")):
                raise ValueError("MEMPALACE_QDRANT_URL must use HTTP or HTTPS")
            self.mempalace_qdrant_url = qdrant_url

            namespace = self.mempalace_qdrant_namespace.strip().lower()
            if not namespace or len(namespace) > 48 or any(
                character not in "abcdefghijklmnopqrstuvwxyz0123456789_-"
                for character in namespace
            ):
                raise ValueError(
                    "MEMPALACE_QDRANT_NAMESPACE must use lowercase letters, digits, _ or -"
                )
            self.mempalace_qdrant_namespace = namespace

            db_path = self.mempalace_remote_db_path.strip()
            if not db_path.startswith("/"):
                raise ValueError("MEMPALACE_REMOTE_DB_PATH must be an absolute path")
            self.mempalace_remote_db_path = db_path

        if self.letta_required and not self.letta_enabled:
            raise ValueError("LETTA_REQUIRED=true requires LETTA_ENABLED=true")

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

    def _validate_storage(self) -> None:
        raw_mode = self.default_storage_mode.strip().lower()
        mode = _STORAGE_MODE_ALIASES.get(raw_mode, raw_mode)
        if mode not in {"local-only", "cloud", "hybrid"}:
            raise ValueError(
                "DEFAULT_STORAGE_MODE must be local-only, cloud, or hybrid"
            )
        self.default_storage_mode = mode

        path = self.vault_registry_path.strip()
        if not path or not path.startswith("/"):
            raise ValueError("VAULT_REGISTRY_PATH must be an absolute path")
        self.vault_registry_path = path

    def _validate_identity(self) -> None:
        aliases = {
            "legacy": "legacy-client-asserted",
            "lobehub": "trusted-openai-user",
            "trusted-user": "trusted-openai-user",
            "optional": "jwt-preferred",
            "preferred": "jwt-preferred",
            "required": "jwt-required",
            "jwt": "jwt-required",
        }
        raw_mode = self.identity_mode.strip().lower()
        mode = aliases.get(raw_mode, raw_mode)
        allowed_modes = {
            "legacy-client-asserted",
            "trusted-openai-user",
            "jwt-preferred",
            "jwt-required",
        }
        if mode not in allowed_modes:
            raise ValueError(
                "IDENTITY_MODE must be legacy-client-asserted, "
                "trusted-openai-user, jwt-preferred, or jwt-required"
            )
        self.identity_mode = mode

        if mode == "legacy-client-asserted":
            return

        if mode == "trusted-openai-user":
            issuer = self.identity_trusted_upstream_issuer.strip()
            if not issuer or len(issuer) > 2048:
                raise ValueError(
                    "IDENTITY_TRUSTED_UPSTREAM_ISSUER must be a non-empty stable identifier"
                )
            self.identity_trusted_upstream_issuer = issuer
            return

        algorithms = self.identity_algorithm_list
        if not algorithms or any(
            algorithm not in _SAFE_IDENTITY_ALGORITHMS for algorithm in algorithms
        ):
            raise ValueError(
                "IDENTITY_ALLOWED_ALGORITHMS contains an unsafe or unsupported "
                "algorithm"
            )

        if not self.identity_issuer.strip():
            raise ValueError("IDENTITY_ISSUER is required for JWT identity modes")
        if not self.identity_audience.strip():
            raise ValueError("IDENTITY_AUDIENCE is required for JWT identity modes")

        jwks_url = self.identity_jwks_url.strip()
        jwks_json = self.identity_jwks_json.get_secret_value().strip()
        if bool(jwks_url) == bool(jwks_json):
            raise ValueError(
                "Configure exactly one of IDENTITY_JWKS_URL or IDENTITY_JWKS_JSON"
            )
        if (
            jwks_url
            and not jwks_url.lower().startswith("https://")
            and not self.identity_allow_insecure_jwks_url
        ):
            raise ValueError(
                "IDENTITY_JWKS_URL must use HTTPS unless explicitly allowed "
                "for local testing"
            )

    @property
    def identity_algorithm_list(self) -> tuple[str, ...]:
        return tuple(
            algorithm.strip()
            for algorithm in self.identity_allowed_algorithms.split(",")
            if algorithm.strip()
        )

    @property
    def relay_chat_url(self) -> str:
        return f"{self.openai_relay_base_url.rstrip('/')}/chat/completions"

    @property
    def relay_models_url(self) -> str:
        return f"{self.openai_relay_base_url.rstrip('/')}/models"

    @property
    def supermemory_documents_url(self) -> str:
        return (
            f"{self.supermemory_base_url.rstrip('/')}"
            f"/{self.supermemory_documents_path.lstrip('/')}"
        )

    @property
    def supermemory_search_url(self) -> str:
        return (
            f"{self.supermemory_base_url.rstrip('/')}"
            f"/{self.supermemory_search_path.lstrip('/')}"
        )

    @property
    def static_jwks(self) -> dict[str, object] | None:
        value = self.identity_jwks_json.get_secret_value().strip()
        return json.loads(value) if value else None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
