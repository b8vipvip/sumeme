from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.memory_scope import MemoryScope
from app.object_api import build_object_router
from app.object_config import ObjectAccessSettings
from app.object_store import PresignedRequest, VerifiedObject
from app.objects import ObjectRecord, ObjectRegistry
from app.vaults import VaultPolicy


def core_settings() -> Settings:
    return Settings(
        openai_relay_base_url="https://relay.example.test/v1",
        openai_relay_api_key=SecretStr("relay"),
        gateway_api_key=SecretStr("gateway"),
        gateway_admin_token=SecretStr("admin"),
        identity_mode="trusted-openai-user",
        identity_trusted_upstream_issuer="lobehub-test",
        letta_required=False,
    )


def object_settings() -> ObjectAccessSettings:
    return ObjectAccessSettings(
        object_api_enabled=True,
        rustfs_internal_endpoint="http://rustfs:9000",
        rustfs_public_endpoint="https://s3.example.test",
        rustfs_access_key="access",
        rustfs_secret_key="secret",
        rustfs_private_bucket="sumeme-vaults",
        object_max_size_bytes=1024,
    )


class MatrixIdentity:
    async def resolve_chat_scope(self, headers, payload: dict[str, Any]) -> MemoryScope:
        metadata = payload.get("metadata") or {}
        identifier = str(payload.get("user") or "missing")
        vault_id = str(metadata.get("vault_id") or "default")
        if headers.get("x-test-principal") == "service":
            return MemoryScope.service(identifier, vault_id)
        return MemoryScope.account(identifier, vault_id)


class MatrixVaults:
    def __init__(self) -> None:
        self.modes: dict[str, str] = {}

    def set_mode(self, scope: MemoryScope, mode: str) -> None:
        self.modes[scope.storage_key] = mode

    async def ensure(self, scope: MemoryScope, *, allow_create: bool) -> VaultPolicy:
        mode = self.modes.get(scope.storage_key, "cloud")
        return VaultPolicy(
            scope=scope,
            storage_mode=mode,  # type: ignore[arg-type]
            created_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-01T00:00:00+00:00",
        )


class MatrixStore:
    async def create_upload(self, record: ObjectRecord) -> PresignedRequest:
        return PresignedRequest(
            method="PUT",
            url=f"https://s3.example.test/upload/{record.object_id}",
            headers={"Content-Type": record.content_type},
            expires_in_seconds=600,
        )

    async def verify_upload(self, record: ObjectRecord) -> VerifiedObject:
        return VerifiedObject(size_bytes=record.size_bytes, sha256=record.sha256)

    async def create_download(self, record: ObjectRecord) -> PresignedRequest:
        return PresignedRequest(
            method="GET",
            url=f"https://s3.example.test/download/{record.object_id}",
            headers={},
            expires_in_seconds=600,
        )

    async def delete(self, _record: ObjectRecord) -> None:
        return None


@dataclass
class MatrixReservations:
    registry: ObjectRegistry
    store: MatrixStore

    async def complete(self, record: ObjectRecord) -> ObjectRecord:
        verified = await self.store.verify_upload(record)
        return await self.registry.complete(
            scope=record.scope,
            object_id=record.object_id,
            actual_size_bytes=verified.size_bytes,
            actual_sha256=verified.sha256,
        )

    async def delete(self, record: ObjectRecord) -> ObjectRecord:
        await self.store.delete(record)
        return await self.registry.soft_delete(record.scope, record.object_id)


def build_client(tmp_path) -> tuple[TestClient, MatrixVaults]:
    registry = ObjectRegistry(str(tmp_path / "objects.sqlite3"), 1024)
    asyncio.run(registry.initialize())
    store = MatrixStore()
    vaults = MatrixVaults()

    application = FastAPI()
    application.state.identity = MatrixIdentity()
    application.state.vaults = vaults
    application.state.objects = registry
    application.state.object_store = store
    application.state.object_reservations = MatrixReservations(registry, store)

    def require_auth(value: str | None) -> None:
        if value != "Bearer gateway":
            raise HTTPException(status_code=401, detail="invalid gateway token")

    application.include_router(
        build_object_router(
            core_settings=core_settings(),
            object_settings=object_settings(),
            require_gateway_auth=require_auth,
        )
    )
    return TestClient(application), vaults


def identity(
    user: str,
    vault: str,
    *,
    principal: str = "account",
) -> tuple[dict[str, str], dict[str, Any]]:
    headers = {"Authorization": "Bearer gateway"}
    if principal == "service":
        headers["X-Test-Principal"] = "service"
    return headers, {"user": user, "metadata": {"vault_id": vault}}


def reserve(
    client: TestClient,
    user: str,
    vault: str,
    *,
    principal: str = "account",
    object_kind: str = "raw",
    sanitized_for_cloud: bool = False,
) -> dict[str, Any]:
    headers, body = identity(user, vault, principal=principal)
    body.update(
        {
            "filename": "private.txt",
            "content_type": "text/plain",
            "size_bytes": 7,
            "sha256": hashlib.sha256(b"private").hexdigest(),
            "object_kind": object_kind,
            "sanitized_for_cloud": sanitized_for_cloud,
        }
    )
    response = client.post(
        "/api/objects/reserve-upload",
        headers=headers,
        json=body,
    )
    return {"response": response, "headers": headers, "identity": body}


def action_body(user: str, vault: str, object_id: str) -> dict[str, Any]:
    return {
        "user": user,
        "metadata": {"vault_id": vault},
        "object_id": object_id,
    }


