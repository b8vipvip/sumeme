from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import httpx

from .config import Settings
from .content import safe_id
from .memory_result import MemoryWriteResult
from .memory_scope import MemoryScope, coerce_scope

logger = logging.getLogger(__name__)


class SupermemoryProvider:
    """Supermemory-compatible memory provider.

    This adapter intentionally uses only the memory/document API. Chat, embedding,
    extraction, OCR, vision and transcription performed inside a self-hosted fork
    must be configured to call the approved relay or an official vendor API.
    """

    name = "supermemory"

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.supermemory_timeout_seconds),
            follow_redirects=True,
        )

    async def recall(self, query: str, scope: MemoryScope | str) -> str:
        if not query.strip():
            return ""

        resolved = coerce_scope(scope, default_user_id=self.settings.sumeme_user_id)
        payload = {
            "q": query,
            "containerTag": self._container_tag(resolved),
            "searchMode": self.settings.supermemory_search_mode,
            "limit": self.settings.memory_recall_limit,
            "threshold": self.settings.supermemory_search_threshold,
            "rerank": self.settings.supermemory_rerank,
        }
        try:
            response = await self._client.post(
                self.settings.supermemory_search_url,
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError):
            logger.exception(
                "Supermemory search failed for scope %s",
                resolved.display_key,
            )
            return ""

        rendered: list[str] = []
        for item in list(data.get("results") or [])[: self.settings.memory_recall_limit]:
            if not isinstance(item, dict):
                continue
            text = self._result_text(item)
            if not text:
                continue
            rendered.append(
                f"- [score={item.get('similarity', item.get('score'))}] {text}"
            )

        if not rendered:
            return ""
        return "Supermemory 个人记忆候选：\n" + "\n".join(rendered)

    async def remember_exchange(
        self,
        *,
        scope: MemoryScope | str,
        conversation_id: str,
        request_payload: dict[str, Any],
        assistant_text: str,
    ) -> MemoryWriteResult:
        resolved = coerce_scope(scope, default_user_id=self.settings.sumeme_user_id)
        content_payload = {
            "conversation_id": conversation_id,
            "account_id": resolved.account_id,
            "vault_id": resolved.vault_id,
            "principal_type": resolved.principal_type,
            "request": request_payload,
            "assistant": assistant_text,
        }
        canonical = json.dumps(
            content_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        digest = hashlib.sha256(
            f"{resolved.storage_key}\n{conversation_id}\n{canonical}".encode()
        ).hexdigest()[:48]
        payload = {
            "content": canonical,
            "containerTag": self._container_tag(resolved),
            "customId": f"sumeme-{digest}",
            "metadata": {
                "source": "sumeme-conversation",
                "conversation_id": safe_id(conversation_id, "unknown")[:100],
                "account_id": resolved.account_id,
                "vault_id": resolved.vault_id,
                "principal_type": resolved.principal_type,
                "scope_key": resolved.storage_key,
                "schema_version": 2,
            },
            "taskType": "memory",
        }

        try:
            response = await self._client.post(
                self.settings.supermemory_documents_url,
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            return MemoryWriteResult(
                provider=self.name,
                components={"supermemory": True},
            )
        except httpx.HTTPError:
            logger.exception(
                "Supermemory write failed for scope %s",
                resolved.display_key,
            )
            return MemoryWriteResult(
                provider=self.name,
                components={"supermemory": False},
                error_codes=("supermemory_write_rejected",),
            )

    async def aclose(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": (
                f"Bearer {self.settings.supermemory_api_key.get_secret_value()}"
            ),
            "Content-Type": "application/json",
        }

    def _container_tag(self, scope: MemoryScope) -> str:
        prefix = safe_id(self.settings.supermemory_container_prefix, "sumeme")
        return f"{prefix}:{scope.storage_key}"[:100]

    @staticmethod
    def _result_text(item: dict[str, Any]) -> str:
        for key in ("memory", "chunk", "summary"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        chunks = item.get("chunks")
        if isinstance(chunks, list):
            values = []
            for chunk in chunks:
                if not isinstance(chunk, dict):
                    continue
                value = chunk.get("content")
                if isinstance(value, str) and value.strip():
                    values.append(value.strip())
            return "\n".join(values)
        return ""
