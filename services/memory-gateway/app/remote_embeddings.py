from __future__ import annotations

import math
import os
from typing import Any

import httpx

from .config import Settings
from .memory_result import MemoryOperationError


class RemoteEmbeddingClient:
    """OpenAI-compatible embedding client with no local-model fallback."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._base_url = os.getenv(
            "EMBEDDING_API_BASE_URL",
            settings.openai_relay_base_url,
        ).strip().rstrip("/")
        configured_key = os.getenv("EMBEDDING_API_KEY", "").strip()
        self._api_key = configured_key or settings.openai_relay_api_key.get_secret_value()
        if not self._base_url.startswith(("http://", "https://")):
            raise ValueError("EMBEDDING_API_BASE_URL must use HTTP or HTTPS")
        if not self._api_key:
            raise ValueError("EMBEDDING_API_KEY is required")
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.embedding_timeout_seconds),
            follow_redirects=True,
        )

    async def embed(
        self,
        texts: list[str],
        *,
        timeout_seconds: float,
    ) -> list[list[float]]:
        if not texts:
            return []
        if not self.settings.openai_embedding_model.strip():
            raise MemoryOperationError("mempalace_embedding_model_missing")

        timeout = min(
            max(float(timeout_seconds), 0.1),
            float(self.settings.embedding_timeout_seconds),
        )
        try:
            response = await self._client.post(
                f"{self._base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.settings.openai_embedding_model,
                    "input": texts,
                },
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            raise MemoryOperationError("mempalace_embedding_timeout") from exc
        except httpx.HTTPError as exc:
            raise MemoryOperationError("mempalace_embedding_unavailable") from exc

        if response.status_code in {401, 403}:
            raise MemoryOperationError("mempalace_embedding_auth_failed")
        if response.status_code == 429:
            raise MemoryOperationError("mempalace_embedding_rate_limited")
        if response.status_code >= 500:
            raise MemoryOperationError("mempalace_embedding_upstream_failed")
        if response.status_code >= 400:
            raise MemoryOperationError("mempalace_embedding_rejected")

        try:
            payload = response.json()
        except ValueError as exc:
            raise MemoryOperationError("mempalace_embedding_invalid_response") from exc

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list) or len(data) != len(texts):
            raise MemoryOperationError("mempalace_embedding_invalid_response")

        ordered: list[list[float] | None] = [None] * len(texts)
        dimension: int | None = None
        for fallback_index, item in enumerate(data):
            if not isinstance(item, dict):
                raise MemoryOperationError("mempalace_embedding_invalid_response")
            raw_index: Any = item.get("index", fallback_index)
            if not isinstance(raw_index, int) or not 0 <= raw_index < len(texts):
                raise MemoryOperationError("mempalace_embedding_invalid_response")
            raw_vector = item.get("embedding")
            if not isinstance(raw_vector, list) or not raw_vector:
                raise MemoryOperationError("mempalace_embedding_invalid_response")
            try:
                vector = [float(value) for value in raw_vector]
            except (TypeError, ValueError) as exc:
                raise MemoryOperationError(
                    "mempalace_embedding_invalid_response"
                ) from exc
            if not all(math.isfinite(value) for value in vector):
                raise MemoryOperationError("mempalace_embedding_invalid_response")
            if dimension is None:
                dimension = len(vector)
            elif len(vector) != dimension:
                raise MemoryOperationError("mempalace_embedding_dimension_mismatch")
            if ordered[raw_index] is not None:
                raise MemoryOperationError("mempalace_embedding_invalid_response")
            ordered[raw_index] = vector

        if any(vector is None for vector in ordered):
            raise MemoryOperationError("mempalace_embedding_invalid_response")
        return [vector for vector in ordered if vector is not None]

    async def aclose(self) -> None:
        await self._client.aclose()