def assert_not_found_for_all_object_actions(
    client: TestClient,
    *,
    headers: dict[str, str],
    body: dict[str, Any],
) -> None:
    for path in (
        "/api/objects/complete-upload",
        "/api/objects/create-download",
        "/api/objects/delete",
    ):
        response = client.post(path, headers=headers, json=body)
        assert response.status_code == 404, (path, response.text)
        assert response.json()["detail"] == "object_not_found"


def test_cross_account_vault_and_principal_cannot_observe_or_mutate_object(
    tmp_path,
) -> None:
    client, _vaults = build_client(tmp_path)
    owner = reserve(client, "alice", "personal")
    assert owner["response"].status_code == 200
    owner_payload = owner["response"].json()
    object_id = owner_payload["object"]["object_id"]
    assert "object_key" not in owner_payload["object"]

    attackers = [
        identity("bob", "personal"),
        identity("alice", "work"),
        identity("alice", "personal", principal="service"),
    ]
    for headers, attacker_identity in attackers:
        body = {
            **attacker_identity,
            "object_id": object_id,
        }
        assert_not_found_for_all_object_actions(
            client,
            headers=headers,
            body=body,
        )
        listed = client.post(
            "/api/objects/list",
            headers=headers,
            json=attacker_identity,
        )
        assert listed.status_code == 200
        assert listed.json()["objects"] == []

    owner_list = client.post(
        "/api/objects/list",
        headers=owner["headers"],
        json={
            "user": "alice",
            "metadata": {"vault_id": "personal"},
        },
    )
    assert owner_list.status_code == 200
    assert [item["object_id"] for item in owner_list.json()["objects"]] == [
        object_id
    ]

    complete = client.post(
        "/api/objects/complete-upload",
        headers=owner["headers"],
        json=action_body("alice", "personal", object_id),
    )
    assert complete.status_code == 200
    assert complete.json()["object"]["state"] == "ready"
    assert "object_key" not in complete.json()["object"]

    download = client.post(
        "/api/objects/create-download",
        headers=owner["headers"],
        json=action_body("alice", "personal", object_id),
    )
    assert download.status_code == 200
    assert download.json()["download"]["method"] == "GET"
    assert "object_key" not in download.json()["object"]

    deleted = client.post(
        "/api/objects/delete",
        headers=owner["headers"],
        json=action_body("alice", "personal", object_id),
    )
    assert deleted.status_code == 200
    assert deleted.json()["object"]["state"] == "deleted"

    default_list = client.post(
        "/api/objects/list",
        headers=owner["headers"],
        json={"user": "alice", "metadata": {"vault_id": "personal"}},
    )
    assert default_list.json()["objects"] == []
    deleted_list = client.post(
        "/api/objects/list",
        headers=owner["headers"],
        json={
            "user": "alice",
            "metadata": {"vault_id": "personal"},
            "include_deleted": True,
        },
    )
    assert deleted_list.json()["objects"][0]["state"] == "deleted"


def test_vault_policy_is_enforced_on_reserve_complete_and_download(tmp_path) -> None:
    client, vaults = build_client(tmp_path)
    local_scope = MemoryScope.account("alice", "local")
    vaults.set_mode(local_scope, "local-only")

    local = reserve(client, "alice", "local")
    assert local["response"].status_code == 409
    assert local["response"].json()["detail"] == "object_cloud_storage_disabled"

    hybrid_scope = MemoryScope.account("alice", "hybrid")
    vaults.set_mode(hybrid_scope, "hybrid")
    unsanitized = reserve(client, "alice", "hybrid")
    assert unsanitized["response"].status_code == 409
    assert (
        unsanitized["response"].json()["detail"]
        == "object_sanitized_cloud_copy_required"
    )
    raw_sanitized = reserve(
        client,
        "alice",
        "hybrid",
        sanitized_for_cloud=True,
    )
    assert raw_sanitized["response"].status_code == 409
    assert (
        raw_sanitized["response"].json()["detail"]
        == "object_raw_hybrid_upload_forbidden"
    )
    derivative = reserve(
        client,
        "alice",
        "hybrid",
        object_kind="sanitized-derivative",
        sanitized_for_cloud=True,
    )
    assert derivative["response"].status_code == 200

    mutable = reserve(client, "alice", "mutable")
    assert mutable["response"].status_code == 200
    mutable_id = mutable["response"].json()["object"]["object_id"]
    mutable_scope = MemoryScope.account("alice", "mutable")

    vaults.set_mode(mutable_scope, "local-only")
    blocked_complete = client.post(
        "/api/objects/complete-upload",
        headers=mutable["headers"],
        json=action_body("alice", "mutable", mutable_id),
    )
    assert blocked_complete.status_code == 409
    assert blocked_complete.json()["detail"] == "object_cloud_storage_disabled"

    vaults.set_mode(mutable_scope, "cloud")
    completed = client.post(
        "/api/objects/complete-upload",
        headers=mutable["headers"],
        json=action_body("alice", "mutable", mutable_id),
    )
    assert completed.status_code == 200

    vaults.set_mode(mutable_scope, "local-only")
    blocked_download = client.post(
        "/api/objects/create-download",
        headers=mutable["headers"],
        json=action_body("alice", "mutable", mutable_id),
    )
    assert blocked_download.status_code == 409
    assert blocked_download.json()["detail"] == "object_cloud_storage_disabled"
