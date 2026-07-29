from __future__ import annotations

import asyncio
from typing import Any, Protocol

from .config import Settings
from .content import flatten_content, latest_user_message
from .letta_memory import LettaMemory
from .memory_result import MemoryWriteResult
from .memory_scope import MemoryScope
from .mempalace_store import MemPalaceStore


class MemoryProvider(Protocol):
    name: str

    async def recall(self, query: str, scope: MemoryScope) -> str: ...

    async def remember_exchange(
        self,
        *,
        scope: MemoryScope,
        conversation_id: str,
        request_payload: dict[str, Any],
        assistant_text: str,
    ) -> MemoryWriteResult: ...

    async def aclose(self) -> None: ...


class MemPalaceLettaProvider:
    name = "mempalace-letta"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.mempalace = MemPalaceStore(settings)
        self.letta = LettaMemory(settings)

    async def recall(self, query: str, scope: MemoryScope) -> str:
        raw_task = asyncio.create_task(self.mempalace.search(query, scope))
        structured_task = asyncio.create_task(self.letta.recall(query, scope))
        raw_results, structured = await asyncio.gather(raw_task, structured_task)

        sections: list[str] = []
        if raw_results:
            rendered = []
            for item in raw_results[: self.settings.memory_recall_limit]:
                text = str(item.get("text") or "")
                similarity = item.get("similarity")
                rendered.append(
                    f"- [{item.get('wing')}/{item.get('room')} score={similarity}] {text}"
                )
            sections.append("MemPalace 原始历史片段：\n" + "\n".join(rendered))
        if structured:
            sections.append("Letta 结构化个人记忆：\n" + structured)

        return "\n\n".join(sections)

    async def remember_exchange(
        self,
        *,
        scope: MemoryScope,
        conversation_id: str,
        request_payload: dict[str, Any],
        assistant_text: str,
    ) -> MemoryWriteResult:
        message = latest_user_message(request_payload.get("messages") or [])
        user_text = flatten_content((message or {}).get("content"))
        outcomes = await asyncio.gather(
            self.mempalace.add_exchange(
                scope=scope,
                conversation_id=conversation_id,
                request_payload=request_payload,
                assistant=assistant_text,
            ),
            self.letta.remember(
                scope=scope,
                user_text=user_text,
                assistant_text=assistant_text,
                conversation_id=conversation_id,
            ),
            return_exceptions=True,
        )

        names = ("mempalace", "letta")
        components: dict[str, bool] = {}
        error_codes: list[str] = []
        for name, outcome in zip(names, outcomes, strict=True):
            accepted = outcome is True
            components[name] = accepted
            if isinstance(outcome, BaseException):
                error_codes.append(f"{name}_write_exception")
            elif not accepted:
                error_codes.append(f"{name}_write_rejected")

        return MemoryWriteResult(
            provider=self.name,
            components=components,
            error_codes=tuple(error_codes),
        )

    async def aclose(self) -> None:
        return None
