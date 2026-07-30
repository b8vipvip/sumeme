from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.config import Settings
from app.letta_memory import LettaMemory
from app.memory_result import MemoryOperationError
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


class ConstantAgents:
    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.created_names: list[str] = []
        self.messages = SimpleNamespace(create=lambda **_kwargs: {})

    def create(self, **kwargs):
        self.created_names.append(kwargs["name"])
        return SimpleNamespace(id=self.agent_id)


@pytest.mark.asyncio
async def test_legacy_agent_is_migrated_only_for_default_scope(tmp_path) -> None:
    state_file = tmp_path / "letta-agent.json"
    state_file.write_text(json.dumps({"agent_id": "legacy-agent"}), encoding="utf-8")

    memory = LettaMemory(make_settings())
    memory._state_file = state_file
    agents = FakeAgents()
    memory._client = SimpleNamespace(agents=agents)

    assert await memory.ensure_agent(MemoryScope.account("default")) == "legacy-agent"
    smoke_agent = await memory.ensure_agent(
        MemoryScope.service("sumeme-smoke", "production-smoke")
    )

    assert smoke_agent == "agent-1"
    assert agents.created_names == [
        "sumeme-personal-memory-svc.sumeme-smoke.vault.production-smoke"
    ]

    persisted = json.loads(state_file.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == 4
    assert persisted["ownership"] == "one-agent-per-scope"
    assert persisted["agents"]["acct.default.vault.default"] == "legacy-agent"
    assert (
        persisted["agents"]["svc.sumeme-smoke.vault.production-smoke"]
        == "agent-1"
    )


@pytest.mark.asyncio
async def test_schema_two_user_map_migrates_to_default_vault(tmp_path) -> None:
    state_file = tmp_path / "letta-agent.json"
    state_file.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "agents": {
                    "default": "default-agent",
                    "user-a": "user-agent",
                    "sumeme_smoke": "smoke-agent",
                },
            }
        ),
        encoding="utf-8",
    )

    memory = LettaMemory(make_settings())
    memory._state_file = state_file

    assert await memory.ensure_agent(MemoryScope.account("default")) == "default-agent"
    assert await memory.ensure_agent(MemoryScope.account("user-a")) == "user-agent"
    assert (
        await memory.ensure_agent(MemoryScope.service("sumeme-smoke", "production-smoke"))
        == "smoke-agent"
    )
    persisted = json.loads(state_file.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == 4


@pytest.mark.asyncio
async def test_explicit_agent_id_does_not_leak_to_other_scopes(tmp_path) -> None:
    memory = LettaMemory(make_settings(letta_agent_id="configured-default-agent"))
    memory._state_file = tmp_path / "letta-agent.json"
    agents = FakeAgents()
    memory._client = SimpleNamespace(agents=agents)

    assert (
        await memory.ensure_agent(MemoryScope.account("default"))
        == "configured-default-agent"
    )
    assert await memory.ensure_agent(MemoryScope.account("another-user")) == "agent-1"
    assert await memory.ensure_agent(
        MemoryScope.account("default", "work")
    ) == "agent-2"
    assert agents.created_names == [
        "sumeme-personal-memory-acct.another-user.vault.default",
        "sumeme-personal-memory-acct.default.vault.work",
    ]


@pytest.mark.asyncio
async def test_same_scope_reuses_persisted_agent(tmp_path) -> None:
    memory = LettaMemory(make_settings())
    memory._state_file = tmp_path / "letta-agent.json"
    agents = FakeAgents()
    memory._client = SimpleNamespace(agents=agents)
    scope = MemoryScope.account("user-a", "work")

    first = await memory.ensure_agent(scope)
    second = await memory.ensure_agent(scope)

    assert first == second == "agent-1"
    assert len(agents.created_names) == 1


@pytest.mark.asyncio
async def test_account_and_vault_pairs_never_share_an_agent(tmp_path) -> None:
    memory = LettaMemory(make_settings())
    memory._state_file = tmp_path / "letta-agent.json"
    agents = FakeAgents()
    memory._client = SimpleNamespace(agents=agents)

    scopes = [
        MemoryScope.account("account-a", "personal"),
        MemoryScope.account("account-a", "work"),
        MemoryScope.account("account-b", "personal"),
        MemoryScope.service("account-a", "personal"),
    ]
    agent_ids = [await memory.ensure_agent(scope) for scope in scopes]

    assert agent_ids == ["agent-1", "agent-2", "agent-3", "agent-4"]
    assert len(set(agent_ids)) == len(scopes)


@pytest.mark.asyncio
async def test_duplicate_persisted_agent_is_invalidated_for_all_scopes(tmp_path) -> None:
    state_file = tmp_path / "letta-agent.json"
    state_file.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "agents": {
                    "acct.account-a.vault.personal": "shared-agent",
                    "acct.account-b.vault.personal": "shared-agent",
                },
            }
        ),
        encoding="utf-8",
    )
    memory = LettaMemory(make_settings())
    memory._state_file = state_file
    agents = FakeAgents()
    memory._client = SimpleNamespace(agents=agents)

    first = await memory.ensure_agent(MemoryScope.account("account-a", "personal"))
    second = await memory.ensure_agent(MemoryScope.account("account-b", "personal"))

    assert first == "agent-1"
    assert second == "agent-2"
    persisted = json.loads(state_file.read_text(encoding="utf-8"))
    assert "shared-agent" not in persisted["agents"].values()
    assert len(set(persisted["agents"].values())) == 2


@pytest.mark.asyncio
async def test_server_returning_existing_agent_id_fails_closed(tmp_path) -> None:
    memory = LettaMemory(make_settings())
    memory._state_file = tmp_path / "letta-agent.json"
    agents = ConstantAgents("same-agent")
    memory._client = SimpleNamespace(agents=agents)

    assert (
        await memory.ensure_agent(MemoryScope.account("account-a", "personal"))
        == "same-agent"
    )
    with pytest.raises(MemoryOperationError) as captured:
        await memory.ensure_agent(MemoryScope.account("account-b", "personal"))

    assert captured.value.code == "letta_agent_ownership_conflict"
    persisted = json.loads(memory._state_file.read_text(encoding="utf-8"))
    assert persisted["agents"] == {}


@pytest.mark.asyncio
async def test_explicit_agent_ownership_survives_conflicting_state(tmp_path) -> None:
    state_file = tmp_path / "letta-agent.json"
    state_file.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "agents": {
                    "acct.default.vault.default": "stale-default-agent",
                    "acct.other.vault.default": "configured-default-agent",
                },
            }
        ),
        encoding="utf-8",
    )
    memory = LettaMemory(make_settings(letta_agent_id="configured-default-agent"))
    memory._state_file = state_file
    agents = FakeAgents()
    memory._client = SimpleNamespace(agents=agents)

    assert (
        await memory.ensure_agent(MemoryScope.account("default"))
        == "configured-default-agent"
    )
    assert await memory.ensure_agent(MemoryScope.account("other")) == "agent-1"

    persisted = json.loads(state_file.read_text(encoding="utf-8"))
    assert (
        persisted["agents"]["acct.default.vault.default"]
        == "configured-default-agent"
    )
    assert persisted["agents"]["acct.other.vault.default"] == "agent-1"
