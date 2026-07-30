from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.config import Settings
from app.letta_memory import LettaMemory
from app.memory_scope import MemoryScope


def make_settings(**overrides) -> Settings:
    values = {
        "openai_relay_base_url": "https://relay.example/v1",
        "openai_relay_api_key": SecretStr("relay-key"),
        "gateway_api_key": SecretStr("gateway-key"),
        "gateway_admin_token": SecretStr("admin-key"),
        "sumeme_user_id": "default",
        "letta_enabled": True,
        "letta_server_password": SecretStr("letta-key"),
        "letta_model": "openai/test-model",
        "letta_embedding": "openai/test-embedding",
        "letta_timeout_seconds": 90,
    }
    values.update(overrides)
    return Settings(**values)


class RecordingMessages:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return {}


class RecordingAgents:
    def __init__(self) -> None:
        self.messages = RecordingMessages()
        self.create_calls: list[dict] = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return SimpleNamespace(id="agent-created")


@pytest.mark.asyncio
async def test_recall_passes_short_deadline_to_letta_sdk(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MEMORY_RECALL_TIMEOUT_SECONDS", "7")
    memory = LettaMemory(make_settings(letta_timeout_seconds=90))
    memory._state_file = tmp_path / "letta-agent.json"
    agents = RecordingAgents()
    memory._client = SimpleNamespace(agents=agents)
    scope = MemoryScope.account("account-a", "personal")
    memory._state_loaded = True
    memory._agent_ids[scope.storage_key] = "agent-existing"

    await memory.recall("question", scope)

    assert len(agents.messages.calls) == 1
    assert agents.messages.calls[0]["request_options"] == {
        "timeout_in_seconds": 7.0
    }


@pytest.mark.asyncio
async def test_write_passes_write_deadline_to_letta_sdk(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MEMORY_WRITE_TIMEOUT_SECONDS", "45")
    memory = LettaMemory(make_settings(letta_timeout_seconds=90))
    memory._state_file = tmp_path / "letta-agent.json"
    agents = RecordingAgents()
    memory._client = SimpleNamespace(agents=agents)
    scope = MemoryScope.account("account-a", "personal")
    memory._state_loaded = True
    memory._agent_ids[scope.storage_key] = "agent-existing"

    accepted = await memory.remember(
        scope=scope,
        user_text="user fact",
        assistant_text="acknowledged",
        conversation_id="conversation-1",
    )

    assert accepted is True
    assert agents.messages.calls[0]["request_options"] == {
        "timeout_in_seconds": 45.0
    }


@pytest.mark.asyncio
async def test_agent_creation_uses_lower_of_operation_and_letta_deadlines(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("MEMORY_WRITE_TIMEOUT_SECONDS", "120")
    memory = LettaMemory(make_settings(letta_timeout_seconds=30))
    memory._state_file = tmp_path / "letta-agent.json"
    agents = RecordingAgents()
    memory._client = SimpleNamespace(agents=agents)

    agent_id = await memory.ensure_agent(
        MemoryScope.account("account-a", "personal"),
        timeout_seconds=120,
    )

    assert agent_id == "agent-created"
    assert agents.create_calls[0]["request_options"] == {
        "timeout_in_seconds": 30.0
    }
