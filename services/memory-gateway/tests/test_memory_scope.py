from __future__ import annotations

import pytest

from app.memory_scope import MemoryScope, coerce_scope


def test_account_scope_is_normalized() -> None:
    scope = MemoryScope.account(" Account A ", "Work / Private", device_id="phone 1")

    assert scope.account_id == "Account_A"
    assert scope.vault_id == "Work_Private"
    assert scope.device_id == "phone_1"
    assert scope.storage_key == "acct.Account_A.vault.Work_Private"
    assert scope.object_prefix == "accounts/Account_A/vaults/Work_Private"


def test_account_vault_and_principal_are_all_part_of_the_key() -> None:
    scopes = {
        MemoryScope.account("account-a", "personal").storage_key,
        MemoryScope.account("account-a", "work").storage_key,
        MemoryScope.account("account-b", "personal").storage_key,
        MemoryScope.service("account-a", "personal").storage_key,
    }

    assert len(scopes) == 4


def test_legacy_smoke_identity_is_always_a_service_scope() -> None:
    scope = MemoryScope.from_legacy_user_id("__sumeme_smoke__")

    assert scope.principal_type == "service"
    assert scope.account_id == "sumeme-smoke"
    assert scope.vault_id == "production-smoke"
    assert scope.storage_key == "svc.sumeme-smoke.vault.production-smoke"


def test_regular_legacy_user_maps_to_default_vault() -> None:
    scope = coerce_scope("user-a")

    assert scope == MemoryScope.account("user-a", "default")


def test_invalid_principal_type_is_rejected() -> None:
    with pytest.raises(ValueError, match="principal_type"):
        MemoryScope(account_id="a", principal_type="admin")  # type: ignore[arg-type]
