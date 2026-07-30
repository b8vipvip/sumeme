from __future__ import annotations

import asyncio

import pytest

from app.memory_scope import MemoryScope
from app.vaults import (
    VaultRegistry,
    VaultRegistryError,
    normalize_storage_mode,
    should_auto_register_vault,
)


@pytest.mark.asyncio
async def test_registry_keys_include_principal_account_and_vault(tmp_path) -> None:
    registry = VaultRegistry(str(tmp_path / "vaults.sqlite3"))
    await registry.initialize()

    personal = await registry.ensure(
        MemoryScope.account("alice", "personal"),
        allow_create=True,
    )
    work = await registry.ensure(
        MemoryScope.account("alice", "work"),
        allow_create=True,
    )
    other_user = await registry.ensure(
        MemoryScope.account("bob", "personal"),
        allow_create=True,
    )
    service = await registry.ensure(
        MemoryScope.service("alice", "personal"),
        allow_create=True,
    )

    keys = {
        personal.scope.storage_key,
        work.scope.storage_key,
        other_user.scope.storage_key,
        service.scope.storage_key,
    }
    assert len(keys) == 4
    assert all(
        policy.storage_mode == "cloud"
        for policy in [personal, work, other_user, service]
    )


@pytest.mark.asyncio
async def test_unknown_vault_is_rejected_when_identity_cannot_auto_register(tmp_path) -> None:
    registry = VaultRegistry(str(tmp_path / "vaults.sqlite3"))
    await registry.initialize()

    with pytest.raises(VaultRegistryError) as captured:
        await registry.ensure(
            MemoryScope.account("alice", "unregistered"),
            allow_create=False,
        )

    assert captured.value.code == "vault_not_registered"
    assert captured.value.status_code == 403


@pytest.mark.asyncio
async def test_explicit_policy_update_preserves_creation_time(tmp_path) -> None:
    registry = VaultRegistry(str(tmp_path / "vaults.sqlite3"))
    await registry.initialize()
    scope = MemoryScope.account("alice", "personal")

    original = await registry.ensure(scope, allow_create=True)
    hybrid = await registry.upsert(scope, "hybrid")
    local = await registry.upsert(scope, "local-only")

    assert hybrid.created_at == original.created_at
    assert local.created_at == original.created_at
    assert hybrid.requires_sanitized_cloud_write is True
    assert hybrid.allows_cloud_recall is True
    assert hybrid.allows_automatic_cloud_write is False
    assert local.is_local_only is True
    assert local.allows_cloud_recall is False
    assert local.allows_automatic_cloud_write is False


@pytest.mark.asyncio
async def test_concurrent_first_use_creates_one_policy(tmp_path) -> None:
    registry = VaultRegistry(str(tmp_path / "vaults.sqlite3"))
    await registry.initialize()
    scope = MemoryScope.account("alice", "default")

    policies = await asyncio.gather(
        *[registry.ensure(scope, allow_create=True) for _ in range(8)]
    )

    assert {policy.created_at for policy in policies} == {policies[0].created_at}
    assert len(await registry.list(account_id="alice")) == 1


@pytest.mark.asyncio
async def test_list_filters_do_not_cross_account_or_principal_boundaries(tmp_path) -> None:
    registry = VaultRegistry(str(tmp_path / "vaults.sqlite3"))
    await registry.initialize()
    await registry.ensure(MemoryScope.account("alice", "default"), allow_create=True)
    await registry.ensure(MemoryScope.account("bob", "default"), allow_create=True)
    await registry.ensure(MemoryScope.service("alice", "system"), allow_create=True)

    account_rows = await registry.list(principal_type="account", account_id="alice")
    service_rows = await registry.list(principal_type="service", account_id="alice")

    assert [row.scope.display_key for row in account_rows] == ["account:alice/default"]
    assert [row.scope.display_key for row in service_rows] == ["service:alice/system"]


def test_storage_mode_aliases_are_normalized_and_invalid_values_fail() -> None:
    assert normalize_storage_mode("local") == "local-only"
    assert normalize_storage_mode("server") == "cloud"
    assert normalize_storage_mode("mixed") == "hybrid"

    with pytest.raises(VaultRegistryError) as captured:
        normalize_storage_mode("unlimited-cloud")
    assert captured.value.code == "vault_storage_mode_invalid"


def test_auto_registration_rules_keep_unverified_named_vaults_admin_controlled() -> None:
    default = MemoryScope.account("alice", "default")
    named = MemoryScope.account("alice", "work")
    service = MemoryScope.service("smoke", "production")

    assert should_auto_register_vault(default, "trusted-openai-user") is True
    assert should_auto_register_vault(named, "trusted-openai-user") is False
    assert should_auto_register_vault(named, "jwt-required") is True
    assert should_auto_register_vault(named, "jwt-preferred") is False
    assert (
        should_auto_register_vault(
            named,
            "jwt-preferred",
            verified_identity=True,
        )
        is True
    )
    assert should_auto_register_vault(named, "legacy-client-asserted") is True
    assert should_auto_register_vault(service, "trusted-openai-user") is True
