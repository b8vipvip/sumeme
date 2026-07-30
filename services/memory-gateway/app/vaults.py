from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import anyio

from .memory_scope import MemoryScope

StorageMode = Literal["local-only", "cloud", "hybrid"]
_STORAGE_MODES: frozenset[str] = frozenset({"local-only", "cloud", "hybrid"})


class VaultRegistryError(Exception):
    def __init__(self, code: str, status_code: int = 409):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def normalize_storage_mode(value: str) -> StorageMode:
    aliases = {
        "local": "local-only",
        "local_only": "local-only",
        "localonly": "local-only",
        "server": "cloud",
        "remote": "cloud",
        "mixed": "hybrid",
    }
    normalized = aliases.get(value.strip().lower(), value.strip().lower())
    if normalized not in _STORAGE_MODES:
        raise VaultRegistryError("vault_storage_mode_invalid", status_code=400)
    return normalized  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class VaultPolicy:
    scope: MemoryScope
    storage_mode: StorageMode
    created_at: str
    updated_at: str

    @property
    def allows_cloud_recall(self) -> bool:
        return self.storage_mode in {"cloud", "hybrid"}

    @property
    def allows_automatic_cloud_write(self) -> bool:
        return self.storage_mode == "cloud"

    @property
    def requires_sanitized_cloud_write(self) -> bool:
        return self.storage_mode == "hybrid"

    @property
    def is_local_only(self) -> bool:
        return self.storage_mode == "local-only"

    def as_dict(self) -> dict[str, str | bool]:
        return {
            "principal_type": self.scope.principal_type,
            "account_id": self.scope.account_id,
            "vault_id": self.scope.vault_id,
            "storage_mode": self.storage_mode,
            "cloud_recall": self.allows_cloud_recall,
            "automatic_cloud_write": self.allows_automatic_cloud_write,
            "sanitized_cloud_write_required": self.requires_sanitized_cloud_write,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def should_auto_register_vault(
    scope: MemoryScope,
    identity_mode: str,
    *,
    verified_identity: bool = False,
) -> bool:
    """Return whether an authenticated scope may create its registry row.

    `jwt-preferred` can also take an unverified legacy fallback, so the caller must
    explicitly say when a valid JWT was present. This prevents transitional mode
    from silently turning client-asserted named vaults into registered vaults.
    """

    if scope.principal_type == "service":
        return True
    if identity_mode == "legacy-client-asserted":
        return True
    if identity_mode == "jwt-required":
        return True
    if identity_mode == "jwt-preferred":
        return verified_identity
    if identity_mode == "trusted-openai-user":
        return scope.vault_id == "default"
    return False


class VaultRegistry:
    def __init__(self, path: str, default_storage_mode: str = "cloud"):
        self.path = Path(path)
        self.default_storage_mode = normalize_storage_mode(default_storage_mode)

    async def initialize(self) -> None:
        await anyio.to_thread.run_sync(self._initialize_sync)

    async def get(self, scope: MemoryScope) -> VaultPolicy | None:
        return await anyio.to_thread.run_sync(self._get_sync, scope)

    async def ensure(
        self,
        scope: MemoryScope,
        *,
        allow_create: bool,
        storage_mode: str | None = None,
    ) -> VaultPolicy:
        mode = normalize_storage_mode(storage_mode or self.default_storage_mode)
        return await anyio.to_thread.run_sync(
            self._ensure_sync,
            scope,
            allow_create,
            mode,
        )

    async def upsert(self, scope: MemoryScope, storage_mode: str) -> VaultPolicy:
        mode = normalize_storage_mode(storage_mode)
        return await anyio.to_thread.run_sync(self._upsert_sync, scope, mode)

    async def list(
        self,
        *,
        principal_type: str | None = None,
        account_id: str | None = None,
    ) -> list[VaultPolicy]:
        if principal_type is not None and principal_type not in {"account", "service"}:
            raise VaultRegistryError("vault_principal_type_invalid", status_code=400)
        return await anyio.to_thread.run_sync(
            self._list_sync,
            principal_type,
            account_id,
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_sync(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS vaults (
                    principal_type TEXT NOT NULL
                        CHECK (principal_type IN ('account', 'service')),
                    account_id TEXT NOT NULL,
                    vault_id TEXT NOT NULL,
                    storage_mode TEXT NOT NULL
                        CHECK (storage_mode IN ('local-only', 'cloud', 'hybrid')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (principal_type, account_id, vault_id)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS vaults_account_idx
                ON vaults (principal_type, account_id, updated_at DESC)
                """
            )

    def _get_sync(self, scope: MemoryScope) -> VaultPolicy | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT principal_type, account_id, vault_id, storage_mode,
                       created_at, updated_at
                FROM vaults
                WHERE principal_type = ? AND account_id = ? AND vault_id = ?
                """,
                (scope.principal_type, scope.account_id, scope.vault_id),
            ).fetchone()
        return self._row_to_policy(row) if row is not None else None

    def _ensure_sync(
        self,
        scope: MemoryScope,
        allow_create: bool,
        storage_mode: StorageMode,
    ) -> VaultPolicy:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT principal_type, account_id, vault_id, storage_mode,
                       created_at, updated_at
                FROM vaults
                WHERE principal_type = ? AND account_id = ? AND vault_id = ?
                """,
                (scope.principal_type, scope.account_id, scope.vault_id),
            ).fetchone()
            if row is not None:
                return self._row_to_policy(row)
            if not allow_create:
                raise VaultRegistryError("vault_not_registered", status_code=403)

            connection.execute(
                """
                INSERT OR IGNORE INTO vaults (
                    principal_type, account_id, vault_id, storage_mode,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    scope.principal_type,
                    scope.account_id,
                    scope.vault_id,
                    storage_mode,
                    now,
                    now,
                ),
            )
            row = connection.execute(
                """
                SELECT principal_type, account_id, vault_id, storage_mode,
                       created_at, updated_at
                FROM vaults
                WHERE principal_type = ? AND account_id = ? AND vault_id = ?
                """,
                (scope.principal_type, scope.account_id, scope.vault_id),
            ).fetchone()
        if row is None:
            raise VaultRegistryError("vault_registry_write_failed", status_code=500)
        return self._row_to_policy(row)

    def _upsert_sync(self, scope: MemoryScope, storage_mode: StorageMode) -> VaultPolicy:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO vaults (
                    principal_type, account_id, vault_id, storage_mode,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(principal_type, account_id, vault_id) DO UPDATE SET
                    storage_mode = excluded.storage_mode,
                    updated_at = excluded.updated_at
                """,
                (
                    scope.principal_type,
                    scope.account_id,
                    scope.vault_id,
                    storage_mode,
                    now,
                    now,
                ),
            )
            row = connection.execute(
                """
                SELECT principal_type, account_id, vault_id, storage_mode,
                       created_at, updated_at
                FROM vaults
                WHERE principal_type = ? AND account_id = ? AND vault_id = ?
                """,
                (scope.principal_type, scope.account_id, scope.vault_id),
            ).fetchone()
        if row is None:
            raise VaultRegistryError("vault_registry_write_failed", status_code=500)
        return self._row_to_policy(row)

    def _list_sync(
        self,
        principal_type: str | None,
        account_id: str | None,
    ) -> list[VaultPolicy]:
        clauses: list[str] = []
        parameters: list[str] = []
        if principal_type is not None:
            clauses.append("principal_type = ?")
            parameters.append(principal_type)
        if account_id is not None:
            clauses.append("account_id = ?")
            parameters.append(account_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT principal_type, account_id, vault_id, storage_mode,
                       created_at, updated_at
                FROM vaults
                {where}
                ORDER BY principal_type, account_id, vault_id
                """,
                parameters,
            ).fetchall()
        return [self._row_to_policy(row) for row in rows]

    @staticmethod
    def _row_to_policy(row: sqlite3.Row) -> VaultPolicy:
        principal_type = str(row["principal_type"])
        scope = MemoryScope(
            principal_type=principal_type,  # type: ignore[arg-type]
            account_id=str(row["account_id"]),
            vault_id=str(row["vault_id"]),
        )
        return VaultPolicy(
            scope=scope,
            storage_mode=normalize_storage_mode(str(row["storage_mode"])),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
