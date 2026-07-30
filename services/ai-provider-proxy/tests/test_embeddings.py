from __future__ import annotations

import json

import httpx
import pytest

from app.main import EmbeddingRouter, Settings, _hash_tags, _parse_tag_response


def settings(monkeypatch, **overrides) -> Settings:
    values = {
        "OPENAI_RELAY_BASE_URL": "https://relay.example/v1",
        "OPENAI_RELAY_API_KEY": "relay-key",
        "PROVIDER_PROXY_API_KEY": "proxy-key",
        "OPENAI_CHAT_MODEL": "gpt-test",
        "OPENAI_MEMORY_MODEL": "",
        "OPENAI_EMBEDDING_MODEL": "text-embedding-test",
        "EMBEDDING_PROVIDER_MODE": "auto",
        "EMBEDDING_DIMENSION": "128",
    }
    values.update({key: str(value) for key, value in overrides.items()})
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return Settings.from_environment()


@pytest.mark.asyncio
async def test_native_embedding_response_is_passed_through(monkeypatch) -> None:
    config = settings(monkeypatch, EMBEDDING_PROVIDER_MODE="native")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/embeddings"
        assert request.headers["authorization"] == "Bearer relay-key"
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [{"object": "embedding", "embedding": [0.1, 0.2], "index": 0}],
                "model": "text-embedding-test",
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    router = EmbeddingRouter(config, client)

    response = await router.create(
        {"model": "text-embedding-test", "input": ["hello"]}
    )

    body = json.loads(response.body)
    assert body["data"][0]["embedding"] == [0.1, 0.2]
    assert router._native_supported is True
    await client.aclose()


@pytest.mark.asyncio
async def test_auto_mode_falls_back_to_remote_semantic_hash(monkeypatch) -> None:
    config = settings(monkeypatch)
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/v1/embeddings":
            return httpx.Response(
                404,
                json={
                    "error": {
                        "type": "bad_response_status_code",
                        "code": "bad_response_status_code",
                    }
                },
            )
        if request.url.path == "/v1/chat/completions":
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"items":[["project sumeme","memory system",'
                                    '"remote ai","privacy vault","deployment"]]}'
                                )
                            }
                        }
                    ]
                },
            )
        raise AssertionError(request.url)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    router = EmbeddingRouter(config, client)

    first = await router.create(
        {"model": "text-embedding-test", "input": "SuMeMe memory project"}
    )
    second = await router.create(
        {"model": "text-embedding-test", "input": "SuMeMe memory project"}
    )

    first_body = json.loads(first.body)
    second_body = json.loads(second.body)
    vector = first_body["data"][0]["embedding"]
    assert len(vector) == 128
    assert vector == second_body["data"][0]["embedding"]
    assert sum(value * value for value in vector) == pytest.approx(1.0)
    assert calls.count("/v1/embeddings") == 1
    assert calls.count("/v1/chat/completions") == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_semantic_mode_never_calls_native_embedding_endpoint(monkeypatch) -> None:
    config = settings(
        monkeypatch,
        EMBEDDING_PROVIDER_MODE="remote-semantic-hash",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"items":[["alpha","beta","gamma","delta"]]}'
                            )
                        }
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    router = EmbeddingRouter(config, client)

    response = await router.create({"input": "text", "model": "ignored"})

    assert len(json.loads(response.body)["data"][0]["embedding"]) == 128
    await client.aclose()


def test_tag_parser_rejects_wrong_item_count() -> None:
    with pytest.raises(ValueError, match="item count"):
        _parse_tag_response('{"items":[["a","b","c","d"]]}', 2)


def test_hash_vector_is_deterministic_and_normalized() -> None:
    first = _hash_tags(["one", "two", "three", "four"], 128)
    second = _hash_tags(["one", "two", "three", "four"], 128)

    assert first == second
    assert sum(value * value for value in first) == pytest.approx(1.0)
