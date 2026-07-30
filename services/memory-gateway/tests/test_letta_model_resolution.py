from __future__ import annotations

import pytest
from pydantic import SecretStr

from app.config import Settings
from app.letta_memory import LettaMemory
from app.memory_result import MemoryOperationError


def make_settings(**overrides) -> Settings:
    values = {
        "openai_relay_base_url": "https://relay.example/v1",
        "openai_relay_api_key": SecretStr("relay-key"),
        "openai_chat_model": "gpt-5.6-sol",
        "openai_memory_model": "replace_me",
        "openai_embedding_model": "text-embedding-3-small",
        "gateway_api_key": SecretStr("gateway-key"),
        "gateway_admin_token": SecretStr("admin-key"),
        "mempalace_enabled": True,
        "letta_enabled": True,
        "letta_model": "openai/replace_me",
        "letta_embedding": "openai/text-embedding-3-small",
    }
    values.update(overrides)
    return Settings(**values)


def test_placeholder_model_resolves_to_openai_proxy_chat_model() -> None:
    memory = LettaMemory(make_settings())

    assert memory._resolved_model_handle() == "openai-proxy/gpt-5.6-sol"
    assert memory._resolved_embedding_handle() == "openai/text-embedding-3-small"


def test_memory_model_precedes_chat_model() -> None:
    memory = LettaMemory(
        make_settings(openai_memory_model="gpt-memory", openai_chat_model="gpt-chat")
    )

    assert memory._resolved_model_handle() == "openai-proxy/gpt-memory"


def test_explicit_letta_handles_are_preserved() -> None:
    memory = LettaMemory(
        make_settings(
            letta_model="openai-proxy/custom-model",
            letta_embedding="openai/custom-embedding",
        )
    )

    assert memory._resolved_model_handle() == "openai-proxy/custom-model"
    assert memory._resolved_embedding_handle() == "openai/custom-embedding"


def test_missing_remote_model_is_rejected() -> None:
    memory = LettaMemory(
        make_settings(
            openai_chat_model="replace_me",
            openai_memory_model="replace_me",
        )
    )

    with pytest.raises(MemoryOperationError) as error:
        memory._resolved_model_handle()

    assert error.value.code == "letta_model_unavailable"
