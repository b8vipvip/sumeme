from __future__ import annotations

import asyncio
import hmac
import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .config import get_settings
from .content import assistant_text, flatten_content, latest_user_message, safe_id
from .identity import IdentityError, IdentityResolver
from .memory import MemoryCoordinator
from .memory_scope import MemoryScope
from .vaults import (
    VaultPolicy,
    VaultRegistry,
    VaultRegistryError,
    should_auto_register_vault,
)

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("sumeme.gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.relay_timeout_seconds),
        follow_redirects=True,
    )
    app.state.memory = MemoryCoordinator(settings)
    app.state.identity = IdentityResolver(settings)
    app.state.vaults = VaultRegistry(
        settings.vault_registry_path,
        settings.default_storage_mode,
    )
    await app.state.vaults.initialize()
    try:
        yield
    finally:
        await app.state.memory.aclose()
        await app.state.http.aclose()


app = FastAPI(title="SuMeMe Memory Gateway", version="0.7.0", lifespan=lifespan)


def _bearer_token(authorization: str | None) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def require_gateway_auth(authorization: str | None) -> None:
    expected = settings.gateway_api_key.get_secret_value()
    supplied = _bearer_token(authorization)
    if not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="invalid gateway token")


def require_admin_auth(authorization: str | None) -> None:
    expected = settings.gateway_admin_token.get_secret_value()
    supplied = _bearer_token(authorization)
    if not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="invalid admin token")


def relay_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.openai_relay_api_key.get_secret_value()}",
        "Content-Type": "application/json",
    }


def resolve_admin_scope(body: dict[str, Any]) -> MemoryScope:
    principal_type = str(body.get("principal_type") or "account").strip().lower()
    if "account_id" in body or "vault_id" in body or principal_type == "service":
        account_id = str(body.get("account_id") or settings.sumeme_user_id)
        vault_id = str(body.get("vault_id") or "default")
        if principal_type == "service":
            return MemoryScope.service(account_id, vault_id)
        if principal_type == "account":
            return MemoryScope.account(account_id, vault_id)
        raise HTTPException(status_code=400, detail="invalid principal_type")

    return MemoryScope.from_legacy_user_id(
        str(body.get("user_id") or settings.sumeme_user_id),
        settings.sumeme_user_id,
    )


async def resolve_vault_policy(scope: MemoryScope) -> VaultPolicy:
    try:
        return await app.state.vaults.ensure(
            scope,
            allow_create=should_auto_register_vault(scope, settings.identity_mode),
        )
    except VaultRegistryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc


def resolve_conversation_id(request: Request, payload: dict[str, Any]) -> str:
    metadata = payload.get("metadata") or {}
    return safe_id(
        request.headers.get("x-sumeme-conversation-id")
        or str(metadata.get("conversation_id") or metadata.get("topic_id") or "")
        or str(payload.get("conversation_id") or "")
        or uuid.uuid4().hex
    )


@app.get("/health")
async def health() -> dict[str, Any]:
    mode = settings.identity_mode
    jwt_mode = mode in {"jwt-preferred", "jwt-required"}
    trusted_user_mode = mode == "trusted-openai-user"
    jwks_source = "none"
    if settings.identity_jwks_url.strip():
        jwks_source = "remote-https"
    elif settings.identity_jwks_json.get_secret_value().strip():
        jwks_source = "static-public-jwks"

    if jwt_mode:
        account_source = "verified-sub"
        vault_authorization = "claim-and-registry-enforced"
    elif trusted_user_mode:
        account_source = "gateway-authenticated-openai-user"
        vault_authorization = "registry-enforced"
    else:
        account_source = "client-asserted"
        vault_authorization = "legacy-registry-autocreate"

    return {
        "status": "ok",
        "memory_provider": app.state.memory.provider_name,
        "memory_scope_schema": 2,
        "vault_registry": "sqlite",
        "default_storage_mode": settings.default_storage_mode,
        "identity_enforcement": mode,
        "identity_account_source": account_source,
        "identity_vault_authorization": vault_authorization,
        "identity_jwks_source": jwks_source,
        "service_identity_configured": bool(
            settings.gateway_service_token.get_secret_value()
        ),
        "memory_checkpoint": True,
        "mempalace_enabled": settings.mempalace_enabled,
        "letta_enabled": settings.letta_enabled,
        "relay_base_url": settings.openai_relay_base_url,
    }


