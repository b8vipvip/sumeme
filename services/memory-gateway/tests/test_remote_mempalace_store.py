from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.memory_scope import MemoryScope
from app.mempalace_store import MemPalaceStore


def make_settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "openai_relay_base_url": "https://relay.example/v1",
        "openai_relay_api_key": SecretStr("relay-key"),
        "openai_embedding_model": "text-embedding-test",
        "gateway_api_key": SecretStr("gateway-key"),
        "gateway_admin_token": SecretStr("admin-key"),
        "mempalace_enabled": True,
        "mempalace_qdrant_url": "http://qdrant:6333",
        "mempalace_qdrant_namespace": "test",
        "mempalace_remote_db_path": str(tmp_path / "drawers.sqlite3"),
        "letta_enabled": False,
    }
    values.update(overrides)
    return Settings(**values)


class FakeEmbeddings:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str], *, timeout_seconds: float):
        self.calls.append(list(texts))
        return [[float(index + 1), 0.5, 0.25] for index, _ in enumerate(texts)]

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_write_uses_remote_vectors_without_raw_qdrant_payload(tmp_path) -> None:
    requests: list[dict[str, object]] = []
    collection_exists = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal collection_exists
        body = json.loads(request.read() or b"{}")
        requests.append({"method": request.method, "path": request.url.path, "body": body})
        if request.method == "GET" and request.url.path.endswith("/collections/test_mempalace_remote_v1"):
            if not collection_exists:
                return httpx.Response(404, json={"status": "not found"})
            return httpx.Response(
                200,
                json={"result": {"config": {"params": {"vectors": {"size": 3}}}}},
            )
        if request.method == "PUT" and request.url.path.endswith("/collections/test_mempalace_remote_v1"):
            collection_exists = True
            return httpx.Response(200, json={"result": True})
        return httpx.Response(200, json={"result": {"status": "ok"}})

    store = MemPalaceStore(make_settings(tmp_path))
    await store._embedding.aclose()
    store._embedding = FakeEmbeddings()
    await store._qdrant.aclose()
    store._qdrant = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    scope = MemoryScope.account("account-a", "personal")

    accepted = await store.add_exchange(
        scope=scope,
        conversation_id="conversation-1",
        request_payload={"messages": [{"role": "user", "content": "private marker"}]},
        assistant="assistant marker",
    )

    assert accepted is True
    upsert = next(
        item
        for item in requests
        if item["method"] == "PUT" and str(item["path"]).endswith("/points")
    )
    serialized_payload = json.dumps(upsert["body"], ensure_ascii=False)
    assert "private marker" not in serialized_payload
    assert "assistant marker" not in serialized_payload
    points = upsert["body"]["points"]
    assert all(point["payload"]["scope_key"] == scope.storage_key for point in points)
    assert all("drawer_id" in point["payload"] for point in points)

    with store._connect() as connection:
        rows = connection.execute(
            "SELECT content FROM mempalace_drawers ORDER BY role"
        ).fetchall()
    persisted = "\n".join(str(row["content"]) for row in rows)
    assert "private marker" in persisted
    assert "assistant marker" in persisted
    await store.aclose()


@pytest.mark.asyncio
async def test_search_enforces_scope_in_qdrant_and_sqlite(tmp_path) -> None:
    observed_filter: dict | None = None
    scope_a = MemoryScope.account("account-a", "personal")
    scope_b = MemoryScope.account("account-b", "personal")

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_filter
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"result": {"config": {"params": {"vectors": {"size": 3}}}}},
            )
        if request.method == "POST" and request.url.path.endswith("/points/query"):
            body = json.loads(request.read())
            observed_filter = body["filter"]
            return httpx.Response(
                200,
                json={
                    "result": {
                        "points": [
                            {
                                "id": "point-a",
                                "score": 0.99,
                                "payload": {"drawer_id": "drawer-a"},
                            },
                            {
                                "id": "point-b",
                                "score": 0.98,
                                "payload": {"drawer_id": "drawer-b"},
                            },
                        ]
                    }
                },
            )
        return httpx.Response(200, json={"result": True})

    store = MemPalaceStore(make_settings(tmp_path))
    await store.initialize()
    now = "2026-01-01T00:00:00+00:00"
    store._store_drawers_sync(
        [
            {
                "drawer_id": "drawer-a",
                "point_id": "point-a",
                "principal_type": scope_a.principal_type,
                "account_id": scope_a.account_id,
                "vault_id": scope_a.vault_id,
                "wing": "scope-a",
                "room": "conversation",
                "role": "user",
                "conversation_id": "a",
                "source": "test",
                "content": "memory-a",
                "content_hash": "a" * 64,
                "created_at": now,
            },
            {
                "drawer_id": "drawer-b",
                "point_id": "point-b",
                "principal_type": scope_b.principal_type,
                "account_id": scope_b.account_id,
                "vault_id": scope_b.vault_id,
                "wing": "scope-b",
                "room": "conversation",
                "role": "user",
                "conversation_id": "b",
                "source": "test",
                "content": "memory-b",
                "content_hash": "b" * 64,
                "created_at": now,
            },
        ]
    )
    await store._embedding.aclose()
    store._embedding = FakeEmbeddings()
    await store._qdrant.aclose()
    store._qdrant = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    results = await store.search("question", scope_a)

    assert observed_filter == {
        "must": [{"key": "scope_key", "match": {"value": scope_a.storage_key}}]
    }
    assert [item["text"] for item in results] == ["memory-a"]
    await store.aclose()


@pytest.mark.asyncio
async def test_same_exchange_has_deterministic_point_ids(tmp_path) -> None:
    store = MemPalaceStore(make_settings(tmp_path))
    scope = MemoryScope.service("smoke", "production")
    kwargs = {
        "scope": scope,
        "conversation_id": "conversation-1",
        "request_payload": {"messages": [{"role": "user", "content": "same"}]},
        "assistant": "same answer",
    }

    first = store._build_items(**kwargs)
    second = store._build_items(**kwargs)

    assert [item["point_id"] for item in first] == [item["point_id"] for item in second]
    await store.aclose()
