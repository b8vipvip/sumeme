from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .admin_store import AdminStore
from .browser_memory import _resolve_lobehub_user
from .content import assistant_text, flatten_content, latest_user_message, safe_id
from .memory_scope import MemoryScope
from .vaults import VaultRegistryError


class ClientChatBody(BaseModel):
    messages: list[dict[str, Any]]
    model: str = Field(default="", max_length=300)
    stream: bool = True
    conversation_id: str = Field(default="", max_length=512)
    vault_id: str = Field(default="default", max_length=128)
    memory_enabled: bool = True


class SignupBody(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=512)
    name: str = Field(min_length=1, max_length=120)


def _same_origin(request: Request) -> None:
    origin = request.headers.get("origin", "").strip()
    if not origin:
        return
    parsed = urlsplit(origin)
    if parsed.netloc.lower() != request.headers.get("host", "").lower():
        raise HTTPException(status_code=403, detail="cross_origin_request_rejected")


def _store(request: Request) -> AdminStore:
    return request.app.state.admin_store


async def _runtime_settings(request: Request) -> dict[str, Any]:
    stored = await _store(request).get_settings(include_secrets=True)
    return {
        "relay_base_url": str(
            stored.get("api.relay_base_url")
            or os.getenv("OPENAI_RELAY_BASE_URL", "")
        ).rstrip("/"),
        "relay_api_key": str(
            stored.get("api.relay_api_key")
            or os.getenv("OPENAI_RELAY_API_KEY", "")
        ),
        "chat_model": str(
            stored.get("api.chat_model") or os.getenv("OPENAI_CHAT_MODEL", "")
        ),
        "model_list": str(
            stored.get("api.model_list") or os.getenv("OPENAI_MODEL_LIST", "")
        ),
        "registration_enabled": bool(
            stored.get("modules.public_registration_enabled", True)
        ),
        "release_channel": str(stored.get("modes.release_channel") or "stable"),
    }


def _relay_url(base_url: str, path: str) -> str:
    if not base_url:
        raise HTTPException(status_code=503, detail="relay_not_configured")
    return urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))


def _relay_headers(config: dict[str, Any]) -> dict[str, str]:
    key = str(config.get("relay_api_key") or "")
    if not key:
        raise HTTPException(status_code=503, detail="relay_api_key_not_configured")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {"error": {"message": response.text[:500] or "invalid relay response"}}


async def _scope_for_request(
    request: Request,
    *,
    vault_id: str,
) -> tuple[dict[str, Any], MemoryScope, Any]:
    user = await _resolve_lobehub_user(request)
    scope = MemoryScope.account(str(user["id"]), vault_id or "default")
    try:
        policy = await request.app.state.vaults.ensure(scope, allow_create=True)
    except VaultRegistryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc
    return user, scope, policy


async def _remember_after_response(
    request: Request,
    *,
    scope: MemoryScope,
    policy: Any,
    conversation_id: str,
    payload: dict[str, Any],
    assistant_output: str,
) -> None:
    if not assistant_output.strip() or not policy.allows_automatic_cloud_write:
        return
    await request.app.state.memory.remember_exchange(
        scope=scope,
        conversation_id=conversation_id,
        request_payload=payload,
        assistant_text=assistant_output,
    )


async def _stream_chat(
    request: Request,
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    scope: MemoryScope,
    policy: Any,
    conversation_id: str,
) -> AsyncIterator[bytes]:
    chunks: list[str] = []
    timeout = httpx.Timeout(None, connect=30)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code < 200 or response.status_code >= 300:
                    body = await response.aread()
                    message = body.decode("utf-8", errors="replace")[:500]
                    error = json.dumps(
                        {"error": {"message": message or "relay request failed"}},
                        ensure_ascii=False,
                    )
                    yield f"data: {error}\n\n".encode("utf-8")
                    yield b"data: [DONE]\n\n"
                    return
                async for line in response.aiter_lines():
                    if not line:
                        yield b"\n"
                        continue
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        if data and data != "[DONE]":
                            try:
                                envelope = json.loads(data)
                                choices = envelope.get("choices") or []
                                if choices:
                                    delta = choices[0].get("delta") or {}
                                    content = delta.get("content")
                                    if isinstance(content, str):
                                        chunks.append(content)
                            except (ValueError, AttributeError, IndexError):
                                pass
                    yield f"{line}\n".encode("utf-8")
        except httpx.HTTPError as exc:
            error = json.dumps(
                {"error": {"message": f"relay unavailable: {exc}"}},
                ensure_ascii=False,
            )
            yield f"data: {error}\n\n".encode("utf-8")
            yield b"data: [DONE]\n\n"
            return
    try:
        await _remember_after_response(
            request,
            scope=scope,
            policy=policy,
            conversation_id=conversation_id,
            payload=payload,
            assistant_output="".join(chunks),
        )
    except Exception:
        return


def _copy_set_cookie(source: httpx.Response, target: JSONResponse) -> None:
    for value in source.headers.get_list("set-cookie"):
        target.headers.append("set-cookie", value)


