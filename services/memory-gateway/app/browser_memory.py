from __future__ import annotations

import os
import uuid
from typing import Any
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .browser_memory_store import BrowserMemoryStore
from .config import Settings
from .content import safe_id
from .memory_result import MemoryOperationError
from .memory_scope import MemoryScope
from .vaults import VaultPolicy, VaultRegistryError


class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=12000)
    vault_id: str = Field(default="default", max_length=128)


class MemoryRememberRequest(BaseModel):
    assistant_text: str = Field(default="", max_length=100000)
    conversation_id: str = Field(default="", max_length=512)
    sanitized_for_cloud: bool = False
    text: str = Field(min_length=1, max_length=100000)
    vault_id: str = Field(default="default", max_length=128)


class MemoryDeleteRequest(BaseModel):
    drawer_id: str = Field(min_length=1, max_length=128)
    vault_id: str = Field(default="default", max_length=128)


def build_browser_memory_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/ui/memory", tags=["browser-memory"])
    store = BrowserMemoryStore(settings)

    async def resolve_context(
        request: Request,
        vault_id: str,
        *,
        mutation: bool = False,
    ) -> tuple[dict[str, Any], MemoryScope, VaultPolicy]:
        if mutation:
            _require_same_origin(request)
        user = await _resolve_lobehub_user(request)
        scope = MemoryScope.account(str(user["id"]), vault_id or "default")
        try:
            policy = await request.app.state.vaults.ensure(scope, allow_create=True)
        except VaultRegistryError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc
        return user, scope, policy

    @router.get("/stats")
    async def memory_stats(
        request: Request,
        vault_id: str = Query(default="default", max_length=128),
    ) -> dict[str, Any]:
        user, scope, policy = await resolve_context(request, vault_id)
        stats = await store.stats(scope)
        return {
            "account": {"id": user["id"], "email": user.get("email")},
            "provider": request.app.state.memory.provider_name,
            "scope": scope.display_key,
            "storage_mode": policy.storage_mode,
            "stats": stats,
        }

    @router.get("/list")
    async def memory_list(
        request: Request,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        q: str = Query(default="", max_length=1000),
        role: str = Query(default="", max_length=32),
        conversation_id: str = Query(default="", max_length=512),
        vault_id: str = Query(default="default", max_length=128),
    ) -> dict[str, Any]:
        user, scope, policy = await resolve_context(request, vault_id)
        result = await store.list_drawers(
            scope,
            limit=limit,
            offset=offset,
            query=q,
            role=role,
            conversation_id=conversation_id,
        )
        return {
            "account": {"id": user["id"], "email": user.get("email")},
            "provider": request.app.state.memory.provider_name,
            "scope": scope.display_key,
            "storage_mode": policy.storage_mode,
            **result,
        }

    @router.get("/item/{drawer_id}")
    async def memory_item(
        drawer_id: str,
        request: Request,
        vault_id: str = Query(default="default", max_length=128),
    ) -> dict[str, Any]:
        _, scope, policy = await resolve_context(request, vault_id)
        item = await store.get_drawer(scope, drawer_id)
        if item is None:
            raise HTTPException(status_code=404, detail="memory_not_found")
        return {
            "item": item,
            "scope": scope.display_key,
            "storage_mode": policy.storage_mode,
        }

    @router.post("/search")
    async def memory_search(
        body: MemorySearchRequest,
        request: Request,
    ) -> dict[str, Any]:
        _, scope, policy = await resolve_context(request, body.vault_id, mutation=True)
        if policy.is_local_only:
            raise HTTPException(status_code=409, detail="vault_local_only")

        query = body.query.strip()
        if not query:
            raise HTTPException(status_code=400, detail="query_required")

        provider = request.app.state.memory.provider
        raw_results: list[dict[str, Any]] = []
        mempalace = getattr(provider, "mempalace", None)
        if mempalace is not None:
            try:
                raw_results = await mempalace.search(query, scope)
            except MemoryOperationError as exc:
                raise HTTPException(status_code=502, detail=exc.code) from exc

        context = await request.app.state.memory.recall(query, scope)
        return {
            "context": context,
            "provider": request.app.state.memory.provider_name,
            "raw_results": raw_results,
            "scope": scope.display_key,
            "storage_mode": policy.storage_mode,
        }

    @router.post("/remember")
    async def memory_remember(
        body: MemoryRememberRequest,
        request: Request,
    ) -> dict[str, Any]:
        _, scope, policy = await resolve_context(request, body.vault_id, mutation=True)
        if policy.is_local_only:
            raise HTTPException(status_code=409, detail="vault_local_only")
        if policy.requires_sanitized_cloud_write and body.sanitized_for_cloud is not True:
            raise HTTPException(
                status_code=409,
                detail="vault_sanitized_cloud_write_required",
            )

        text = body.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="memory_text_required")
        conversation_id = safe_id(
            body.conversation_id.strip() or f"manual-{uuid.uuid4().hex}",
            "manual-memory",
        )
        result = await request.app.state.memory.remember_exchange(
            scope=scope,
            conversation_id=conversation_id,
            request_payload={
                "messages": [{"content": text, "role": "user"}],
                "metadata": {"source": "sumeme-memory-ui"},
            },
            assistant_text=body.assistant_text.strip(),
        )
        return {
            "conversation_id": conversation_id,
            "scope": scope.display_key,
            "storage_mode": policy.storage_mode,
            "write": result.as_dict(),
        }

    @router.post("/delete")
    async def memory_delete(
        body: MemoryDeleteRequest,
        request: Request,
    ) -> dict[str, Any]:
        _, scope, policy = await resolve_context(request, body.vault_id, mutation=True)
        try:
            deleted = await store.delete_drawer(scope, body.drawer_id)
        except MemoryOperationError as exc:
            raise HTTPException(status_code=502, detail=exc.code) from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="memory_not_found")
        return {
            "deleted": True,
            "drawer_id": body.drawer_id,
            "scope": scope.display_key,
            "storage_mode": policy.storage_mode,
        }

    return router


def _require_same_origin(request: Request) -> None:
    origin = request.headers.get("origin", "").strip()
    if not origin:
        return
    parsed = urlsplit(origin)
    request_host = request.headers.get("host", "").strip().lower()
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != request_host:
        raise HTTPException(status_code=403, detail="cross_origin_request_rejected")


async def _resolve_lobehub_user(request: Request) -> dict[str, Any]:
    cookie = request.headers.get("cookie", "").strip()
    if not cookie:
        raise HTTPException(status_code=401, detail="lobehub_session_required")

    base_url = os.getenv("LOBEHUB_INTERNAL_URL", "http://lobe:3210").rstrip("/")
    headers = {
        "Accept": "application/json",
        "Cookie": cookie,
        "X-Forwarded-Host": request.headers.get("host", ""),
        "X-Forwarded-Proto": request.url.scheme,
    }
    try:
        response = await request.app.state.http.get(
            f"{base_url}/api/auth/get-session",
            headers=headers,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="lobehub_auth_unavailable") from exc

    if response.status_code in {401, 403}:
        raise HTTPException(status_code=401, detail="lobehub_session_required")
    if response.status_code >= 400:
        raise HTTPException(status_code=503, detail="lobehub_auth_unavailable")
    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="lobehub_auth_invalid_response") from exc

    user = payload.get("user") if isinstance(payload, dict) else None
    session = payload.get("session") if isinstance(payload, dict) else None
    if not isinstance(user, dict) or not user.get("id") or not session:
        raise HTTPException(status_code=401, detail="lobehub_session_required")
    return user
