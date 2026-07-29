from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .config import get_settings
from .content import assistant_text, flatten_content, latest_user_message, safe_id
from .memory import MemoryCoordinator

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
    yield
    await app.state.http.aclose()


app = FastAPI(title="SuMeMe Memory Gateway", version="0.1.0", lifespan=lifespan)


def require_gateway_auth(authorization: str | None) -> None:
    expected = settings.gateway_api_key.get_secret_value()
    supplied = ""
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    if not expected or supplied != expected:
        raise HTTPException(status_code=401, detail="invalid gateway token")


def require_admin_auth(authorization: str | None) -> None:
    expected = settings.gateway_admin_token.get_secret_value()
    supplied = ""
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    if not expected or supplied != expected:
        raise HTTPException(status_code=401, detail="invalid admin token")


def relay_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.openai_relay_api_key.get_secret_value()}",
        "Content-Type": "application/json",
    }


def resolve_user_id(request: Request, payload: dict[str, Any]) -> str:
    return safe_id(
        request.headers.get("x-sumeme-user-id")
        or str(payload.get("user") or "")
        or settings.sumeme_user_id
    )


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
    return {
        "status": "ok",
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

    user_id = resolve_user_id(request, payload)
    conversation_id = resolve_conversation_id(request, payload)
    latest = latest_user_message(messages)
    query = flatten_content((latest or {}).get("content"))

    memory_context = await app.state.memory.recall(query, user_id)
    enriched = app.state.memory.inject_context(payload, memory_context)

    if payload.get("stream"):
        return StreamingResponse(
            _stream_relay(
                request_payload=payload,
                enriched_payload=enriched,
                user_id=user_id,
                conversation_id=conversation_id,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
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
    if 200 <= response.status_code < 300:
        asyncio.create_task(
            app.state.memory.remember_exchange(
                user_id=user_id,
                conversation_id=conversation_id,
                request_payload=payload,
                assistant_text=assistant_text(data),
            )
        )
    return JSONResponse(
        status_code=response.status_code,
        content=data,
        headers=_safe_response_headers(response),
    )


@app.post("/api/memory/search")
async def memory_search(
    request: Request,
    authorization: str | None = Header(default=None),
):
    require_admin_auth(authorization)
    body = await request.json()
    query = str(body.get("query") or "")
    user_id = safe_id(str(body.get("user_id") or settings.sumeme_user_id))
    return {"context": await app.state.memory.recall(query, user_id)}


async def _stream_relay(
    *,
    request_payload: dict[str, Any],
    enriched_payload: dict[str, Any],
    user_id: str,
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

    asyncio.create_task(
        app.state.memory.remember_exchange(
            user_id=user_id,
            conversation_id=conversation_id,
            request_payload=request_payload,
            assistant_text="".join(assistant_parts),
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
    except Exception:
        return


def _json_or_error(response: httpx.Response) -> dict[str, Any]:
    try:
        value = response.json()
        if isinstance(value, dict):
            return value
        return {"data": value}
    except Exception:
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
