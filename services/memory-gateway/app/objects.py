from __future__ import annotations

import re
import sqlite3
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import anyio

from .memory_scope import MemoryScope
from .vaults import StorageMode, VaultPolicy

ObjectKind = Literal[
    "raw",
    "sanitized-derivative",
    "thumbnail",
    "transcript",
    "temporary",
]
ObjectState = Literal["reserved", "ready", "deleted"]

_OBJECT_KINDS: frozenset[str] = frozenset(
    {
        "raw",
        "sanitized-derivative",
        "thumbnail",
        "transcript",
        "temporary",
    }
)
_OBJECT_STATES: frozenset[str] = frozenset({"reserved", "ready", "deleted"})
_SAFE_EXTENSION = re.compile(r"^\.[a-z0-9]{1,16}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_OBJECT_ID = re.compile(r"^[0-9a-f]{32}$")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


class ObjectRegistryError(Exception):
    def __init__(self, code: str, status_code: int = 409):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def normalize_object_kind(value: str) -> ObjectKind:
    aliases = {
        "derived": "sanitized-derivative",
        "sanitized": "sanitized-derivative",
        "preview": "thumbnail",
        "temp": "temporary",
    }
    normalized = aliases.get(value.strip().lower(), value.strip().lower())
    if normalized not in _OBJECT_KINDS:
        raise ObjectRegistryError("object_kind_invalid", status_code=400)
    return normalized  # type: ignore[return-value]


def normalize_sha256(value: str) -> str:
    normalized = value.strip().lower()
    if not _SHA256.fullmatch(normalized):
        raise ObjectRegistryError("object_sha256_invalid", status_code=400)
    return normalized


def safe_display_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    normalized = _CONTROL_CHARS.sub("", normalized)
    normalized = normalized.replace("/", "_").replace("\\", "_")
    normalized = " ".join(normalized.split())
    if normalized in {"", ".", ".."}:
        return "file"
    return normalized[:255]


def safe_extension(filename: str) -> str:
    display_name = safe_display_name(filename)
    suffix = Path(display_name).suffix.lower()
    if _SAFE_EXTENSION.fullmatch(suffix):
        return suffix
    return ""


def build_object_key(scope: MemoryScope, object_id: str, filename: str) -> str:
    normalized_id = object_id.strip().lower()
    if not _OBJECT_ID.fullmatch(normalized_id):
        raise ObjectRegistryError("object_id_invalid", status_code=400)
    return f"{scope.object_prefix}/objects/{normalized_id}{safe_extension(filename)}"


def validate_storage_policy_for_object(
    policy: VaultPolicy,
    *,
    object_kind: ObjectKind,
    sanitized_for_cloud: bool,
) -> None:
    if policy.storage_mode == "local-only":
        raise ObjectRegistryError("object_cloud_storage_disabled", status_code=409)
    if policy.storage_mode == "hybrid":
        if not sanitized_for_cloud:
            raise ObjectRegistryError(
                "object_sanitized_cloud_copy_required",
                status_code=409,
            )
        if object_kind == "raw":
            raise ObjectRegistryError("object_raw_hybrid_upload_forbidden", status_code=409)


@dataclass(frozen=True, slots=True)
class ObjectRecord:
    object_id: str
    scope: MemoryScope
    object_key: str
    storage_mode: StorageMode
    object_kind: ObjectKind
    state: ObjectState
    original_name: str
    content_type: str
    size_bytes: int
    sha256: str
    sanitized_for_cloud: bool
    local_ref_id: str
    created_at: str
    updated_at: str
    ready_at: str
    deleted_at: str

    def as_dict(self) -> dict[str, str | int | bool]:
        return {
            "object_id": self.object_id,
            "principal_type": self.scope.principal_type,
            "account_id": self.scope.account_id,
            "vault_id": self.scope.vault_id,
            "object_key": self.object_key,
            "storage_mode": self.storage_mode,
            "object_kind": self.object_kind,
            "state": self.state,
            "original_name": self.original_name,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "sanitized_for_cloud": self.sanitized_for_cloud,
            "local_ref_id": self.local_ref_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "ready_at": self.ready_at,
            "deleted_at": self.deleted_at,
        }


class ObjectRegistry:
    def __init__(self, path: str, max_size_bytes: int):
        self.path = Path(path)
        self.max_size_bytes = max_size_bytes
        if self.max_size_bytes < 1:
            raise ValueError("max_size_bytes must be positive")

    async def initialize(self) -> None:
        await anyio.to_thread.run_sync(self._initialize_sync)

    async def reserve(
        self,
        *,
        scope: MemoryScope,
        policy: VaultPolicy,
        filename: str,
        content_type: str,
        size_bytes: int,
        sha256: str,
        object_kind: str = "raw",
        sanitized_for_cloud: bool = False,
        local_ref_id: str = "",
    ) -> ObjectRecord:
        kind = normalize_object_kind(object_kind)
        validate_storage_policy_for_object(
            policy,
            object_kind=kind,
            sanitized_for_cloud=sanitized_for_cloud,
        )
        if policy.scope.storage_key != scope.storage_key:
            raise ObjectRegistryError("object_vault_policy_mismatch", status_code=403)
        if size_bytes < 0 or size_bytes > self.max_size_bytes:
            raise ObjectRegistryError("object_size_invalid", status_code=400)
        digest = normalize_sha256(sha256)
        object_id = uuid.uuid4().hex
        object_key = build_object_key(scope, object_id, filename)
        return await anyio.to_thread.run_sync(
            self._reserve_sync,
            object_id,
            scope,
            object_key,
            policy.storage_mode,
            kind,
            safe_display_name(filename),
            self._normalize_content_type(content_type),
            size_bytes,
            digest,
            sanitized_for_cloud,
            self._normalize_local_ref(local_ref_id),
        )

    async def get(self, scope: MemoryScope, object_id: str) -> ObjectRecord | None:
        normalized_id = self._normalize_object_id(object_id)
        return await anyio.to_thread.run_sync(self._get_sync, scope, normalized_id)

    async def complete(
        self,
        *,
        scope: MemoryScope,
        object_id: str,
        actual_size_bytes: int,
        actual_sha256: str,
    ) -> ObjectRecord:
        normalized_id = self._normalize_object_id(object_id)
        digest = normalize_sha256(actual_sha256)
        return await anyio.to_thread.run_sync(
            self._complete_sync,
            scope,
            normalized_id,
            actual_size_bytes,
            digest,
        )

    async def soft_delete(self, scope: MemoryScope, object_id: str) -> ObjectRecord:
        normalized_id = self._normalize_object_id(object_id)
        return await anyio.to_thread.run_sync(
            self._soft_delete_sync,
            scope,
            normalized_id,
        )

    async def list(
        self,
        scope: MemoryScope,
        *,
        include_deleted: bool = False,
        limit: int = 100,
    ) -> list[ObjectRecord]:
        bounded_limit = max(1, min(limit, 500))
        return await anyio.to_thread.run_sync(
            self._list_sync,
            scope,
            include_deleted,
            bounded_limit,
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize_sync(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS objects (
                    object_id TEXT PRIMARY KEY,
                    principal_type TEXT NOT NULL
                        CHECK (principal_type IN ('account', 'service')),
                    account_id TEXT NOT NULL,
                    vault_id TEXT NOT NULL,
                    object_key TEXT NOT NULL UNIQUE,
                    storage_mode TEXT NOT NULL
                        CHECK (storage_mode IN ('local-only', 'cloud', 'hybrid')),
                    object_kind TEXT NOT NULL
                        CHECK (object_kind IN (
                            'raw', 'sanitized-derivative', 'thumbnail',
                            'transcript', 'temporary'
                        )),
                    state TEXT NOT NULL
                        CHECK (state IN ('reserved', 'ready', 'deleted')),
                    original_name TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
                    sha256 TEXT NOT NULL,
                    sanitized_for_cloud INTEGER NOT NULL CHECK (
                        sanitized_for_cloud IN (0, 1)
                    ),
                    local_ref_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    ready_at TEXT NOT NULL,
                    deleted_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS objects_scope_state_idx
                ON objects (
                    principal_type, account_id, vault_id, state, created_at DESC
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS objects_scope_hash_idx
                ON objects (
                    principal_type, account_id, vault_id, sha256
                )
                """
            )

    def _reserve_sync(
        self,
        object_id: str,
        scope: MemoryScope,
        object_key: str,
        storage_mode: StorageMode,
        object_kind: ObjectKind,
        original_name: str,
        content_type: str,
        size_bytes: int,
        sha256: str,
        sanitized_for_cloud: bool,
        local_ref_id: str,
    ) -> ObjectRecord:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO objects (
                    object_id, principal_type, account_id, vault_id, object_key,
                    storage_mode, object_kind, state, original_name, content_type,
                    size_bytes, sha256, sanitized_for_cloud, local_ref_id,
                    created_at, updated_at, ready_at, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'reserved', ?, ?, ?, ?, ?, ?, ?, ?, '', '')
                """,
                (
                    object_id,
                    scope.principal_type,
                    scope.account_id,
                    scope.vault_id,
                    object_key,
                    storage_mode,
                    object_kind,
                    original_name,
                    content_type,
                    size_bytes,
                    sha256,
                    int(sanitized_for_cloud),
                    local_ref_id,
                    now,
                    now,
                ),
            )
        record = self._get_sync(scope, object_id)
        if record is None:
            raise ObjectRegistryError("object_registry_write_failed", status_code=500)
        return record

    def _get_sync(self, scope: MemoryScope, object_id: str) -> ObjectRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM objects
                WHERE object_id = ? AND principal_type = ?
                  AND account_id = ? AND vault_id = ?
                """,
                (
                    object_id,
                    scope.principal_type,
                    scope.account_id,
                    scope.vault_id,
                ),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def _complete_sync(
        self,
        scope: MemoryScope,
        object_id: str,
        actual_size_bytes: int,
        actual_sha256: str,
    ) -> ObjectRecord:
        current = self._get_sync(scope, object_id)
        if current is None:
            raise ObjectRegistryError("object_not_found", status_code=404)
        if current.state == "deleted":
            raise ObjectRegistryError("object_deleted", status_code=409)
        if actual_size_bytes != current.size_bytes:
            raise ObjectRegistryError("object_size_mismatch", status_code=409)
        if actual_sha256 != current.sha256:
            raise ObjectRegistryError("object_sha256_mismatch", status_code=409)

        now = datetime.now(UTC).isoformat()
        ready_at = current.ready_at or now
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE objects
                SET state = 'ready', updated_at = ?, ready_at = ?
                WHERE object_id = ? AND principal_type = ?
                  AND account_id = ? AND vault_id = ?
                """,
                (
                    now,
                    ready_at,
                    object_id,
                    scope.principal_type,
                    scope.account_id,
                    scope.vault_id,
                ),
            )
        result = self._get_sync(scope, object_id)
        if result is None:
            raise ObjectRegistryError("object_registry_write_failed", status_code=500)
        return result

    def _soft_delete_sync(self, scope: MemoryScope, object_id: str) -> ObjectRecord:
        current = self._get_sync(scope, object_id)
        if current is None:
            raise ObjectRegistryError("object_not_found", status_code=404)
        if current.state == "deleted":
            return current

        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE objects
                SET state = 'deleted', updated_at = ?, deleted_at = ?
                WHERE object_id = ? AND principal_type = ?
                  AND account_id = ? AND vault_id = ?
                """,
                (
                    now,
                    now,
                    object_id,
                    scope.principal_type,
                    scope.account_id,
                    scope.vault_id,
                ),
            )
        result = self._get_sync(scope, object_id)
        if result is None:
            raise ObjectRegistryError("object_registry_write_failed", status_code=500)
        return result

    def _list_sync(
        self,
        scope: MemoryScope,
        include_deleted: bool,
        limit: int,
    ) -> list[ObjectRecord]:
        state_clause = "" if include_deleted else "AND state != 'deleted'"
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM objects
                WHERE principal_type = ? AND account_id = ? AND vault_id = ?
                {state_clause}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (
                    scope.principal_type,
                    scope.account_id,
                    scope.vault_id,
                    limit,
                ),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    @staticmethod
    def _normalize_object_id(value: str) -> str:
        normalized = value.strip().lower()
        if not _OBJECT_ID.fullmatch(normalized):
            raise ObjectRegistryError("object_id_invalid", status_code=400)
        return normalized

    @staticmethod
    def _normalize_content_type(value: str) -> str:
        normalized = value.strip().lower()
        if not normalized or len(normalized) > 255 or _CONTROL_CHARS.search(normalized):
            raise ObjectRegistryError("object_content_type_invalid", status_code=400)
        return normalized

    @staticmethod
    def _normalize_local_ref(value: str) -> str:
        normalized = _CONTROL_CHARS.sub("", value.strip())
        if len(normalized) > 512:
            raise ObjectRegistryError("object_local_ref_invalid", status_code=400)
        return normalized

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ObjectRecord:
        state = str(row["state"])
        kind = str(row["object_kind"])
        storage_mode = str(row["storage_mode"])
        if state not in _OBJECT_STATES or kind not in _OBJECT_KINDS:
            raise ObjectRegistryError("object_registry_corrupt", status_code=500)
        if storage_mode not in {"local-only", "cloud", "hybrid"}:
            raise ObjectRegistryError("object_registry_corrupt", status_code=500)
        scope = MemoryScope(
            principal_type=str(row["principal_type"]),  # type: ignore[arg-type]
            account_id=str(row["account_id"]),
            vault_id=str(row["vault_id"]),
        )
        return ObjectRecord(
            object_id=str(row["object_id"]),
            scope=scope,
            object_key=str(row["object_key"]),
            storage_mode=storage_mode,  # type: ignore[arg-type]
            object_kind=kind,  # type: ignore[arg-type]
            state=state,  # type: ignore[arg-type]
            original_name=str(row["original_name"]),
            content_type=str(row["content_type"]),
            size_bytes=int(row["size_bytes"]),
            sha256=str(row["sha256"]),
            sanitized_for_cloud=bool(row["sanitized_for_cloud"]),
            local_ref_id=str(row["local_ref_id"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            ready_at=str(row["ready_at"]),
            deleted_at=str(row["deleted_at"]),
        )
