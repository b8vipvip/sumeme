from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.config import Settings
from app.memory_provider import MemPalaceLettaProvider
from app.memory_result import MemoryWriteResult
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


def test_write_result_exposes_only_sanitized_status() -> None:
    result = MemoryWriteResult(
        provider="mempalace-letta",
        components={"mempalace": True, "letta": False},
        error_codes=("letta_write_rejected",),
    )

    assert result.success is False
    assert result.as_dict() == {
        "provider": "mempalace-letta",
        "success": False,
        "components": {"mempalace": True, "letta": False},
        "error_codes": ["letta_write_rejected"],
    }


@pytest.mark.asyncio
async def test_default_provider_reports_each_component() -> None:
    provider = MemPalaceLettaProvider(make_settings())
    provider.mempalace = SimpleNamespace(
        add_exchange=_async_value(True),
    )
    provider.letta = SimpleNamespace(
        remember=_async_value(False),
    )

    result = await provider.remember_exchange(
        scope=MemoryScope.service("smoke", "test"),
        conversation_id="conversation-1",
        request_payload={"messages": [{"role": "user", "content": "marker"}]},
        assistant_text="marker",
    )

    assert result.provider == "mempalace-letta"
    assert result.components == {"mempalace": True, "letta": False}
    assert result.error_codes == ("letta_write_rejected",)
    assert result.success is False


@pytest.mark.asyncio
async def test_default_provider_converts_exceptions_to_error_codes() -> None:
    provider = MemPalaceLettaProvider(make_settings())
    provider.mempalace = SimpleNamespace(
        add_exchange=_async_exception(RuntimeError("secret provider response")),
    )
    provider.letta = SimpleNamespace(
        remember=_async_value(True),
    )

    result = await provider.remember_exchange(
        scope=MemoryScope.service("smoke", "test"),
        conversation_id="conversation-1",
        request_payload={"messages": [{"role": "user", "content": "marker"}]},
        assistant_text="marker",
    )

    assert result.components == {"mempalace": False, "letta": True}
    assert result.error_codes == ("mempalace_write_exception",)
    assert "secret" not in str(result.as_dict())


def _async_value(value: bool):
    async def call(**_kwargs):
        return value

    return call


def _async_exception(error: Exception):
    async def call(**_kwargs):
        raise error

    return call
