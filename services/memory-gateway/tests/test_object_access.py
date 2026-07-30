from __future__ import annotations

import asyncio
import hashlib
import io
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.memory_scope import MemoryScope
from app.object_api import build_object_router
from app.object_config import ObjectAccessSettings
from app.object_store import (
    ObjectStoreError,
    PresignedRequest,
    S3ObjectStore,
    VerifiedObject,
)
from app.objects import ObjectRecord, ObjectRegistry
from app.vaults import VaultPolicy


class FakeStreamingBody(io.BytesIO):
    def close(self) -> None:
        super().close()


class FakeS3Client:
    def __init__(self, endpoint_url: str):
        self.endpoint_url = endpoint_url
        self.objects: dict[tuple[str, str], bytes] = {}
        self.deleted: list[tuple[str, str]] = []

    def generate_presigned_url(
        self,
        operation: str,
        *,
        Params: dict,
        ExpiresIn: int,
        HttpMethod: str,
    ) -> str:
        return (
            f"{self.endpoint_url}/{Params['Bucket']}/{Params['Key']}"
            f"?operation={operation}&expires={ExpiresIn}&method={HttpMethod}"
        )

    def get_object(self, *, Bucket: str, Key: str) -> dict:
        value = self.objects[(Bucket, Key)]
        return {
            "ContentLength": len(value),
            "Body": FakeStreamingBody(value),
        }

    def head_object(self, *, Bucket: str, Key: str) -> dict:
        value = self.objects[(Bucket, Key)]
        return {"ContentLength": len(value)}

    def delete_object(self, *, Bucket: str, Key: str) -> dict:
        self.objects.pop((Bucket, Key), None)
        self.deleted.append((Bucket, Key))
        return {}


def object_settings(**overrides) -> ObjectAccessSettings:
    values = {
        "object_api_enabled": True,
        "rustfs_internal_endpoint": "http://rustfs:9000",
        "rustfs_public_endpoint": "https://s3.example.test",
        "rustfs_access_key": "access",
        "rustfs_secret_key": "secret",
        "rustfs_private_bucket": "sumeme-vaults",
    }
    values.update(overrides)
    return ObjectAccessSettings(**values)


def core_settings(*, identity_mode: str = "trusted-openai-user") -> Settings:
    return Settings(
        openai_relay_base_url="https://relay.example.test/v1",
        openai_relay_api_key="relay",
        gateway_api_key="gateway",
        gateway_admin_token="admin",
        identity_mode=identity_mode,
        identity_trusted_upstream_issuer="lobehub-test",
        letta_required=False,
    )


def record(*, state: str = "reserved", content: bytes = b"hello") -> ObjectRecord:
    now = datetime.now(UTC).isoformat()
    return ObjectRecord(
        object_id="1" * 32,
        scope=MemoryScope.account("alice", "personal"),
        object_key="accounts/alice/vaults/personal/objects/" + "1" * 32 + ".txt",
        storage_mode="cloud",
        object_kind="raw",
        state=state,  # type: ignore[arg-type]
        original_name="notes.txt",
        content_type="text/plain",
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        sanitized_for_cloud=False,
        local_ref_id="",
        created_at=now,
        updated_at=now,
        ready_at=now if state == "ready" else "",
        deleted_at="",
    )


def test_object_access_config_requires_https_and_credentials() -> None:
    disabled = ObjectAccessSettings()
    assert disabled.object_api_enabled is False

    with pytest.raises(ValidationError):
        object_settings(rustfs_public_endpoint="http://public.example.test")
    with pytest.raises(ValidationError):
        object_settings(rustfs_access_key="")

    configured = object_settings()
    assert configured.rustfs_public_endpoint == "https://s3.example.test"
    assert configured.object_presign_ttl_seconds == 600


def test_s3_store_signs_public_urls_and_verifies_content(monkeypatch) -> None:
    clients: dict[str, FakeS3Client] = {}

    def fake_client(_service: str, *, endpoint_url: str, **_kwargs):
        client = clients.setdefault(endpoint_url, FakeS3Client(endpoint_url))
        return client

    monkeypatch.setattr("app.object_store.boto3.client", fake_client)
    store = S3ObjectStore(object_settings())
    item = record()
    internal = clients["http://rustfs:9000"]
    internal.objects[("sumeme-vaults", item.object_key)] = b"hello"

    upload = store._create_upload_sync(item)
    assert upload.method == "PUT"
    assert upload.url.startswith("https://s3.example.test/sumeme-vaults/")
    assert upload.headers == {"Content-Type": "text/plain"}

    verified = store._verify_upload_sync(item)
    assert verified == VerifiedObject(
        size_bytes=5,
        sha256=hashlib.sha256(b"hello").hexdigest(),
    )


