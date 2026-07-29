from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import httpx

from .config import Settings
from .content import safe_id

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

    async def recall(self, query: str, user_id: str) -> str:
        if not query.strip():
            return ""

        payload = {
            "q": query,
            "containerTag": self._container_tag(user_id),
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
            logger.exception("Supermemory search failed")
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
        user_id: str,
        conversation_id: str,
        request_payload: dict[str, Any],
        assistant_text: str,
    ) -> None:
        content_payload = {
            "conversation_id": conversation_id,
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
            f"{user_id}\n{conversation_id}\n{canonical}".encode()
        ).hexdigest()[:48]
        payload = {
            "content": canonical,
            "containerTag": self._container_tag(user_id),
            "customId": f"sumeme-{digest}",
            "metadata": {
                "source": "sumeme-conversation",
                "conversation_id": safe_id(conversation_id, "unknown")[:100],
                "schema_version": 1,
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
        except httpx.HTTPError:
            logger.exception("Supermemory write failed")

    async def aclose(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": (
                f"Bearer {self.settings.supermemory_api_key.get_secret_value()}"
            ),
            "Content-Type": "application/json",
        }

    def _container_tag(self, user_id: str) -> str:
        prefix = safe_id(self.settings.supermemory_container_prefix, "sumeme")
        account = safe_id(user_id, "default")
        return f"{prefix}:{account}"[:100]

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
