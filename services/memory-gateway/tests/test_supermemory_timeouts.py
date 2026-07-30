from __future__ import annotations

import httpx
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.memory_scope import MemoryScope
from app.supermemory_provider import SupermemoryProvider


def make_settings(**overrides) -> Settings:
    values = {
        "openai_relay_base_url": "https://relay.example/v1",
        "openai_relay_api_key": SecretStr("relay-key"),
        "gateway_api_key": SecretStr("gateway-key"),
        "gateway_admin_token": SecretStr("admin-key"),
        "memory_provider": "supermemory",
        "supermemory_base_url": "https://memory.example",
        "supermemory_api_key": SecretStr("supermemory-key"),
        "supermemory_timeout_seconds": 90,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.asyncio
async def test_supermemory_recall_timeout_degrades_to_empty_context(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEMORY_RECALL_TIMEOUT_SECONDS", "7")
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["timeout"] = request.extensions.get("timeout")
        raise httpx.ReadTimeout("slow", request=request)

    provider = SupermemoryProvider(make_settings())
    await provider._client.aclose()
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    result = await provider.recall(
        "question",
        MemoryScope.account("account-a", "personal"),
    )

    assert result == ""
    assert captured["timeout"]["read"] == 7.0
    await provider.aclose()


@pytest.mark.asyncio
async def test_supermemory_write_timeout_has_stable_error_code(monkeypatch) -> None:
    monkeypatch.setenv("MEMORY_WRITE_TIMEOUT_SECONDS", "45")
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["timeout"] = request.extensions.get("timeout")
        raise httpx.ReadTimeout("slow", request=request)

    provider = SupermemoryProvider(make_settings())
    await provider._client.aclose()
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    result = await provider.remember_exchange(
        scope=MemoryScope.account("account-a", "personal"),
        conversation_id="conversation-1",
        request_payload={"messages": [{"role": "user", "content": "marker"}]},
        assistant_text="marker",
    )

    assert result.components == {"supermemory": False}
    assert result.error_codes == ("supermemory_write_timeout",)
    assert captured["timeout"]["read"] == 45.0
    await provider.aclose()
