from __future__ import annotations

import json

import httpx
import pytest
from pydantic import SecretStr

from app.config import Settings
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
        "memory_recall_limit": 5,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.asyncio
async def test_recall_uses_scoped_container_and_v4_search() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["authorization"] = request.headers.get("authorization")
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "results": [
                    {"memory": "用户喜欢喝茶", "similarity": 0.91},
                    {"chunk": "项目预计周五发布", "similarity": 0.82},
                ]
            },
        )

    provider = SupermemoryProvider(make_settings())
    await provider._client.aclose()
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    result = await provider.recall("用户喜欢什么", "account-a")

    assert captured["path"] == "/v4/search"
    assert captured["authorization"] == "Bearer supermemory-key"
    assert captured["payload"] == {
        "q": "用户喜欢什么",
        "containerTag": "sumeme:account-a",
        "searchMode": "hybrid",
        "limit": 5,
        "threshold": 0.6,
        "rerank": False,
    }
    assert "用户喜欢喝茶" in result
    assert "项目预计周五发布" in result
    await provider.aclose()


@pytest.mark.asyncio
async def test_remember_exchange_uses_idempotent_custom_id() -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(
            {
                "path": request.url.path,
                "payload": json.loads(request.content),
            }
        )
        return httpx.Response(200, json={"id": "doc-1", "status": "queued"})

    provider = SupermemoryProvider(make_settings())
    await provider._client.aclose()
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    kwargs = {
        "user_id": "account-a",
        "conversation_id": "conversation-1",
        "request_payload": {
            "messages": [{"role": "user", "content": "我喜欢喝茶"}]
        },
        "assistant_text": "我记住了。",
    }

    await provider.remember_exchange(**kwargs)
    await provider.remember_exchange(**kwargs)

    first = requests[0]
    second = requests[1]
    assert first["path"] == "/v3/documents"
    assert first["payload"]["containerTag"] == "sumeme:account-a"
    assert first["payload"]["taskType"] == "memory"
    assert first["payload"]["customId"] == second["payload"]["customId"]
    assert first["payload"]["customId"].startswith("sumeme-")
    assert "我喜欢喝茶" in first["payload"]["content"]
    await provider.aclose()


@pytest.mark.asyncio
async def test_search_failure_degrades_to_empty_context() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    provider = SupermemoryProvider(make_settings())
    await provider._client.aclose()
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    assert await provider.recall("test", "account-a") == ""
    await provider.aclose()
