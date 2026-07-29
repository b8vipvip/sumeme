from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from app.config import Settings
from app.memory import MemoryCoordinator
from app.memory_provider import MemPalaceLettaProvider
from app.supermemory_provider import SupermemoryProvider


def make_settings(**overrides) -> Settings:
    values = {
        "openai_relay_base_url": "https://relay.example/v1",
        "openai_relay_api_key": SecretStr("relay-key"),
        "gateway_api_key": SecretStr("gateway-key"),
        "gateway_admin_token": SecretStr("admin-key"),
        "letta_server_password": SecretStr("letta-key"),
        "letta_model": "openai/test-model",
        "letta_embedding": "openai/test-embedding",
    }
    values.update(overrides)
    return Settings(**values)


def test_default_provider_is_mempalace_letta() -> None:
    coordinator = MemoryCoordinator(make_settings())

    assert coordinator.provider_name == "mempalace-letta"
    assert isinstance(coordinator.provider, MemPalaceLettaProvider)


@pytest.mark.asyncio
async def test_supermemory_provider_is_selected_explicitly() -> None:
    coordinator = MemoryCoordinator(
        make_settings(
            memory_provider="supermemory",
            supermemory_base_url="https://memory.example",
            supermemory_api_key=SecretStr("supermemory-key"),
        )
    )

    assert coordinator.provider_name == "supermemory"
    assert isinstance(coordinator.provider, SupermemoryProvider)
    await coordinator.aclose()


def test_provider_alias_is_normalized() -> None:
    settings = make_settings(memory_provider="mempalace+letta")

    assert settings.memory_provider == "mempalace-letta"


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(ValidationError, match="MEMORY_PROVIDER"):
        make_settings(memory_provider="automatic")


def test_supermemory_requires_explicit_endpoint_and_key() -> None:
    with pytest.raises(ValidationError, match="SUPERMEMORY_BASE_URL"):
        make_settings(memory_provider="supermemory")

    with pytest.raises(ValidationError, match="SUPERMEMORY_API_KEY"):
        make_settings(
            memory_provider="supermemory",
            supermemory_base_url="https://memory.example",
        )
