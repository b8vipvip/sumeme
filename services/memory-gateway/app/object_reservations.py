from __future__ import annotations

import asyncio
import logging
import sqlite3
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import anyio

from .object_store import ObjectStoreError, S3ObjectStore
from .objects import ObjectRecord, ObjectRegistry, ObjectRegistryError

logger = logging.getLogger(__name__)


class ObjectReservationError(Exception):
    def __init__(self, code: str, status_code: int = 409):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class CleanupResult:
    candidates: int
    deleted: int
    skipped: int
    failed: int


_EXPECTED_CLEANUP_ERRORS = (
    ObjectReservationError,
    ObjectStoreError,
    ObjectRegistryError,
    sqlite3.Error,
    OSError,
    ValueError,
)


class ObjectReservationManager:
    """Serialize completion/deletion and clean abandoned reservations safely."""

    def __init__(
        self,
        *,
        registry: ObjectRegistry,
        store: S3ObjectStore,
        registry_path: str,
        reservation_ttl_seconds: int,
        cleanup_interval_seconds: int,
        cleanup_batch_size: int,
        operation_lease_seconds: int,
    ):
        self.registry = registry
        self.store = store
        self.path = Path(registry_path)
        self.reservation_ttl_seconds = reservation_ttl_seconds
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self.cleanup_batch_size = cleanup_batch_size
        self.operation_lease_seconds = operation_lease_seconds

    async def initialize(self) -> None:
        await anyio.to_thread.run_sync(self._initialize_sync)

    async def complete(self, record: ObjectRecord) -> ObjectRecord:
        async with self._lease(record.object_id, "complete"):
            current = await self.registry.get(record.scope, record.object_id)
            if current is None:
                raise ObjectReservationError("object_not_found", status_code=404)
            if current.state != "reserved":
                raise ObjectReservationError("object_upload_not_reserved", status_code=409)
            verified = await self.store.verify_upload(current)
            return await self.registry.complete(
                scope=current.scope,
                object_id=current.object_id,
                actual_size_bytes=verified.size_bytes,
                actual_sha256=verified.sha256,
            )

    async def delete(self, record: ObjectRecord) -> ObjectRecord:
        async with self._lease(record.object_id, "delete"):
            current = await self.registry.get(record.scope, record.object_id)
            if current is None:
                raise ObjectReservationError("object_not_found", status_code=404)
            if current.state == "deleted":
                return current
            await self.store.delete(current)
            return await self.registry.soft_delete(current.scope, current.object_id)

    async def cleanup_once(self) -> CleanupResult:
        cutoff = datetime.now(UTC) - timedelta(seconds=self.reservation_ttl_seconds)
        candidates = await anyio.to_thread.run_sync(
            self._expired_sync,
            cutoff.isoformat(),
            self.cleanup_batch_size,
        )
        deleted = 0
        skipped = 0
        failed = 0
        for candidate in candidates:
            try:
                async with self._lease(candidate.object_id, "expire"):
                    current = await self.registry.get(
                        candidate.scope,
                        candidate.object_id,
                    )
                    if current is None or current.state != "reserved":
                        skipped += 1
                        continue
                    created_at = self._parse_timestamp(current.created_at)
                    if created_at is None or created_at > cutoff:
                        skipped += 1
                        continue
                    await self.store.delete(current)
                    await self.registry.soft_delete(current.scope, current.object_id)
                    deleted += 1
            except ObjectReservationError as exc:
                if exc.code == "object_operation_in_progress":
                    skipped += 1
                else:
                    failed += 1
                    self._log_cleanup_failure(candidate.object_id, exc)
            except (
                ObjectStoreError,
                ObjectRegistryError,
                sqlite3.Error,
                OSError,
                ValueError,
            ) as exc:
                failed += 1
                self._log_cleanup_failure(candidate.object_id, exc)
        return CleanupResult(
            candidates=len(candidates),
            deleted=deleted,
            skipped=skipped,
            failed=failed,
        )

    async def run_forever(self) -> None:
        while True:
            try:
                result = await self.cleanup_once()
                if result.candidates:
                    logger.info(
                        "Reservation cleanup candidates=%s deleted=%s skipped=%s failed=%s",
                        result.candidates,
                        result.deleted,
                        result.skipped,
                        result.failed,
                    )
            except asyncio.CancelledError:
                raise
            except _EXPECTED_CLEANUP_ERRORS as exc:
                logger.warning(
                    "Reservation cleanup cycle failed code=%s",
                    getattr(exc, "code", type(exc).__name__),
                )
            await asyncio.sleep(self.cleanup_interval_seconds)

    @staticmethod
    def _log_cleanup_failure(object_id: str, exc: Exception) -> None:
        logger.warning(
            "Reservation cleanup failed object_id=%s code=%s",
            object_id,
            getattr(exc, "code", type(exc).__name__),
        )

    @asynccontextmanager
    async def _lease(self, object_id: str, operation: str) -> AsyncIterator[None]:
        lease_id = await anyio.to_thread.run_sync(
            self._acquire_sync,
            object_id,
            operation,
        )
        if lease_id is None:
            raise ObjectReservationError("object_operation_in_progress", status_code=409)
        try:
            yield
        finally:
            await anyio.to_thread.run_sync(
                self._release_sync,
                object_id,
                lease_id,
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize_sync(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS object_operation_leases (
                    object_id TEXT PRIMARY KEY,
                    lease_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    acquired_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )
            columns = {
                str(row["name"])
                for row in connection.execute(
                    "PRAGMA table_info(object_operation_leases)"
                ).fetchall()
            }
            if "lease_id" not in columns:
                connection.execute("DROP TABLE object_operation_leases")
                connection.execute(
                    """
                    CREATE TABLE object_operation_leases (
                        object_id TEXT PRIMARY KEY,
                        lease_id TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        acquired_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL
                    )
                    """
                )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS object_operation_leases_expiry_idx
                ON object_operation_leases (expires_at)
                """
            )

    def _acquire_sync(self, object_id: str, operation: str) -> str | None:
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=self.operation_lease_seconds)
        lease_id = uuid.uuid4().hex
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM object_operation_leases WHERE expires_at <= ?",
                (now.isoformat(),),
            )
            try:
                connection.execute(
                    """
                    INSERT INTO object_operation_leases (
                        object_id, lease_id, operation, acquired_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        object_id,
                        lease_id,
                        operation,
                        now.isoformat(),
                        expires_at.isoformat(),
                    ),
                )
            except sqlite3.IntegrityError:
                connection.rollback()
                return None
            connection.commit()
            return lease_id

    def _release_sync(self, object_id: str, lease_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM object_operation_leases
                WHERE object_id = ? AND lease_id = ?
                """,
                (object_id, lease_id),
            )

    def _expired_sync(self, cutoff: str, limit: int) -> list[ObjectRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM objects
                WHERE state = 'reserved' AND created_at <= ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (cutoff, limit),
            ).fetchall()
        return [ObjectRegistry._row_to_record(row) for row in rows]

    @staticmethod
    def _parse_timestamp(value: str) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