def test_s3_store_removes_invalid_upload(monkeypatch) -> None:
    clients: dict[str, FakeS3Client] = {}

    def fake_client(_service: str, *, endpoint_url: str, **_kwargs):
        return clients.setdefault(endpoint_url, FakeS3Client(endpoint_url))

    monkeypatch.setattr("app.object_store.boto3.client", fake_client)
    store = S3ObjectStore(object_settings())
    item = record()
    internal = clients["http://rustfs:9000"]
    internal.objects[("sumeme-vaults", item.object_key)] = b"wrong"

    with pytest.raises(ObjectStoreError) as captured:
        store._verify_upload_sync(item)
    assert captured.value.code == "object_sha256_mismatch"
    assert ("sumeme-vaults", item.object_key) in internal.deleted


class FakeIdentity:
    async def resolve_chat_scope(self, _headers, payload):
        metadata = payload.get("metadata") or {}
        return MemoryScope.account(
            str(payload.get("user") or "missing"),
            str(metadata.get("vault_id") or "default"),
        )


class FakeVaults:
    async def ensure(self, scope, *, allow_create):
        return VaultPolicy(
            scope=scope,
            storage_mode="cloud",
            created_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-01T00:00:00+00:00",
        )


class FakeObjectStore:
    async def create_upload(self, _record):
        return PresignedRequest(
            method="PUT",
            url="https://s3.example.test/upload",
            headers={"Content-Type": "text/plain"},
            expires_in_seconds=600,
        )

    async def verify_upload(self, item):
        return VerifiedObject(size_bytes=item.size_bytes, sha256=item.sha256)

    async def create_download(self, _record):
        return PresignedRequest(
            method="GET",
            url="https://s3.example.test/download",
            headers={},
            expires_in_seconds=600,
        )

    async def delete(self, _record):
        return None


def test_object_api_hides_internal_key_and_enforces_scope(tmp_path) -> None:
    registry = ObjectRegistry(str(tmp_path / "objects.sqlite3"), 1024)
    asyncio.run(registry.initialize())
    application = FastAPI()
    application.state.identity = FakeIdentity()
    application.state.vaults = FakeVaults()
    application.state.objects = registry
    application.state.object_store = FakeObjectStore()

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
    client = TestClient(application)
    digest = hashlib.sha256(b"hello").hexdigest()

    reserve = client.post(
        "/api/objects/reserve-upload",
        headers={"Authorization": "Bearer gateway"},
        json={
            "user": "alice",
            "metadata": {"vault_id": "personal"},
            "filename": "notes.txt",
            "content_type": "text/plain",
            "size_bytes": 5,
            "sha256": digest,
        },
    )
    assert reserve.status_code == 200
    reserved = reserve.json()
    assert "object_key" not in reserved["object"]
    object_id = reserved["object"]["object_id"]

    complete = client.post(
        "/api/objects/complete-upload",
        headers={"Authorization": "Bearer gateway"},
        json={
            "user": "alice",
            "metadata": {"vault_id": "personal"},
            "object_id": object_id,
        },
    )
    assert complete.status_code == 200
    assert complete.json()["object"]["state"] == "ready"

    cross_account = client.post(
        "/api/objects/create-download",
        headers={"Authorization": "Bearer gateway"},
        json={
            "user": "bob",
            "metadata": {"vault_id": "personal"},
            "object_id": object_id,
        },
    )
    assert cross_account.status_code == 404
    assert cross_account.json()["detail"] == "object_not_found"


def test_object_api_rejects_untrusted_legacy_account() -> None:
    application = FastAPI()
    application.state.identity = FakeIdentity()
    application.state.vaults = FakeVaults()
    application.state.objects = SimpleNamespace()
    application.state.object_store = FakeObjectStore()
    application.include_router(
        build_object_router(
            core_settings=core_settings(identity_mode="legacy-client-asserted"),
            object_settings=object_settings(),
            require_gateway_auth=lambda _value: None,
        )
    )
    client = TestClient(application)

    response = client.post(
        "/api/objects/list",
        json={"user": "alice", "metadata": {"vault_id": "personal"}},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "object_trusted_identity_required"