def build_client_router() -> APIRouter:
    router = APIRouter(prefix="/api/client", tags=["client"])

    @router.get("/config")
    async def client_config(request: Request) -> dict[str, Any]:
        config = await _runtime_settings(request)
        return {
            "service": "SuMeMe",
            "registration_enabled": config["registration_enabled"],
            "default_model": config["chat_model"],
            "release_channel": config["release_channel"],
            "web_client": "/",
            "admin_console": "/admin/",
        }

    @router.get("/session")
    async def client_session(request: Request) -> dict[str, Any]:
        user = await _resolve_lobehub_user(request)
        return {
            "user": {
                "id": user.get("id"),
                "email": user.get("email"),
                "name": user.get("name") or user.get("fullName") or user.get("username"),
            }
        }

    @router.post("/auth/sign-up/email")
    async def client_signup(body: SignupBody, request: Request) -> JSONResponse:
        _same_origin(request)
        config = await _runtime_settings(request)
        if not config["registration_enabled"]:
            raise HTTPException(status_code=403, detail="registration_disabled")
        base_url = os.getenv("LOBEHUB_INTERNAL_URL", "http://lobe:3210").rstrip("/")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Forwarded-Host": request.headers.get("host", ""),
            "X-Forwarded-Proto": request.url.scheme,
        }
        response = await request.app.state.http.post(
            f"{base_url}/api/auth/sign-up/email",
            headers=headers,
            json=body.model_dump(),
        )
        result = JSONResponse(status_code=response.status_code, content=_safe_json(response))
        _copy_set_cookie(response, result)
        return result

    @router.get("/models")
    async def client_models(request: Request) -> JSONResponse:
        await _resolve_lobehub_user(request)
        config = await _runtime_settings(request)
        configured = [
            item.strip()
            for item in str(config["model_list"]).split(",")
            if item.strip()
        ]
        if configured:
            return JSONResponse(
                content={"data": [{"id": item, "object": "model"} for item in configured]}
            )
        try:
            response = await request.app.state.http.get(
                _relay_url(config["relay_base_url"], "/models"),
                headers=_relay_headers(config),
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"relay unavailable: {exc}") from exc
        return JSONResponse(status_code=response.status_code, content=_safe_json(response))

    @router.post("/chat/completions")
    async def client_chat(body: ClientChatBody, request: Request):
        _same_origin(request)
        if not body.messages:
            raise HTTPException(status_code=400, detail="messages_required")
        user, scope, policy = await _scope_for_request(request, vault_id=body.vault_id)
        config = await _runtime_settings(request)
        model = body.model.strip() or str(config["chat_model"])
        if not model:
            raise HTTPException(status_code=503, detail="chat_model_not_configured")
        payload: dict[str, Any] = {
            "model": model,
            "messages": body.messages,
            "stream": body.stream,
            "user": str(user["id"]),
            "metadata": {
                "vault_id": scope.vault_id,
                "conversation_id": safe_id(
                    body.conversation_id or uuid.uuid4().hex,
                    "client-chat",
                ),
                "source": "sumeme-native-client",
            },
        }
        latest = latest_user_message(body.messages)
        query = flatten_content((latest or {}).get("content"))
        memory_context = ""
        if body.memory_enabled and policy.allows_cloud_recall:
            memory_context = await request.app.state.memory.recall(query, scope)
        enriched = request.app.state.memory.inject_context(payload, memory_context)
        url = _relay_url(config["relay_base_url"], "/chat/completions")
        headers = _relay_headers(config)
        conversation_id = str(payload["metadata"]["conversation_id"])
        if body.stream:
            return StreamingResponse(
                _stream_chat(
                    request,
                    url=url,
                    headers=headers,
                    payload=enriched,
                    scope=scope,
                    policy=policy,
                    conversation_id=conversation_id,
                ),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        try:
            response = await request.app.state.http.post(url, headers=headers, json=enriched)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"relay unavailable: {exc}") from exc
        data = _safe_json(response)
        if 200 <= response.status_code < 300:
            asyncio.create_task(
                _remember_after_response(
                    request,
                    scope=scope,
                    policy=policy,
                    conversation_id=conversation_id,
                    payload=payload,
                    assistant_output=assistant_text(data),
                )
            )
        return JSONResponse(status_code=response.status_code, content=data)

    @router.get("/releases/{platform}")
    async def client_release(
        platform: str,
        request: Request,
        channel: str = Query(default="stable", max_length=20),
    ) -> dict[str, Any]:
        platform_value = platform.strip().lower()
        channel_value = channel.strip().lower()
        if platform_value not in {"android", "windows"}:
            raise HTTPException(status_code=404, detail="unsupported_platform")
        release = await _store(request).get_release(platform_value, channel_value)
        if release is None and channel_value == "stable":
            base = "https://github.com/b8vipvip/sumeme/releases/download/v0.5.0"
            filename = (
                "SuMeMe-Android-0.5.0.apk"
                if platform_value == "android"
                else "SuMeMe-Windows-0.5.0-Setup.exe"
            )
            release = {
                "platform": platform_value,
                "channel": channel_value,
                "latest_version": "0.5.0",
                "minimum_version": "0.4.0",
                "download_url": f"{base}/{filename}",
                "notes": (
                    "全新单对话客户端：历史跨重启常驻、隐藏历史模式、"
                    "聊天与记忆检索、附件上传和带时间轴的资料库。"
                ),
                "published_at": "",
            }
        if release is None:
            return {
                "platform": platform_value,
                "channel": channel_value,
                "available": False,
            }
        return {
            "available": True,
            "platform": release["platform"],
            "channel": release["channel"],
            "version": release["latest_version"],
            "minimum_version": release.get("minimum_version", ""),
            "build_number": 0,
            "download_url": release["download_url"],
            "notes": release.get("notes", ""),
            "published_at": release.get("published_at", ""),
            "mandatory": False,
        }

    return router
