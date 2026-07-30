from __future__ import annotations

import asyncio

import pytest

from app.memory_scope import MemoryScope
from app.objects import (
    ObjectRegistry,
    ObjectRegistryError,
    build_object_key,
    safe_display_name,
)
from app.vaults import VaultPolicy


def policy(scope: MemoryScope, storage_mode: str) -> VaultPolicy:
    return VaultPolicy(
        scope=scope,
        storage_mode=storage_mode,  # type: ignore[arg-type]
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def sha(character: str = "a") -> str:
    return character * 64


def test_object_key_uses_scope_and_server_object_id_not_raw_filename() -> None:
    account = MemoryScope.account("alice", "personal")
    service = MemoryScope.service("alice", "personal")
    object_id = "1" * 32

    account_key = build_object_key(account, object_id, "../身份证照片.JPG")
    service_key = build_object_key(service, object_id, "../身份证照片.JPG")

    assert account_key == (
        "accounts/alice/vaults/personal/objects/11111111111111111111111111111111.jpg"
    )
    assert service_key == (
        "services/alice/vaults/personal/objects/11111111111111111111111111111111.jpg"
    )
    assert "身份证" not in account_key
    assert ".." not in account_key
    assert safe_display_name("../身份证\x00照片.JPG") == ".._身份证照片.JPG"


@pytest.mark.asyncio
async def test_local_only_vault_rejects_cloud_object_reservation(tmp_path) -> None:
    registry = ObjectRegistry(str(tmp_path / "objects.sqlite3"), 1024)
    await registry.initialize()
    scope = MemoryScope.account("alice", "personal")

    with pytest.raises(ObjectRegistryError) as captured:
        await registry.reserve(
            scope=scope,
            policy=policy(scope, "local-only"),
            filename="private.pdf",
            content_type="application/pdf",
            size_bytes=10,
            sha256=sha(),
        )

    assert captured.value.code == "object_cloud_storage_disabled"


@pytest.mark.asyncio
async def test_hybrid_vault_requires_sanitized_non_raw_derivative(tmp_path) -> None:
    registry = ObjectRegistry(str(tmp_path / "objects.sqlite3"), 1024)
    await registry.initialize()
    scope = MemoryScope.account("alice", "personal")
    hybrid = policy(scope, "hybrid")

    with pytest.raises(ObjectRegistryError) as unsanitized:
        await registry.reserve(
            scope=scope,
            policy=hybrid,
            filename="summary.txt",
            content_type="text/plain",
            size_bytes=10,
            sha256=sha(),
            object_kind="sanitized-derivative",
        )
    assert unsanitized.value.code == "object_sanitized_cloud_copy_required"

    with pytest.raises(ObjectRegistryError) as raw:
        await registry.reserve(
            scope=scope,
            policy=hybrid,
            filename="raw.txt",
            content_type="text/plain",
            size_bytes=10,
            sha256=sha(),
            object_kind="raw",
            sanitized_for_cloud=True,
        )
    assert raw.value.code == "object_raw_hybrid_upload_forbidden"

    record = await registry.reserve(
        scope=scope,
        policy=hybrid,
        filename="summary.txt",
        content_type="text/plain",
        size_bytes=10,
        sha256=sha(),
        object_kind="sanitized-derivative",
        sanitized_for_cloud=True,
        local_ref_id="device-object-42",
    )
    assert record.storage_mode == "hybrid"
    assert record.sanitized_for_cloud is True
    assert record.local_ref_id == "device-object-42"


@pytest.mark.asyncio
async def test_record_lifecycle_is_scoped_and_hash_checked(tmp_path) -> None:
    registry = ObjectRegistry(str(tmp_path / "objects.sqlite3"), 1024)
    await registry.initialize()
    alice = MemoryScope.account("alice", "personal")
    bob = MemoryScope.account("bob", "personal")

    reserved = await registry.reserve(
        scope=alice,
        policy=policy(alice, "cloud"),
        filename="report.PDF",
        content_type="Application/PDF",
        size_bytes=10,
        sha256=sha("b"),
    )
    assert reserved.state == "reserved"
    assert reserved.content_type == "application/pdf"
    assert reserved.object_key.startswith("accounts/alice/vaults/personal/objects/")
    assert await registry.get(bob, reserved.object_id) is None

    with pytest.raises(ObjectRegistryError) as size_mismatch:
        await registry.complete(
            scope=alice,
            object_id=reserved.object_id,
            actual_size_bytes=11,
            actual_sha256=sha("b"),
        )
    assert size_mismatch.value.code == "object_size_mismatch"

    with pytest.raises(ObjectRegistryError) as hash_mismatch:
        await registry.complete(
            scope=alice,
            object_id=reserved.object_id,
            actual_size_bytes=10,
            actual_sha256=sha("c"),
        )
    assert hash_mismatch.value.code == "object_sha256_mismatch"

    ready = await registry.complete(
        scope=alice,
        object_id=reserved.object_id,
        actual_size_bytes=10,
        actual_sha256=sha("b"),
    )
    assert ready.state == "ready"
    assert ready.ready_at

    deleted = await registry.soft_delete(alice, reserved.object_id)
    assert deleted.state == "deleted"
    assert deleted.deleted_at
    assert await registry.list(alice) == []
    assert [item.object_id for item in await registry.list(alice, include_deleted=True)] == [
        reserved.object_id
    ]


@pytest.mark.asyncio
async def test_policy_scope_mismatch_is_rejected(tmp_path) -> None:
    registry = ObjectRegistry(str(tmp_path / "objects.sqlite3"), 1024)
    await registry.initialize()
    alice = MemoryScope.account("alice", "personal")
    work = MemoryScope.account("alice", "work")

    with pytest.raises(ObjectRegistryError) as captured:
        await registry.reserve(
            scope=work,
            policy=policy(alice, "cloud"),
            filename="report.pdf",
            content_type="application/pdf",
            size_bytes=10,
            sha256=sha(),
        )
    assert captured.value.code == "object_vault_policy_mismatch"
    assert captured.value.status_code == 403


@pytest.mark.asyncio
async def test_parallel_reservations_have_unique_ids_and_keys(tmp_path) -> None:
    registry = ObjectRegistry(str(tmp_path / "objects.sqlite3"), 1024)
    await registry.initialize()
    scope = MemoryScope.account("alice", "personal")
    cloud = policy(scope, "cloud")

    records = await asyncio.gather(
        *[
            registry.reserve(
                scope=scope,
                policy=cloud,
                filename="same.txt",
                content_type="text/plain",
                size_bytes=1,
                sha256=sha(str(index % 10)),
            )
            for index in range(8)
        ]
    )

    assert len({record.object_id for record in records}) == 8
    assert len({record.object_key for record in records}) == 8
    assert len(await registry.list(scope)) == 8


def test_invalid_hash_size_kind_and_content_type_are_rejected(tmp_path) -> None:
    async def run() -> None:
        registry = ObjectRegistry(str(tmp_path / "objects.sqlite3"), 100)
        await registry.initialize()
        scope = MemoryScope.account("alice", "personal")
        cloud = policy(scope, "cloud")

        cases = [
            {"sha256": "not-a-hash"},
            {"size_bytes": 101},
            {"object_kind": "executable-model"},
            {"content_type": ""},
        ]
        for override in cases:
            arguments = {
                "scope": scope,
                "policy": cloud,
                "filename": "file.bin",
                "content_type": "application/octet-stream",
                "size_bytes": 10,
                "sha256": sha(),
                **override,
            }
            with pytest.raises(ObjectRegistryError):
                await registry.reserve(**arguments)

    asyncio.run(run())
