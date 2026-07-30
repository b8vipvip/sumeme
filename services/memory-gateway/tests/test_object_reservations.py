from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.memory_scope import MemoryScope
from app.object_config import ObjectAccessSettings
from app.object_reservations import ObjectReservationError, ObjectReservationManager
from app.object_store import VerifiedObject
from app.objects import ObjectRecord, ObjectRegistry
from app.vaults import VaultPolicy


def cloud_policy(scope: MemoryScope) -> VaultPolicy:
    return VaultPolicy(
        scope=scope,
        storage_mode="cloud",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


class FakeStore:
    def __init__(self):
        self.deleted: list[str] = []
        self.verified: list[str] = []

    async def verify_upload(self, record: ObjectRecord) -> VerifiedObject:
        self.verified.append(record.object_id)
        return VerifiedObject(
            size_bytes=record.size_bytes,
            sha256=record.sha256,
        )

    async def delete(self, record: ObjectRecord) -> None:
        self.deleted.append(record.object_id)


async def reserve(
    registry: ObjectRegistry,
    scope: MemoryScope,
    *,
    suffix: str = "a",
) -> ObjectRecord:
    return await registry.reserve(
        scope=scope,
        policy=cloud_policy(scope),
        filename=f"{suffix}.txt",
        content_type="text/plain",
        size_bytes=1,
        sha256=suffix * 64,
    )


def backdate(path: str, object_id: str, *, hours: int) -> None:
    value = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE objects SET created_at = ?, updated_at = ? WHERE object_id = ?",
            (value, value, object_id),
        )


def manager(
    registry: ObjectRegistry,
    store: FakeStore,
    path: str,
    *,
    reservation_ttl_seconds: int = 3600,
) -> ObjectReservationManager:
    return ObjectReservationManager(
        registry=registry,
        store=store,  # type: ignore[arg-type]
        registry_path=path,
        reservation_ttl_seconds=reservation_ttl_seconds,
        cleanup_interval_seconds=300,
        cleanup_batch_size=100,
        operation_lease_seconds=3600,
    )


@pytest.mark.asyncio
async def test_cleanup_deletes_only_expired_reserved_objects(tmp_path) -> None:
    path = str(tmp_path / "objects.sqlite3")
    registry = ObjectRegistry(path, 1024)
    await registry.initialize()
    store = FakeStore()
    reservations = manager(registry, store, path)
    await reservations.initialize()
    scope = MemoryScope.account("alice", "personal")

    expired = await reserve(registry, scope, suffix="a")
    fresh = await reserve(registry, scope, suffix="b")
    ready = await reserve(registry, scope, suffix="c")
    backdate(path, expired.object_id, hours=2)
    backdate(path, ready.object_id, hours=2)
    await registry.complete(
        scope=scope,
        object_id=ready.object_id,
        actual_size_bytes=ready.size_bytes,
        actual_sha256=ready.sha256,
    )

    result = await reservations.cleanup_once()

    assert result.candidates == 1
    assert result.deleted == 1
    assert result.skipped == 0
    assert result.failed == 0
    assert store.deleted == [expired.object_id]
    assert (await registry.get(scope, expired.object_id)).state == "deleted"  # type: ignore[union-attr]
    assert (await registry.get(scope, fresh.object_id)).state == "reserved"  # type: ignore[union-attr]
    assert (await registry.get(scope, ready.object_id)).state == "ready"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_cleanup_skips_object_with_active_operation_lease(tmp_path) -> None:
    path = str(tmp_path / "objects.sqlite3")
    registry = ObjectRegistry(path, 1024)
    await registry.initialize()
    store = FakeStore()
    reservations = manager(registry, store, path)
    await reservations.initialize()
    scope = MemoryScope.account("alice", "personal")
    item = await reserve(registry, scope)
    backdate(path, item.object_id, hours=2)

    lease_id = reservations._acquire_sync(item.object_id, "complete")
    assert lease_id is not None
    try:
        result = await reservations.cleanup_once()
    finally:
        reservations._release_sync(item.object_id, lease_id)

    assert result.candidates == 1
    assert result.deleted == 0
    assert result.skipped == 1
    assert store.deleted == []
    assert (await registry.get(scope, item.object_id)).state == "reserved"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_completion_and_delete_share_operation_lease(tmp_path) -> None:
    path = str(tmp_path / "objects.sqlite3")
    registry = ObjectRegistry(path, 1024)
    await registry.initialize()
    store = FakeStore()
    reservations = manager(registry, store, path)
    await reservations.initialize()
    scope = MemoryScope.account("alice", "personal")
    item = await reserve(registry, scope)

    lease_id = reservations._acquire_sync(item.object_id, "expire")
    assert lease_id is not None
    try:
        with pytest.raises(ObjectReservationError) as completion:
            await reservations.complete(item)
        with pytest.raises(ObjectReservationError) as deletion:
            await reservations.delete(item)
    finally:
        reservations._release_sync(item.object_id, lease_id)

    assert completion.value.code == "object_operation_in_progress"
    assert deletion.value.code == "object_operation_in_progress"
    assert store.verified == []
    assert store.deleted == []


@pytest.mark.asyncio
async def test_complete_then_delete_transitions_under_manager(tmp_path) -> None:
    path = str(tmp_path / "objects.sqlite3")
    registry = ObjectRegistry(path, 1024)
    await registry.initialize()
    store = FakeStore()
    reservations = manager(registry, store, path)
    await reservations.initialize()
    scope = MemoryScope.account("alice", "personal")
    item = await reserve(registry, scope)

    ready = await reservations.complete(item)
    deleted = await reservations.delete(ready)

    assert ready.state == "ready"
    assert deleted.state == "deleted"
    assert store.verified == [item.object_id]
    assert store.deleted == [item.object_id]


def test_expired_lease_owner_cannot_release_replacement_lease(tmp_path) -> None:
    path = str(tmp_path / "objects.sqlite3")
    registry = ObjectRegistry(path, 1024)
    import asyncio

    asyncio.run(registry.initialize())
    store = FakeStore()
    reservations = manager(registry, store, path)
    asyncio.run(reservations.initialize())
    object_id = "1" * 32

    first = reservations._acquire_sync(object_id, "complete")
    assert first is not None
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE object_operation_leases SET expires_at = ? WHERE object_id = ?",
            ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), object_id),
        )
    second = reservations._acquire_sync(object_id, "delete")
    assert second is not None and second != first

    reservations._release_sync(object_id, first)

    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT lease_id FROM object_operation_leases WHERE object_id = ?",
            (object_id,),
        ).fetchone()
    assert row is not None
    assert row[0] == second


def test_reservation_ttl_cannot_expire_before_signed_url() -> None:
    with pytest.raises(ValidationError):
        ObjectAccessSettings(
            object_presign_ttl_seconds=900,
            object_reservation_ttl_seconds=600,
        )
