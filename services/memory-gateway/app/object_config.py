from __future__ import annotations

import re
from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BUCKET = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")


class ObjectAccessSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    object_api_enabled: bool = False
    object_registry_path: str = "/data/gateway/objects.sqlite3"
    object_max_size_bytes: int = Field(
        default=2 * 1024**3,
        ge=1,
        le=50 * 1024**3,
    )
    object_presign_ttl_seconds: int = Field(default=600, ge=60, le=3600)
    object_allow_insecure_public_endpoint: bool = False

    rustfs_internal_endpoint: str = "http://rustfs:9000"
    rustfs_public_endpoint: str = ""
    rustfs_access_key: SecretStr = SecretStr("")
    rustfs_secret_key: SecretStr = SecretStr("")
    rustfs_private_bucket: str = "sumeme-vaults"
    rustfs_region: str = "us-east-1"

    @model_validator(mode="after")
    def validate_object_access(self) -> ObjectAccessSettings:
        path = self.object_registry_path.strip()
        if not path.startswith("/"):
            raise ValueError("OBJECT_REGISTRY_PATH must be an absolute path")
        self.object_registry_path = path

        bucket = self.rustfs_private_bucket.strip().lower()
        if not _BUCKET.fullmatch(bucket) or ".." in bucket:
            raise ValueError("RUSTFS_PRIVATE_BUCKET is not a valid S3 bucket name")
        self.rustfs_private_bucket = bucket

        self.rustfs_internal_endpoint = self._endpoint(
            self.rustfs_internal_endpoint,
            "RUSTFS_INTERNAL_ENDPOINT",
        )
        public_endpoint = self.rustfs_public_endpoint.strip()
        if self.object_api_enabled and not public_endpoint:
            raise ValueError(
                "RUSTFS_PUBLIC_ENDPOINT is required when OBJECT_API_ENABLED=true"
            )
        if public_endpoint:
            public_endpoint = self._endpoint(
                public_endpoint,
                "RUSTFS_PUBLIC_ENDPOINT",
            )
            if (
                not public_endpoint.lower().startswith("https://")
                and not self.object_allow_insecure_public_endpoint
            ):
                raise ValueError(
                    "RUSTFS_PUBLIC_ENDPOINT must use HTTPS unless explicitly allowed"
                )
        self.rustfs_public_endpoint = public_endpoint

        if self.object_api_enabled:
            if not self.rustfs_access_key.get_secret_value().strip():
                raise ValueError(
                    "RUSTFS_ACCESS_KEY is required when OBJECT_API_ENABLED=true"
                )
            if not self.rustfs_secret_key.get_secret_value().strip():
                raise ValueError(
                    "RUSTFS_SECRET_KEY is required when OBJECT_API_ENABLED=true"
                )
        return self

    @staticmethod
    def _endpoint(value: str, name: str) -> str:
        endpoint = value.strip().rstrip("/")
        if not endpoint.startswith(("http://", "https://")):
            raise ValueError(f"{name} must use HTTP or HTTPS")
        return endpoint


@lru_cache
def get_object_settings() -> ObjectAccessSettings:
    return ObjectAccessSettings()
