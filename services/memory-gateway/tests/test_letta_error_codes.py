from __future__ import annotations

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
        "openai_embedding_model": "text-embedding-test",
        "gateway_api_key": SecretStr("gateway-key"),
        "gateway_admin_token": SecretStr("admin-key"),
        "mempalace_enabled": False,
        "letta_enabled": True,
        "letta_server_password": SecretStr("letta-key"),
        "letta_model": "openai/test-model",
        "letta_embedding": "openai/test-embedding",
    }
    values.update(overrides)
    return Settings(**values)


class StatusError(RuntimeError):
    def __init__(self, status_code: int):
        super().__init__("provider response intentionally hidden")
        self.status_code = status_code


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (StatusError(401), "letta_auth_failed"),
        (StatusError(404), "letta_agent_not_found"),
        (StatusError(429), "letta_rate_limited"),
        (StatusError(503), "letta_server_error"),
        (StatusError(400), "letta_write_rejected"),
        (TimeoutError(), "letta_timeout"),
    ],
)
def test_letta_exception_classification_is_stable(exception, expected) -> None:
    assert LettaMemory._operation_error(exception, "write").code == expected


@pytest.mark.asyncio
async def test_missing_letta_configuration_returns_sanitized_error(tmp_path) -> None:
    memory = LettaMemory(
        make_settings(
            letta_model="",
            letta_embedding="",
        )
    )
    memory._state_file = tmp_path / "state.json"

    with pytest.raises(MemoryOperationError) as error:
        await memory.ensure_agent(MemoryScope.account("account-a", "personal"))

    assert error.value.code == "letta_configuration_missing"


@pytest.mark.asyncio
async def test_letta_write_error_reaches_provider_boundary(tmp_path) -> None:
    memory = LettaMemory(make_settings())
    memory._state_file = tmp_path / "state.json"
    scope = MemoryScope.account("account-a", "personal")
    memory._state_loaded = True
    memory._agent_ids[scope.storage_key] = "agent-existing"

    class Messages:
        def create(self, **_kwargs):
            raise StatusError(400)

    memory._client = SimpleNamespace(agents=SimpleNamespace(messages=Messages()))

    with pytest.raises(MemoryOperationError) as error:
        await memory.remember(
            scope=scope,
            user_text="fact",
            assistant_text="answer",
            conversation_id="conversation-1",
        )

    assert error.value.code == "letta_write_rejected"
