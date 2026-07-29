from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import anyio

from .config import Settings
from .content import flatten_content, safe_id

logger = logging.getLogger(__name__)


class LettaMemory:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: Any | None = None
        self._agent_id: str | None = settings.letta_agent_id.strip() or None
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

    async def ensure_agent(self, user_id: str) -> str | None:
        if not self.settings.letta_enabled:
            return None
        if self._agent_id:
            return self._agent_id

        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text(encoding="utf-8"))
                saved = str(data.get("agent_id") or "")
                if saved:
                    self._agent_id = saved
                    return saved
            except Exception:
                logger.warning("Could not read persisted Letta agent id", exc_info=True)

        if not self.settings.letta_model or not self.settings.letta_embedding:
            logger.warning("Letta model/embedding missing; structured memory disabled")
            return None

        def create() -> Any:
            return self._get_client().agents.create(
                name=f"{self.settings.letta_agent_name}-{safe_id(user_id)}",
                model=self.settings.letta_model,
                embedding=self.settings.letta_embedding,
                memory_blocks=[
                    {
                        "label": "human",
                        "value": (
                            "This is the long-term personal memory for one user. "
                            "Keep stable facts, preferences, projects, people, events, "
                            "dates, changes and contradictions. Never invent facts."
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
            )

        try:
            agent = await anyio.to_thread.run_sync(create)
            agent_id = str(getattr(agent, "id", "") or "")
            if not agent_id:
                logger.error("Letta created an agent without an id")
                return None
            self._agent_id = agent_id
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._state_file.write_text(
                json.dumps({"agent_id": agent_id}, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("Created Letta agent %s", agent_id)
            return agent_id
        except Exception:
            logger.exception("Letta agent creation failed")
            return None

    async def recall(self, query: str, user_id: str) -> str:
        agent_id = await self.ensure_agent(user_id)
        if not agent_id or not query.strip():
            return ""

        prompt = (
            "[RECALL_ONLY]\n"
            "Return only personal memories relevant to the current question. "
            "Use concise Chinese bullet points. Include dates and uncertainty. "
            "Do not answer the question itself.\n\n"
            f"Current question:\n{query[:12000]}"
        )
        try:
            response = await anyio.to_thread.run_sync(
                lambda: self._get_client().agents.messages.create(
                    agent_id=agent_id,
                    input=prompt,
                )
            )
            return self._extract_text(response)
        except Exception:
            logger.exception("Letta recall failed")
            return ""

    async def remember(
        self,
        *,
        user_id: str,
        user_text: str,
        assistant_text: str,
        conversation_id: str,
    ) -> None:
        agent_id = await self.ensure_agent(user_id)
        if not agent_id or not user_text.strip():
            return

        prompt = (
            "[MEMORY_UPDATE]\n"
            "Study this exchange and update durable personal memory. Preserve concrete "
            "names, dates, numbers, preferences, decisions, project status and changes. "
            "Do not treat assistant speculation as user fact. Reply only with SAVED.\n\n"
            f"conversation_id: {conversation_id}\n"
            f"USER:\n{user_text[:30000]}\n\n"
            f"ASSISTANT:\n{assistant_text[:30000]}"
        )
        try:
            await anyio.to_thread.run_sync(
                lambda: self._get_client().agents.messages.create(
                    agent_id=agent_id,
                    input=prompt,
                )
            )
        except Exception:
            logger.exception("Letta memory update failed")

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
