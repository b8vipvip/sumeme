from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .config import Settings
from .identity import IdentityError
from .memory_scope import MemoryScope
from .object_config import ObjectAccessSettings
from .object_store import ObjectStoreError
from .objects import (
    ObjectRecord,
    ObjectRegistryError,
    validate_storage_policy_for_object,
)
from .vaults import VaultPolicy, VaultRegistryError, should_auto_register_vault


class ObjectIdentityBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReserveUploadBody(ObjectIdentityBody):
    filename: str = Field(min_length=1, max_length=1024)
    content_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    object_kind: str = "raw"
    sanitized_for_cloud: bool = False
    local_ref_id: str = Field(default="", max_length=512)


class ObjectActionBody(ObjectIdentityBody):
    object_id: str = Field(min_length=32, max_length=32)


class ListObjectsBody(ObjectIdentityBody):
    include_deleted: bool = False
    limit: int = Field(default=100, ge=1, le=500)


def public_object(record: ObjectRecord) -> dict[str, Any]:
    """Return metadata without exposing internal bucket coordinates."""

    return {
        "object_id": record.object_id,
        "storage_mode": record.storage_mode,
        "object_kind": record.object_kind,
        "state": record.state,
        "original_name": record.original_name,
        "content_type": record.content_type,
        "size_bytes": record.size_bytes,
        "sha256": record.sha256,
        "sanitized_for_cloud": record.sanitized_for_cloud,
        "local_ref_id": record.local_ref_id,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "ready_at": record.ready_at,
        "deleted_at": record.deleted_at,
    }


def build_object_router(
    core_settings: Settings,
    object_settings: ObjectAccessSettings,
    require_gateway_auth: Callable[[str | None], None],
) -> APIRouter:
    router = APIRouter(prefix="/api/objects", tags=["objects"])

    def require_enabled(request: Request) -> None:
        if not object_settings.object_api_enabled:
            raise HTTPException(status_code=503, detail="object_api_disabled")
        if not hasattr(request.app.state, "objects") or not hasattr(
            request.app.state, "object_store"
        ):
            raise HTTPException(status_code=503, detail="object_api_unavailable")

    async def resolve_scope_and_policy(
        request: Request,
        body: ObjectIdentityBody,
    ) -> tuple[MemoryScope, VaultPolicy]:
        service_token = str(request.headers.get("x-sumeme-service-token") or "").strip()
        if core_settings.identity_mode == "legacy-client-asserted" and not service_token:
            raise HTTPException(
                status_code=503,
                detail="object_trusted_identity_required",
            )
        payload = body.model_dump(exclude_none=True)
        try:
            scope = await request.app.state.identity.resolve_chat_scope(
                request.headers,
                payload,
            )
        except IdentityError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc
        try:
            policy = await request.app.state.vaults.ensure(
                scope,
                allow_create=should_auto_register_vault(
                    scope,
                    core_settings.identity_mode,
                ),
            )
        except VaultRegistryError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc
        return scope, policy

    def raise_registry(exc: ObjectRegistryError) -> None:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc

    def raise_store(exc: ObjectStoreError) -> None:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc

    def enforce_current_policy(policy: VaultPolicy, record: ObjectRecord) -> None:
        try:
            validate_storage_policy_for_object(
                policy,
                object_kind=record.object_kind,
                sanitized_for_cloud=record.sanitized_for_cloud,
            )
        except ObjectRegistryError as exc:
            raise_registry(exc)

    @router.post("/reserve-upload")
    async def reserve_upload(
        body: ReserveUploadBody,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_gateway_auth(authorization)
        require_enabled(request)
        scope, policy = await resolve_scope_and_policy(request, body)
        try:
            record = await request.app.state.objects.reserve(
                scope=scope,
                policy=policy,
                filename=body.filename,
                content_type=body.content_type,
                size_bytes=body.size_bytes,
                sha256=body.sha256,
                object_kind=body.object_kind,
                sanitized_for_cloud=body.sanitized_for_cloud,
                local_ref_id=body.local_ref_id,
            )
        except ObjectRegistryError as exc:
            raise_registry(exc)
        try:
            upload = await request.app.state.object_store.create_upload(record)
        except ObjectStoreError as exc:
            try:
                await request.app.state.objects.soft_delete(scope, record.object_id)
            except ObjectRegistryError:
                pass
            raise_store(exc)
        return {
            "scope": scope.display_key,
            "object": public_object(record),
            "upload": upload.as_dict(),
        }

    @router.post("/complete-upload")
    async def complete_upload(
        body: ObjectActionBody,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_gateway_auth(authorization)
        require_enabled(request)
        scope, policy = await resolve_scope_and_policy(request, body)
        try:
            record = await request.app.state.objects.get(scope, body.object_id)
        except ObjectRegistryError as exc:
            raise_registry(exc)
        if record is None:
            raise HTTPException(status_code=404, detail="object_not_found")
        enforce_current_policy(policy, record)
        try:
            verified = await request.app.state.object_store.verify_upload(record)
            completed = await request.app.state.objects.complete(
                scope=scope,
                object_id=record.object_id,
                actual_size_bytes=verified.size_bytes,
                actual_sha256=verified.sha256,
            )
        except ObjectStoreError as exc:
            raise_store(exc)
        except ObjectRegistryError as exc:
            raise_registry(exc)
        return {
            "scope": scope.display_key,
            "object": public_object(completed),
        }

    @router.post("/create-download")
    async def create_download(
        body: ObjectActionBody,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_gateway_auth(authorization)
        require_enabled(request)
        scope, policy = await resolve_scope_and_policy(request, body)
        try:
            record = await request.app.state.objects.get(scope, body.object_id)
        except ObjectRegistryError as exc:
            raise_registry(exc)
        if record is None or record.state == "deleted":
            raise HTTPException(status_code=404, detail="object_not_found")
        enforce_current_policy(policy, record)
        try:
            download = await request.app.state.object_store.create_download(record)
        except ObjectStoreError as exc:
            raise_store(exc)
        return {
            "scope": scope.display_key,
            "object": public_object(record),
            "download": download.as_dict(),
        }

    @router.post("/delete")
    async def delete_object(
        body: ObjectActionBody,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_gateway_auth(authorization)
        require_enabled(request)
        scope, _policy = await resolve_scope_and_policy(request, body)
        try:
            record = await request.app.state.objects.get(scope, body.object_id)
        except ObjectRegistryError as exc:
            raise_registry(exc)
        if record is None:
            raise HTTPException(status_code=404, detail="object_not_found")
        if record.state != "deleted":
            try:
                await request.app.state.object_store.delete(record)
                record = await request.app.state.objects.soft_delete(
                    scope,
                    record.object_id,
                )
            except ObjectStoreError as exc:
                raise_store(exc)
            except ObjectRegistryError as exc:
                raise_registry(exc)
        return {
            "scope": scope.display_key,
            "object": public_object(record),
        }

    @router.post("/list")
    async def list_objects(
        body: ListObjectsBody,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_gateway_auth(authorization)
        require_enabled(request)
        scope, policy = await resolve_scope_and_policy(request, body)
        try:
            records = await request.app.state.objects.list(
                scope,
                include_deleted=body.include_deleted,
                limit=body.limit,
            )
        except ObjectRegistryError as exc:
            raise_registry(exc)
        return {
            "scope": scope.display_key,
            "storage_mode": policy.storage_mode,
            "objects": [public_object(record) for record in records],
        }

    return router
