from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .content import safe_id

PrincipalType = Literal["account", "service"]


@dataclass(frozen=True, slots=True)
class MemoryScope:
    """Canonical memory isolation scope.

    `account_id` and `vault_id` are the minimum storage boundary. `principal_type`
    keeps service identities such as smoke tests and migrations outside real user
    namespaces, even when their textual identifiers overlap.
    """

    account_id: str
    vault_id: str = "default"
    principal_type: PrincipalType = "account"
    device_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "account_id", safe_id(self.account_id, "default"))
        object.__setattr__(self, "vault_id", safe_id(self.vault_id, "default"))
        object.__setattr__(self, "device_id", safe_id(self.device_id, "") if self.device_id else "")
        if self.principal_type not in {"account", "service"}:
            raise ValueError("principal_type must be account or service")

    @classmethod
    def account(
        cls,
        account_id: str,
        vault_id: str = "default",
        *,
        device_id: str = "",
    ) -> MemoryScope:
        return cls(
            account_id=account_id,
            vault_id=vault_id,
            principal_type="account",
            device_id=device_id,
        )

    @classmethod
    def service(
        cls,
        service_id: str,
        vault_id: str = "system",
        *,
        device_id: str = "",
    ) -> MemoryScope:
        return cls(
            account_id=service_id,
            vault_id=vault_id,
            principal_type="service",
            device_id=device_id,
        )

    @classmethod
    def from_legacy_user_id(cls, user_id: str, default_user_id: str = "default") -> MemoryScope:
        normalized = safe_id(user_id or default_user_id, safe_id(default_user_id))
        if normalized == "sumeme_smoke":
            return cls.service("sumeme-smoke", "production-smoke")
        return cls.account(normalized)

    @property
    def storage_key(self) -> str:
        prefix = "svc" if self.principal_type == "service" else "acct"
        return f"{prefix}.{self.account_id}.vault.{self.vault_id}"

    @property
    def display_key(self) -> str:
        return f"{self.principal_type}:{self.account_id}/{self.vault_id}"

    @property
    def object_prefix(self) -> str:
        prefix = "services" if self.principal_type == "service" else "accounts"
        return f"{prefix}/{self.account_id}/vaults/{self.vault_id}"


def coerce_scope(
    value: MemoryScope | str,
    *,
    default_user_id: str = "default",
) -> MemoryScope:
    if isinstance(value, MemoryScope):
        return value
    return MemoryScope.from_legacy_user_id(value, default_user_id)
