from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from functools import partial
from typing import Any

import anyio

from .config import Settings
from .content import safe_id
from .memory_scope import MemoryScope, coerce_scope

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

    async def search(
        self,
        query: str,
        scope: MemoryScope | str,
    ) -> list[dict[str, Any]]:
        if not self.settings.mempalace_enabled or not query.strip():
            return []

        resolved = coerce_scope(scope, default_user_id=self.settings.sumeme_user_id)
        wings = [self._wing(resolved)]
        if legacy := self._legacy_wing(resolved):
            wings.append(legacy)

        batches = await asyncio.gather(
            *[self._search_wing(query, wing) for wing in dict.fromkeys(wings)]
        )
        merged: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for batch in batches:
            for item in batch:
                key = (
                    str(item.get("wing") or ""),
                    str(item.get("room") or ""),
                    str(item.get("text") or ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                merged.append(item)

        merged.sort(
            key=lambda item: float(item.get("similarity") or 0),
            reverse=True,
        )
        return merged[: self.settings.mempalace_recall_limit]

    async def _search_wing(self, query: str, wing: str) -> list[dict[str, Any]]:
        try:
            handler = self._load()["mempalace_search"]["handler"]
            result = await anyio.to_thread.run_sync(
                partial(
                    handler,
                    query=query,
                    limit=self.settings.mempalace_recall_limit,
                    wing=wing,
                )
            )
            return list((result or {}).get("results") or [])
        except Exception:
            logger.exception("MemPalace search failed for wing %s", wing)
            return []

    async def add_exchange(
        self,
        *,
        scope: MemoryScope | str,
        conversation_id: str,
        request_payload: dict[str, Any],
        assistant: str,
    ) -> bool:
        if not self.settings.mempalace_enabled:
            return False

        resolved = coerce_scope(scope, default_user_id=self.settings.sumeme_user_id)
        now = datetime.now(timezone.utc).isoformat()
        source = f"lobe:{safe_id(conversation_id, 'unknown')}"
        common = {
            "timestamp": now,
            "conversation_id": conversation_id,
            "account_id": resolved.account_id,
            "vault_id": resolved.vault_id,
            "principal_type": resolved.principal_type,
            "scope_key": resolved.storage_key,
        }
        items = [
            {
                "wing": self._wing(resolved),
                "room": "conversation",
                "content": json.dumps(
                    {
                        **common,
                        "role": "user",
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
                    "wing": self._wing(resolved),
                    "room": "conversation",
                    "content": json.dumps(
                        {
                            **common,
                            "role": "assistant",
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
            return True
        except Exception:
            logger.exception(
                "MemPalace write failed for %s in %s",
                source,
                resolved.display_key,
            )
            return False

    @staticmethod
    def _wing(scope: MemoryScope) -> str:
        return f"scope_{safe_id(scope.storage_key)}"

    @staticmethod
    def _legacy_wing(scope: MemoryScope) -> str | None:
        # Phase 1 stored one wing per user ID. Read it during the transition so
        # existing memories remain available until an explicit migration is run.
        if scope.vault_id != "default" and scope.principal_type != "service":
            return None
        legacy_user = "sumeme_smoke" if scope.principal_type == "service" else scope.account_id
        return f"user_{safe_id(legacy_user)}"
