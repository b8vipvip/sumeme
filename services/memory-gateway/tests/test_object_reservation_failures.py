from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from app.memory_scope import MemoryScope
from app.object_reservations import ObjectReservationManager
from app.object_store import ObjectStoreError, VerifiedObject
from app.objects import ObjectRecord, ObjectRegistry
from app.vaults import VaultPolicy


class FailingDeleteStore:
    async def verify_upload(self, record: ObjectRecord) -> VerifiedObject:
        return VerifiedObject(
            size_bytes=record.size_bytes,
            sha256=record.sha256,
        )

    async def delete(self, _record: ObjectRecord) -> None:
        raise ObjectStoreError("object_delete_failed", status_code=503)


@pytest.mark.asyncio
async def test_failed_expired_blob_delete_keeps_reservation_retryable(tmp_path) -> None:
    path = str(tmp_path / "objects.sqlite3")
    registry = ObjectRegistry(path, 1024)
    await registry.initialize()
    scope = MemoryScope.account("alice", "personal")
    policy = VaultPolicy(
        scope=scope,
        storage_mode="cloud",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    item = await registry.reserve(
        scope=scope,
        policy=policy,
        filename="retry.txt",
        content_type="text/plain",
        size_bytes=1,
        sha256="a" * 64,
    )
    old = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE objects SET created_at = ?, updated_at = ? WHERE object_id = ?",
            (old, old, item.object_id),
        )

    reservations = ObjectReservationManager(
        registry=registry,
        store=FailingDeleteStore(),  # type: ignore[arg-type]
        registry_path=path,
        reservation_ttl_seconds=3600,
        cleanup_interval_seconds=300,
        cleanup_batch_size=100,
        operation_lease_seconds=7200,
    )
    await reservations.initialize()

    result = await reservations.cleanup_once()

    assert result.candidates == 1
    assert result.deleted == 0
    assert result.failed == 1
    current = await registry.get(scope, item.object_id)
    assert current is not None
    assert current.state == "reserved"
