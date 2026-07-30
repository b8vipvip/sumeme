from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import anyio

from .config import Settings
from .content import flatten_content, safe_id
from .memory_deadlines import MemoryDeadlines
from .memory_result import MemoryOperationError
from .memory_scope import MemoryScope, coerce_scope

logger = logging.getLogger(__name__)

_MODEL_PLACEHOLDERS = {
    "",
    "replace_me",
    "+replace_me",
    "openai/replace_me",
    "openai-proxy/replace_me",
}


class LettaMemory:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.deadlines = MemoryDeadlines.from_environment()
        self._client: Any | None = None
        self._agent_ids: dict[str, str] = {}
        self._state_loaded = False
        self._agent_lock = anyio.Lock()
        self._state_file = Path("/data/gateway/letta-agent.json")

    def _get_client(self) -> Any:
        if self._client is None:
            from letta_client import Letta

            kwargs: dict[str, Any] = {"base_url": self.settings.letta_base_url}
            password = self.settings.letta_server_password.get_secret_value()
            if password:
                kwargs["api_key"] = password
            self._client = Letta(**kwargs)
        return self._client

    def _scope(self, value: MemoryScope | str) -> MemoryScope:
        return coerce_scope(value, default_user_id=self.settings.sumeme_user_id)

    def _scope_key(self, value: MemoryScope | str) -> str:
        return self._scope(value).storage_key

    def _request_timeout(self, operation_timeout: float | None) -> float:
        configured = max(float(self.settings.letta_timeout_seconds), 0.1)
        if operation_timeout is None:
            return configured
        return min(configured, max(float(operation_timeout), 0.1))

    def _resolved_model_handle(self) -> str:
        configured = self.settings.letta_model.strip()
        if configured.lower() not in _MODEL_PLACEHOLDERS:
            return configured

        fallback = self._first_remote_model(
            self.settings.openai_memory_model,
            self.settings.openai_chat_model,
        )
        if not fallback:
            raise MemoryOperationError("letta_model_unavailable")
        return f"openai-proxy/{fallback}"

    def _resolved_embedding_handle(self) -> str:
        configured = self.settings.letta_embedding.strip()
        if configured.lower() not in _MODEL_PLACEHOLDERS:
            return configured
        model = self.settings.openai_embedding_model.strip()
        if model.lower() in _MODEL_PLACEHOLDERS:
            raise MemoryOperationError("letta_embedding_unavailable")
        basename = model.split("/", 1)[-1]
        return f"openai/{basename}"

    @staticmethod
    def _first_remote_model(*values: str) -> str:
        for value in values:
            candidate = value.strip()
            if candidate.lower() in _MODEL_PLACEHOLDERS:
                continue
            if "/" in candidate:
                candidate = candidate.split("/", 1)[1]
            if candidate:
                return candidate
        return ""

    def _load_state(self) -> None:
        if self._state_loaded:
            return
        self._state_loaded = True

        default_scope = MemoryScope.account(self.settings.sumeme_user_id)
        explicit = self.settings.letta_agent_id.strip()
        if explicit:
            self._agent_ids[default_scope.storage_key] = explicit

        if not self._state_file.exists():
            return
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8"))
            agents = data.get("agents")
            if isinstance(agents, dict):
                for raw_scope, raw_agent in agents.items():
                    raw_key = str(raw_scope or "").strip()
                    if not raw_key:
                        continue
                    if raw_key.startswith(("acct.", "svc.")) and ".vault." in raw_key:
                        scope_key = safe_id(raw_key)
                    else:
                        scope_key = MemoryScope.from_legacy_user_id(
                            raw_key,
                            self.settings.sumeme_user_id,
                        ).storage_key
                    agent_id = str(raw_agent or "").strip()
                    if agent_id:
                        self._agent_ids.setdefault(scope_key, agent_id)
                return

            legacy = str(data.get("agent_id") or "").strip()
            if legacy:
                self._agent_ids.setdefault(default_scope.storage_key, legacy)
        except Exception:
            logger.warning("Could not read persisted Letta agent map", exc_info=True)

    def _persist_state(self) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_file.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(
                {
                    "schema_version": 3,
                    "scope_format": "principal.account.vault",
                    "agents": dict(sorted(self._agent_ids.items())),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(self._state_file)

    async def ensure_agent(
        self,
        scope: MemoryScope | str,
        *,
        timeout_seconds: float | None = None,
    ) -> str | None:
        if not self.settings.letta_enabled:
            return None

        resolved = self._scope(scope)
        scope_key = resolved.storage_key
        self._load_state()
        if agent_id := self._agent_ids.get(scope_key):
            return agent_id

        model_handle = self._resolved_model_handle()
        embedding_handle = self._resolved_embedding_handle()

        async with self._agent_lock:
            if agent_id := self._agent_ids.get(scope_key):
                return agent_id

            request_timeout = self._request_timeout(timeout_seconds)

            def create() -> Any:
                return self._get_client().agents.create(
                    name=f"{self.settings.letta_agent_name}-{safe_id(scope_key)}",
                    model=model_handle,
                    embedding=embedding_handle,
                    memory_blocks=[
                        {
                            "label": "human",
                            "value": (
                                "This is one isolated long-term memory vault. "
                                f"Scope: {resolved.display_key}. "
                                "Keep stable facts, preferences, projects, people, events, "
                                "dates, changes and contradictions. Never invent facts and "
                                "never copy facts from another scope."
                            ),
                        },
                        {
                            "label": "persona",
                            "value": (
                                "You are SuMeMe's private memory curator. "
                                "For MEMORY_UPDATE messages, update memory and answer briefly. "
                                "For RECALL_ONLY messages, return only relevant remembered facts "
                                "with uncertainty and dates when available."
                            ),
                        },
                    ],
                    request_options={"timeout_in_seconds": request_timeout},
                )

            try:
                agent = await anyio.to_thread.run_sync(
                    create,
                    abandon_on_cancel=True,
                )
            except Exception as exc:
                raise self._operation_error(exc, "agent_create") from exc

            agent_id = str(getattr(agent, "id", "") or "")
            if not agent_id:
                raise MemoryOperationError("letta_invalid_response")
            self._agent_ids[scope_key] = agent_id
            self._persist_state()
            logger.info(
                "Created Letta agent %s for scope %s",
                agent_id,
                resolved.display_key,
            )
            return agent_id

    async def recall(self, query: str, scope: MemoryScope | str) -> str:
        resolved = self._scope(scope)
        timeout_seconds = self.deadlines.recall_seconds
        agent_id = await self.ensure_agent(
            resolved,
            timeout_seconds=timeout_seconds,
        )
        if not agent_id or not query.strip():
            return ""

        prompt = (
            "[RECALL_ONLY]\n"
            f"Memory scope: {resolved.display_key}\n"
            "Return only personal memories relevant to the current question. "
            "Use concise Chinese bullet points. Include dates and uncertainty. "
            "Do not answer the question itself. Never use another scope.\n\n"
            f"Current question:\n{query[:12000]}"
        )
        request_timeout = self._request_timeout(timeout_seconds)
        try:
            response = await anyio.to_thread.run_sync(
                lambda: self._get_client().agents.messages.create(
                    agent_id=agent_id,
                    input=prompt,
                    request_options={"timeout_in_seconds": request_timeout},
                ),
                abandon_on_cancel=True,
            )
        except Exception as exc:
            raise self._operation_error(exc, "recall") from exc
        return self._extract_text(response)

    async def remember(
        self,
        *,
        scope: MemoryScope | str,
        user_text: str,
        assistant_text: str,
        conversation_id: str,
    ) -> bool:
        if not self.settings.letta_enabled:
            return False
        if not user_text.strip():
            return True

        resolved = self._scope(scope)
        timeout_seconds = self.deadlines.write_seconds
        agent_id = await self.ensure_agent(
            resolved,
            timeout_seconds=timeout_seconds,
        )
        if not agent_id:
            raise MemoryOperationError("letta_agent_unavailable")

        prompt = (
            "[MEMORY_UPDATE]\n"
            f"Memory scope: {resolved.display_key}\n"
            "Study this exchange and update durable personal memory. Preserve concrete "
            "names, dates, numbers, preferences, decisions, project status and changes. "
            "Do not treat assistant speculation as user fact. Never use or update another "
            "scope. Reply only with SAVED.\n\n"
            f"conversation_id: {conversation_id}\n"
            f"USER:\n{user_text[:30000]}\n\n"
            f"ASSISTANT:\n{assistant_text[:30000]}"
        )
        request_timeout = self._request_timeout(timeout_seconds)
        try:
            await anyio.to_thread.run_sync(
                lambda: self._get_client().agents.messages.create(
                    agent_id=agent_id,
                    input=prompt,
                    request_options={"timeout_in_seconds": request_timeout},
                ),
                abandon_on_cancel=True,
            )
        except Exception as exc:
            raise self._operation_error(exc, "write") from exc
        return True

    @staticmethod
    def _operation_error(exc: Exception, operation: str) -> MemoryOperationError:
        if isinstance(exc, MemoryOperationError):
            return exc

        status = getattr(exc, "status_code", None)
        if status is None:
            response = getattr(exc, "response", None)
            status = getattr(response, "status_code", None)
        try:
            status_code = int(status) if status is not None else None
        except (TypeError, ValueError):
            status_code = None

        name = type(exc).__name__.lower()
        if isinstance(exc, TimeoutError) or "timeout" in name:
            return MemoryOperationError("letta_timeout")
        if status_code in {401, 403}:
            return MemoryOperationError("letta_auth_failed")
        if status_code == 404:
            return MemoryOperationError("letta_agent_not_found")
        if status_code == 429:
            return MemoryOperationError("letta_rate_limited")
        if status_code is not None and status_code >= 500:
            return MemoryOperationError("letta_server_error")
        if status_code is not None and status_code >= 400:
            return MemoryOperationError(f"letta_{operation}_rejected")
        if "connection" in name or "connect" in name:
            return MemoryOperationError("letta_unavailable")
        return MemoryOperationError(f"letta_{operation}_failed")

    @staticmethod
    def _extract_text(response: Any) -> str:
        if hasattr(response, "model_dump"):
            value = response.model_dump()
        elif isinstance(response, dict):
            value = response
        else:
            value = json.loads(
                json.dumps(response, default=lambda obj: getattr(obj, "__dict__", str(obj)))
            )

        texts: list[str] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                message_type = str(node.get("message_type") or node.get("type") or "")
                if "assistant" in message_type:
                    content = node.get("content") or node.get("text")
                    if content:
                        texts.append(flatten_content(content))
                for child in node.values():
                    walk(child)
            elif isinstance(node, list):
                for child in node:
                    walk(child)

        walk(value)
        return "\n".join(dict.fromkeys(text for text in texts if text)).strip()
