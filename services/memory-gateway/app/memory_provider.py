from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from typing import Any, Protocol

from .config import Settings
from .content import flatten_content, latest_user_message
from .letta_memory import LettaMemory
from .memory_deadlines import MemoryDeadlines
from .memory_result import MemoryOperationError, MemoryWriteResult
from .memory_scope import MemoryScope
from .mempalace_store import MemPalaceStore

logger = logging.getLogger(__name__)


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
        self.deadlines = MemoryDeadlines.from_environment()
        self.mempalace = MemPalaceStore(settings)
        self.letta = LettaMemory(settings)

    async def recall(self, query: str, scope: MemoryScope) -> str:
        raw_results, structured = await asyncio.gather(
            self._recall_component(
                "mempalace",
                self.mempalace.search(query, scope),
                [],
            ),
            self._recall_component(
                "letta",
                self.letta.recall(query, scope),
                "",
            ),
        )

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
            self._write_component(
                "mempalace",
                self.mempalace.add_exchange(
                    scope=scope,
                    conversation_id=conversation_id,
                    request_payload=request_payload,
                    assistant=assistant_text,
                ),
            ),
            self._write_component(
                "letta",
                self.letta.remember(
                    scope=scope,
                    user_text=user_text,
                    assistant_text=assistant_text,
                    conversation_id=conversation_id,
                ),
            ),
        )

        components: dict[str, bool] = {}
        error_codes: list[str] = []
        for name, accepted, error_code in outcomes:
            components[name] = accepted
            if error_code:
                error_codes.append(error_code)

        return MemoryWriteResult(
            provider=self.name,
            components=components,
            error_codes=tuple(error_codes),
        )

    async def _recall_component(
        self,
        name: str,
        operation: Awaitable[Any],
        default: Any,
    ) -> Any:
        try:
            return await asyncio.wait_for(
                operation,
                timeout=self.deadlines.recall_seconds,
            )
        except TimeoutError:
            logger.warning(
                "Memory recall timed out component=%s timeout_seconds=%s",
                name,
                self.deadlines.recall_seconds,
            )
            return default
        except MemoryOperationError as exc:
            logger.warning(
                "Memory recall unavailable component=%s code=%s",
                name,
                exc.code,
            )
            return default
        except Exception:
            logger.exception("Memory recall failed component=%s", name)
            return default

    async def _write_component(
        self,
        name: str,
        operation: Awaitable[bool],
    ) -> tuple[str, bool, str | None]:
        try:
            accepted = await asyncio.wait_for(
                operation,
                timeout=self.deadlines.write_seconds,
            )
        except TimeoutError:
            logger.warning(
                "Memory write timed out component=%s timeout_seconds=%s",
                name,
                self.deadlines.write_seconds,
            )
            return name, False, f"{name}_write_timeout"
        except MemoryOperationError as exc:
            logger.warning(
                "Memory write unavailable component=%s code=%s",
                name,
                exc.code,
            )
            return name, False, exc.code
        except Exception:
            logger.exception("Memory write failed component=%s", name)
            return name, False, f"{name}_write_exception"

        if accepted is True:
            return name, True, None
        return name, False, f"{name}_write_rejected"

    async def aclose(self) -> None:
        await self.mempalace.aclose()
