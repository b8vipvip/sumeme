from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.config import Settings
from app.letta_memory import LettaMemory


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
    }
    values.update(overrides)
    return Settings(**values)


class FakeAgents:
    def __init__(self) -> None:
        self.created_names: list[str] = []
        self.messages = SimpleNamespace(create=lambda **_kwargs: {})

    def create(self, **kwargs):
        self.created_names.append(kwargs["name"])
        return SimpleNamespace(id=f"agent-{len(self.created_names)}")


@pytest.mark.asyncio
async def test_legacy_agent_is_migrated_only_for_default_user(tmp_path) -> None:
    state_file = tmp_path / "letta-agent.json"
    state_file.write_text(json.dumps({"agent_id": "legacy-agent"}), encoding="utf-8")

    memory = LettaMemory(make_settings())
    memory._state_file = state_file
    agents = FakeAgents()
    memory._client = SimpleNamespace(agents=agents)

    assert await memory.ensure_agent("default") == "legacy-agent"
    smoke_agent = await memory.ensure_agent("__sumeme_smoke__")

    assert smoke_agent == "agent-1"
    assert agents.created_names == ["sumeme-personal-memory-sumeme_smoke"]

    persisted = json.loads(state_file.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == 2
    assert persisted["agents"]["default"] == "legacy-agent"
    assert persisted["agents"]["sumeme_smoke"] == "agent-1"


@pytest.mark.asyncio
async def test_explicit_agent_id_does_not_leak_to_other_users(tmp_path) -> None:
    memory = LettaMemory(make_settings(letta_agent_id="configured-default-agent"))
    memory._state_file = tmp_path / "letta-agent.json"
    agents = FakeAgents()
    memory._client = SimpleNamespace(agents=agents)

    assert await memory.ensure_agent("default") == "configured-default-agent"
    assert await memory.ensure_agent("another-user") == "agent-1"
    assert agents.created_names == ["sumeme-personal-memory-another-user"]


@pytest.mark.asyncio
async def test_same_user_reuses_persisted_agent(tmp_path) -> None:
    memory = LettaMemory(make_settings())
    memory._state_file = tmp_path / "letta-agent.json"
    agents = FakeAgents()
    memory._client = SimpleNamespace(agents=agents)

    first = await memory.ensure_agent("user-a")
    second = await memory.ensure_agent("user-a")

    assert first == second == "agent-1"
    assert len(agents.created_names) == 1
