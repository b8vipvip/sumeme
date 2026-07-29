from __future__ import annotations

import json

import pytest
from pydantic import SecretStr

from app.config import Settings
from app.memory_scope import MemoryScope
from app.mempalace_store import MemPalaceStore


def make_settings(**overrides) -> Settings:
    values = {
        "openai_relay_base_url": "https://relay.example/v1",
        "openai_relay_api_key": SecretStr("relay-key"),
        "gateway_api_key": SecretStr("gateway-key"),
        "gateway_admin_token": SecretStr("admin-key"),
        "mempalace_enabled": True,
        "mempalace_recall_limit": 6,
    }
    values.update(overrides)
    return Settings(**values)


def test_wing_contains_account_vault_and_principal() -> None:
    scopes = [
        MemoryScope.account("account-a", "personal"),
        MemoryScope.account("account-a", "work"),
        MemoryScope.account("account-b", "personal"),
        MemoryScope.service("account-a", "personal"),
    ]

    wings = {MemPalaceStore._wing(scope) for scope in scopes}

    assert len(wings) == len(scopes)
    assert "scope_acct.account-a.vault.personal" in wings
    assert "scope_svc.account-a.vault.personal" in wings


def test_legacy_wing_is_only_used_for_compatible_default_vaults() -> None:
    assert (
        MemPalaceStore._legacy_wing(MemoryScope.account("account-a", "default"))
        == "user_account-a"
    )
    assert MemPalaceStore._legacy_wing(MemoryScope.account("account-a", "work")) is None
    assert (
        MemPalaceStore._legacy_wing(
            MemoryScope.service("sumeme-smoke", "production-smoke")
        )
        == "user_sumeme_smoke"
    )


@pytest.mark.asyncio
async def test_write_embeds_scope_metadata_and_uses_scoped_wing() -> None:
    captured: dict[str, object] = {}

    def checkpoint_handler(**kwargs):
        captured.update(kwargs)
        return {"added": len(kwargs["items"])}

    store = MemPalaceStore(make_settings())
    store._tools = {
        "mempalace_checkpoint": {"handler": checkpoint_handler},
        "mempalace_search": {"handler": lambda **_kwargs: {"results": []}},
    }
    scope = MemoryScope.account("account-a", "work")

    await store.add_exchange(
        scope=scope,
        conversation_id="conversation-1",
        request_payload={"messages": [{"role": "user", "content": "hello"}]},
        assistant="world",
    )

    items = captured["items"]
    assert len(items) == 2
    assert {item["wing"] for item in items} == {
        "scope_acct.account-a.vault.work"
    }
    first = json.loads(items[0]["content"])
    assert first["account_id"] == "account-a"
    assert first["vault_id"] == "work"
    assert first["principal_type"] == "account"
    assert first["scope_key"] == "acct.account-a.vault.work"


@pytest.mark.asyncio
async def test_search_never_queries_another_account_or_vault() -> None:
    queried_wings: list[str] = []

    def search_handler(**kwargs):
        queried_wings.append(kwargs["wing"])
        return {
            "results": [
                {
                    "wing": kwargs["wing"],
                    "room": "conversation",
                    "text": kwargs["wing"],
                    "similarity": 0.9,
                }
            ]
        }

    store = MemPalaceStore(make_settings())
    store._tools = {
        "mempalace_checkpoint": {"handler": lambda **_kwargs: {}},
        "mempalace_search": {"handler": search_handler},
    }

    results = await store.search("test", MemoryScope.account("account-a", "work"))

    assert queried_wings == ["scope_acct.account-a.vault.work"]
    assert all("account-b" not in wing for wing in queried_wings)
    assert all(item["wing"] == "scope_acct.account-a.vault.work" for item in results)
