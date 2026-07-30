from __future__ import annotations

import httpx
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.memory_result import MemoryOperationError
from app.remote_embeddings import RemoteEmbeddingClient


def make_settings(**overrides) -> Settings:
    values = {
        "openai_relay_base_url": "https://relay.example/v1",
        "openai_relay_api_key": SecretStr("relay-key"),
        "openai_embedding_model": "text-embedding-test",
        "gateway_api_key": SecretStr("gateway-key"),
        "gateway_admin_token": SecretStr("admin-key"),
        "mempalace_enabled": True,
        "letta_enabled": False,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.asyncio
async def test_embeddings_use_configured_relay_and_restore_input_order() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["body"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.3, 0.4]},
                    {"index": 0, "embedding": [0.1, 0.2]},
                ]
            },
        )

    client = RemoteEmbeddingClient(make_settings())
    await client._client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    vectors = await client.embed(["first", "second"], timeout_seconds=10)

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert captured["url"] == "https://relay.example/v1/embeddings"
    assert captured["authorization"] == "Bearer relay-key"
    assert '"model":"text-embedding-test"' in str(captured["body"]).replace(" ", "")
    await client.aclose()


@pytest.mark.asyncio
async def test_embedding_timeout_returns_stable_error_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client = RemoteEmbeddingClient(make_settings())
    await client._client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    with pytest.raises(MemoryOperationError) as error:
        await client.embed(["text"], timeout_seconds=3)

    assert error.value.code == "mempalace_embedding_timeout"
    await client.aclose()


@pytest.mark.asyncio
async def test_invalid_embedding_response_is_rejected() -> None:
    client = RemoteEmbeddingClient(make_settings())
    await client._client.aclose()
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={"data": [{"index": 0, "embedding": [1.0, "bad"]}]},
            )
        )
    )

    with pytest.raises(MemoryOperationError) as error:
        await client.embed(["text"], timeout_seconds=3)

    assert error.value.code == "mempalace_embedding_invalid_response"
    await client.aclose()