@app.get("/v1/models")
async def models(authorization: str | None = Header(default=None)):
    require_gateway_auth(authorization)
    try:
        response = await app.state.http.get(settings.relay_models_url, headers=relay_headers())
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"relay unavailable: {exc}") from exc
    return JSONResponse(
        status_code=response.status_code,
        content=_json_or_error(response),
        headers=_safe_response_headers(response),
    )


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    authorization: str | None = Header(default=None),
):
    require_gateway_auth(authorization)
    payload = await request.json()
    messages = payload.get("messages")
    if not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="messages must be an array")

    try:
        scope = await app.state.identity.resolve_chat_scope(request.headers, payload)
    except IdentityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc
    policy = await resolve_vault_policy(scope)

    conversation_id = resolve_conversation_id(request, payload)
    latest = latest_user_message(messages)
    query = flatten_content((latest or {}).get("content"))

    memory_context = ""
    if policy.allows_cloud_recall:
        memory_context = await app.state.memory.recall(query, scope)
    enriched = app.state.memory.inject_context(payload, memory_context)

    if payload.get("stream"):
        return StreamingResponse(
            _stream_relay(
                request_payload=payload,
                enriched_payload=enriched,
                scope=scope,
                policy=policy,
                conversation_id=conversation_id,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                **_vault_policy_headers(policy),
            },
        )

    try:
        response = await app.state.http.post(
            settings.relay_chat_url,
            headers=relay_headers(),
            json=enriched,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"relay unavailable: {exc}") from exc

    data = _json_or_error(response)
    if 200 <= response.status_code < 300 and policy.allows_automatic_cloud_write:
        asyncio.create_task(
            _remember_background(
                scope=scope,
                conversation_id=conversation_id,
                request_payload=payload,
                assistant_output=assistant_text(data),
            )
        )
    response_headers = _safe_response_headers(response)
    response_headers.update(_vault_policy_headers(policy))
    return JSONResponse(
        status_code=response.status_code,
        content=data,
        headers=response_headers,
    )


@app.put("/api/vaults/policy")
async def upsert_vault_policy(
    request: Request,
    authorization: str | None = Header(default=None),
):
    require_admin_auth(authorization)
    body = await request.json()
    scope = resolve_admin_scope(body)
    storage_mode = str(body.get("storage_mode") or "")
    try:
        policy = await app.state.vaults.upsert(scope, storage_mode)
    except VaultRegistryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc
    return {"vault": policy.as_dict()}


@app.post("/api/vaults/list")
async def list_vault_policies(
    request: Request,
    authorization: str | None = Header(default=None),
):
    require_admin_auth(authorization)
    body = await request.json()
    principal_type = str(body.get("principal_type") or "").strip() or None
    account_id = str(body.get("account_id") or "").strip() or None
    try:
        policies = await app.state.vaults.list(
            principal_type=principal_type,
            account_id=account_id,
        )
    except VaultRegistryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc
    return {"vaults": [policy.as_dict() for policy in policies]}


@app.post("/api/memory/checkpoint")
async def memory_checkpoint(
    request: Request,
    authorization: str | None = Header(default=None),
):
    """Synchronously submit one exchange and return only sanitized outcomes."""

    require_admin_auth(authorization)
    body = await request.json()
    scope = resolve_admin_scope(body)
    policy = await resolve_vault_policy(scope)
    if policy.is_local_only:
        raise HTTPException(status_code=409, detail="vault_local_only")
    if policy.requires_sanitized_cloud_write and body.get("sanitized_for_cloud") is not True:
        raise HTTPException(
            status_code=409,
            detail="vault_sanitized_cloud_write_required",
        )

    request_payload = body.get("request_payload")
    if not isinstance(request_payload, dict):
        raise HTTPException(status_code=400, detail="request_payload must be an object")
    if not isinstance(request_payload.get("messages"), list):
        raise HTTPException(
            status_code=400,
            detail="request_payload.messages must be an array",
        )

    conversation_id = safe_id(
        str(body.get("conversation_id") or uuid.uuid4().hex),
        "memory-checkpoint",
    )
    assistant_output = str(body.get("assistant_text") or "")
    result = await app.state.memory.remember_exchange(
        scope=scope,
        conversation_id=conversation_id,
        request_payload=request_payload,
        assistant_text=assistant_output,
    )
    return {
        "scope": scope.display_key,
        "storage_mode": policy.storage_mode,
        "write": result.as_dict(),
    }


