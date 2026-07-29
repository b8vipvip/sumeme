from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from functools import partial
from typing import Any

import anyio

from .config import Settings
from .content import safe_id

logger = logging.getLogger(__name__)


class MemPalaceStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._tools: dict[str, Any] | None = None

    def _load(self) -> dict[str, Any]:
        if self._tools is None:
            from mempalace.mcp_server import TOOLS

            self._tools = TOOLS
        return self._tools

    async def search(self, query: str, user_id: str) -> list[dict[str, Any]]:
        if not self.settings.mempalace_enabled or not query.strip():
            return []
        try:
            handler = self._load()["mempalace_search"]["handler"]
            result = await anyio.to_thread.run_sync(
                partial(
                    handler,
                    query=query,
                    limit=self.settings.mempalace_recall_limit,
                    wing=self._wing(user_id),
                )
            )
            return list((result or {}).get("results") or [])
        except Exception:
            logger.exception("MemPalace search failed")
            return []

    async def add_exchange(
        self,
        *,
        user_id: str,
        conversation_id: str,
        request_payload: dict[str, Any],
        assistant: str,
    ) -> None:
        if not self.settings.mempalace_enabled:
            return
        now = datetime.now(timezone.utc).isoformat()
        source = f"lobe:{safe_id(conversation_id, 'unknown')}"
        items = [
            {
                "wing": self._wing(user_id),
                "room": "conversation",
                "content": json.dumps(
                    {
                        "timestamp": now,
                        "role": "user",
                        "conversation_id": conversation_id,
                        "request": request_payload,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            }
        ]
        if assistant and self.settings.store_assistant_verbatim:
            items.append(
                {
                    "wing": self._wing(user_id),
                    "room": "conversation",
                    "content": json.dumps(
                        {
                            "timestamp": now,
                            "role": "assistant",
                            "conversation_id": conversation_id,
                            "content": assistant,
                        },
                        ensure_ascii=False,
                    ),
                }
            )

        try:
            handler = self._load()["mempalace_checkpoint"]["handler"]
            await anyio.to_thread.run_sync(
                partial(
                    handler,
                    items=items,
                    dedup_threshold=0.995,
                    added_by="sumeme-memory-gateway",
                )
            )
        except Exception:
            logger.exception("MemPalace write failed for %s", source)

    @staticmethod
    def _wing(user_id: str) -> str:
        return f"user_{safe_id(user_id)}"
