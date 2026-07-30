from __future__ import annotations

import json
from pathlib import Path

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
        "mempalace_qdrant_namespace": "test",
        "mempalace_remote_db_path": str(tmp_path / "drawers.sqlite3"),
        "letta_enabled": False,
    }
    values.update(overrides)
    return Settings(**values)


def test_drawers_embed_account_vault_and_principal_metadata(tmp_path) -> None:
    store = MemPalaceStore(make_settings(tmp_path))
    scope = MemoryScope.account("account-a", "work")

    items = store._build_items(
        scope=scope,
        conversation_id="conversation-1",
        request_payload={"messages": [{"role": "user", "content": "hello"}]},
        assistant="world",
    )

    assert len(items) == 2
    assert {item["wing"] for item in items} == {
        "scope_acct.account-a.vault.work"
    }
    assert {item["principal_type"] for item in items} == {"account"}
    assert {item["account_id"] for item in items} == {"account-a"}
    assert {item["vault_id"] for item in items} == {"work"}
    first = json.loads(items[0]["content"])
    assert first["scope_key"] == "acct.account-a.vault.work"


def test_same_names_in_account_and_service_scopes_never_share_drawer_ids(
    tmp_path,
) -> None:
    store = MemPalaceStore(make_settings(tmp_path))
    request = {"messages": [{"role": "user", "content": "same"}]}

    account_items = store._build_items(
        scope=MemoryScope.account("same-name", "personal"),
        conversation_id="conversation-1",
        request_payload=request,
        assistant="same",
    )
    service_items = store._build_items(
        scope=MemoryScope.service("same-name", "personal"),
        conversation_id="conversation-1",
        request_payload=request,
        assistant="same",
    )

    assert {item["drawer_id"] for item in account_items}.isdisjoint(
        {item["drawer_id"] for item in service_items}
    )
    assert {item["wing"] for item in account_items} != {
        item["wing"] for item in service_items
    }