@app.post("/api/memory/search")
async def memory_search(
    request: Request,
    authorization: str | None = Header(default=None),
):
    require_admin_auth(authorization)
    body = await request.json()
    query = str(body.get("query") or "")
    scope = resolve_admin_scope(body)
    policy = await resolve_vault_policy(scope)

    context = ""
    if policy.allows_cloud_recall:
        context = await app.state.memory.recall(query, scope)
    return {
        "provider": app.state.memory.provider_name,
        "scope": scope.display_key,
        "storage_mode": policy.storage_mode,
        "context": context,
    }


async def _remember_background(
    *,
    scope: MemoryScope,
    conversation_id: str,
    request_payload: dict[str, Any],
    assistant_output: str,
) -> None:
    try:
        result = await app.state.memory.remember_exchange(
            scope=scope,
            conversation_id=conversation_id,
            request_payload=request_payload,
            assistant_text=assistant_output,
        )
        if not result.success:
            logger.warning(
                "Memory write incomplete provider=%s scope=%s error_codes=%s",
                result.provider,
                scope.display_key,
                ",".join(result.error_codes) or "unknown",
            )
    except Exception:
        logger.exception(
            "Unexpected background memory write failure provider=%s scope=%s",
            app.state.memory.provider_name,
            scope.display_key,
        )


async def _stream_relay(
    *,
    request_payload: dict[str, Any],
    enriched_payload: dict[str, Any],
    scope: MemoryScope,
    policy: VaultPolicy,
    conversation_id: str,
) -> AsyncIterator[bytes]:
    assistant_parts: list[str] = []
    try:
        async with app.state.http.stream(
            "POST",
            settings.relay_chat_url,
            headers=relay_headers(),
            json=enriched_payload,
        ) as response:
            if response.status_code >= 400:
                body = await response.aread()
                yield body
                return

            pending = b""
            async for chunk in response.aiter_bytes():
                if not chunk:
                    continue
                pending += chunk
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    _capture_sse_text(line, assistant_parts)
                yield chunk
            if pending:
                _capture_sse_text(pending, assistant_parts)
    except httpx.HTTPError as exc:
        logger.exception("Relay streaming failed")
        error = {
            "error": {
                "message": f"relay unavailable: {exc}",
                "type": "upstream_error",
            }
        }
        yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n".encode()
        yield b"data: [DONE]\n\n"
        return

    if policy.allows_automatic_cloud_write:
        asyncio.create_task(
            _remember_background(
                scope=scope,
                conversation_id=conversation_id,
                request_payload=request_payload,
                assistant_output="".join(assistant_parts),
            )
        )


def _capture_sse_text(line: bytes, parts: list[str]) -> None:
    line = line.strip()
    if not line.startswith(b"data:"):
        return
    raw = line[5:].strip()
    if not raw or raw == b"[DONE]":
        return
    try:
        event = json.loads(raw)
        delta = ((event.get("choices") or [{}])[0].get("delta") or {}).get("content")
        if isinstance(delta, str):
            parts.append(delta)
        elif delta:
            parts.append(flatten_content(delta))
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
        return


def _json_or_error(response: httpx.Response) -> dict[str, Any]:
    try:
        value = response.json()
        if isinstance(value, dict):
            return value
        return {"data": value}
    except ValueError:
        return {
            "error": {
                "message": response.text[:5000],
                "type": "invalid_upstream_response",
            }
        }


def _safe_response_headers(response: httpx.Response) -> dict[str, str]:
    allowed = {}
    for key in ("x-request-id", "openai-processing-ms"):
        if value := response.headers.get(key):
            allowed[key] = value
    return allowed


def _vault_policy_headers(policy: VaultPolicy) -> dict[str, str]:
    write_policy = "automatic"
    if policy.is_local_only:
        write_policy = "disabled-local-only"
    elif policy.requires_sanitized_cloud_write:
        write_policy = "explicit-sanitized-only"
    return {
        "X-SuMeMe-Storage-Mode": policy.storage_mode,
        "X-SuMeMe-Memory-Write": write_policy,
    }
