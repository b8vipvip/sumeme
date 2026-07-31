from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from pydantic import SecretStr

from app.browser_memory_store import BrowserMemoryStore
from app.config import Settings
from app.memory_scope import MemoryScope


def make_settings(db_path: Path) -> Settings:
    return Settings(
        openai_relay_base_url="https://relay.example/v1",
        openai_relay_api_key=SecretStr("relay-key"),
        openai_chat_model="test-chat",
        openai_memory_model="test-memory",
        openai_embedding_model="test-embedding",
        gateway_api_key=SecretStr("gateway-key"),
        gateway_admin_token=SecretStr("admin-key"),
        mempalace_enabled=True,
        mempalace_remote_db_path=str(db_path),
        letta_enabled=False,
        letta_required=False,
    )


def insert_drawer(
    db_path: Path,
    *,
    drawer_id: str,
    point_id: str,
    scope: MemoryScope,
    role: str,
    conversation_id: str,
    text: str,
    created_at: str,
) -> None:
    content = json.dumps(
        {
            "account_id": scope.account_id,
            "content": text,
            "conversation_id": conversation_id,
            "role": role,
            "vault_id": scope.vault_id,
        },
        ensure_ascii=False,
    )
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO mempalace_drawers (
                drawer_id, point_id, principal_type, account_id, vault_id,
                wing, room, role, conversation_id, source, content,
                content_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                drawer_id,
                point_id,
                scope.principal_type,
                scope.account_id,
                scope.vault_id,
                f"scope_{scope.storage_key}",
                "conversation",
                role,
                conversation_id,
                f"lobe:{conversation_id}",
                content,
                f"hash-{drawer_id}",
                created_at,
            ),
        )


@pytest.mark.asyncio
async def test_list_detail_stats_are_strictly_scope_isolated(tmp_path: Path) -> None:
    db_path = tmp_path / "mempalace.sqlite3"
    store = BrowserMemoryStore(make_settings(db_path))
    await store.initialize()

    owner = MemoryScope.account("alice", "default")
    same_account_other_vault = MemoryScope.account("alice", "work")
    other_account = MemoryScope.account("bob", "default")

    insert_drawer(
        db_path,
        drawer_id="owner-user",
        point_id="point-owner-user",
        scope=owner,
        role="user",
        conversation_id="conversation-owner",
        text="OWNER_MARKER project preference",
        created_at="2026-07-31T10:00:00+00:00",
    )
    insert_drawer(
        db_path,
        drawer_id="owner-assistant",
        point_id="point-owner-assistant",
        scope=owner,
        role="assistant",
        conversation_id="conversation-owner",
        text="assistant response",
        created_at="2026-07-31T10:01:00+00:00",
    )
    insert_drawer(
        db_path,
        drawer_id="other-vault",
        point_id="point-other-vault",
        scope=same_account_other_vault,
        role="user",
        conversation_id="conversation-work",
        text="FOREIGN_VAULT_MARKER",
        created_at="2026-07-31T10:02:00+00:00",
    )
    insert_drawer(
        db_path,
        drawer_id="other-account",
        point_id="point-other-account",
        scope=other_account,
        role="user",
        conversation_id="conversation-bob",
        text="FOREIGN_ACCOUNT_MARKER",
        created_at="2026-07-31T10:03:00+00:00",
    )

    listing = await store.list_drawers(owner, limit=50)
    assert listing["total"] == 2
    assert [item["drawer_id"] for item in listing["items"]] == [
        "owner-assistant",
        "owner-user",
    ]
    assert all("FOREIGN_" not in item["preview"] for item in listing["items"])

    filtered = await store.list_drawers(owner, query="OWNER_MARKER", role="user")
    assert filtered["total"] == 1
    assert filtered["items"][0]["drawer_id"] == "owner-user"

    detail = await store.get_drawer(owner, "owner-user")
    assert detail is not None
    assert detail["text"] == "OWNER_MARKER project preference"
    assert await store.get_drawer(owner, "other-account") is None
    assert await store.get_drawer(owner, "other-vault") is None

    stats = await store.stats(owner)
    assert stats["total"] == 2
    assert stats["conversations"] == 1
    assert stats["roles"] == {"assistant": 1, "user": 1}
    assert stats["bytes"] > 0


@pytest.mark.asyncio
async def test_delete_removes_only_scoped_row_and_its_vector(tmp_path: Path) -> None:
    db_path = tmp_path / "mempalace.sqlite3"
    store = BrowserMemoryStore(make_settings(db_path))
    await store.initialize()

    owner = MemoryScope.account("alice", "default")
    foreign = MemoryScope.account("bob", "default")
    insert_drawer(
        db_path,
        drawer_id="shared-looking-id",
        point_id="point-owner",
        scope=owner,
        role="user",
        conversation_id="owner-conversation",
        text="owner text",
        created_at="2026-07-31T10:00:00+00:00",
    )
    insert_drawer(
        db_path,
        drawer_id="foreign-id",
        point_id="point-foreign",
        scope=foreign,
        role="user",
        conversation_id="foreign-conversation",
        text="foreign text",
        created_at="2026-07-31T10:00:00+00:00",
    )

    deleted_points: list[str] = []

    async def fake_delete_qdrant_point(point_id: str) -> None:
        deleted_points.append(point_id)

    store._delete_qdrant_point = fake_delete_qdrant_point  # type: ignore[method-assign]

    assert await store.delete_drawer(owner, "foreign-id") is False
    assert deleted_points == []
    assert await store.get_drawer(foreign, "foreign-id") is not None

    assert await store.delete_drawer(owner, "shared-looking-id") is True
    assert deleted_points == ["point-owner"]
    assert await store.get_drawer(owner, "shared-looking-id") is None
    assert await store.get_drawer(foreign, "foreign-id") is not None


@pytest.mark.asyncio
async def test_literal_search_escapes_sql_wildcards(tmp_path: Path) -> None:
    db_path = tmp_path / "mempalace.sqlite3"
    store = BrowserMemoryStore(make_settings(db_path))
    await store.initialize()
    scope = MemoryScope.account("alice", "default")

    insert_drawer(
        db_path,
        drawer_id="literal-percent",
        point_id="point-percent",
        scope=scope,
        role="user",
        conversation_id="conversation-percent",
        text="literal 100% complete_value",
        created_at="2026-07-31T10:00:00+00:00",
    )
    insert_drawer(
        db_path,
        drawer_id="wildcard-decoy",
        point_id="point-decoy",
        scope=scope,
        role="user",
        conversation_id="conversation-decoy",
        text="literal 100x completeZvalue",
        created_at="2026-07-31T10:01:00+00:00",
    )

    percent = await store.list_drawers(scope, query="100%")
    underscore = await store.list_drawers(scope, query="complete_value")

    assert [item["drawer_id"] for item in percent["items"]] == ["literal-percent"]
    assert [item["drawer_id"] for item in underscore["items"]] == ["literal-percent"]
