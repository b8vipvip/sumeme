from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.config import Settings
from app.memory_deadlines import MemoryDeadlines
from app.memory_provider import MemPalaceLettaProvider
from app.memory_scope import MemoryScope


def make_settings(**overrides) -> Settings:
    values = {
        "openai_relay_base_url": "https://relay.example/v1",
        "openai_relay_api_key": SecretStr("relay-key"),
        "gateway_api_key": SecretStr("gateway-key"),
        "gateway_admin_token": SecretStr("admin-key"),
        "mempalace_enabled": True,
        "letta_enabled": True,
        "letta_server_password": SecretStr("letta-key"),
        "letta_model": "openai/test-model",
        "letta_embedding": "openai/test-embedding",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.asyncio
async def test_recall_uses_partial_memory_when_one_component_times_out(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEMORY_RECALL_TIMEOUT_SECONDS", "0.1")
    provider = MemPalaceLettaProvider(make_settings())
    provider.mempalace = SimpleNamespace(
        search=_async_result(
            [
                {
                    "wing": "scope-test",
                    "room": "conversation",
                    "text": "available raw memory",
                    "similarity": 0.99,
                }
            ]
        )
    )
    provider.letta = SimpleNamespace(recall=_slow_result("late structured memory"))

    context = await provider.recall(
        "question",
        MemoryScope.account("account-a", "personal"),
    )

    assert "available raw memory" in context
    assert "late structured memory" not in context


@pytest.mark.asyncio
async def test_recall_returns_quickly_when_both_components_time_out(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEMORY_RECALL_TIMEOUT_SECONDS", "0.1")
    provider = MemPalaceLettaProvider(make_settings())
    provider.mempalace = SimpleNamespace(search=_slow_result([]))
    provider.letta = SimpleNamespace(recall=_slow_result("late"))

    context = await asyncio.wait_for(
        provider.recall(
            "question",
            MemoryScope.account("account-a", "personal"),
        ),
        timeout=1.0,
    )

    assert context == ""


@pytest.mark.asyncio
async def test_write_timeout_is_reported_per_component(monkeypatch) -> None:
    monkeypatch.setenv("MEMORY_WRITE_TIMEOUT_SECONDS", "0.1")
    provider = MemPalaceLettaProvider(make_settings())
    provider.mempalace = SimpleNamespace(add_exchange=_slow_result(True))
    provider.letta = SimpleNamespace(remember=_async_result(True))

    result = await provider.remember_exchange(
        scope=MemoryScope.service("smoke", "test"),
        conversation_id="conversation-1",
        request_payload={"messages": [{"role": "user", "content": "marker"}]},
        assistant_text="marker",
    )

    assert result.components == {"mempalace": False, "letta": True}
    assert result.error_codes == ("mempalace_write_timeout",)


def test_deadline_environment_is_validated(monkeypatch) -> None:
    monkeypatch.setenv("MEMORY_RECALL_TIMEOUT_SECONDS", "not-a-number")

    with pytest.raises(ValueError, match="MEMORY_RECALL_TIMEOUT_SECONDS"):
        MemoryDeadlines.from_environment()


def _async_result(value):
    async def call(*_args, **_kwargs):
        return value

    return call


def _slow_result(value):
    async def call(*_args, **_kwargs):
        await asyncio.sleep(60)
        return value

    return call
