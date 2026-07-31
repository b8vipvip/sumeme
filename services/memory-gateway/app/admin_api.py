from __future__ import annotations

import os
from typing import Any, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from .admin_store import AdminSession, AdminStore


ADMIN_COOKIE = "sumeme_admin_session"
_SECRET_KEYS = {
    "api.relay_api_key",
    "storage.access_key",
    "storage.secret_key",
}
_ALLOWED_SETTINGS = {
    "api.relay_base_url",
    "api.relay_api_key",
    "api.chat_model",
    "api.memory_model",
    "api.embedding_model",
    "api.model_list",
    "storage.endpoint",
    "storage.bucket",
    "storage.private_bucket",
    "storage.region",
    "storage.path_style",
    "storage.access_key",
    "storage.secret_key",
    "modules.mempalace_enabled",
    "modules.letta_enabled",
    "modules.object_api_enabled",
    "modules.searxng_enabled",
    "modules.public_registration_enabled",
    "modes.memory_provider",
    "modes.default_storage_mode",
    "modes.identity_mode",
    "modes.release_channel",
}


class BootstrapBody(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=512)
    display_name: str = Field(default="", max_length=120)


class LoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=512)


class SettingsBody(BaseModel):
    values: dict[str, Any]


class UserUpdateBody(BaseModel):
    role: Literal["user", "admin"] | None = None
    banned: bool | None = None
    ban_reason: str | None = Field(default=None, max_length=500)


class ReleaseBody(BaseModel):
    platform: Literal["android", "windows"]
    channel: Literal["stable", "beta"] = "stable"
    latest_version: str = Field(min_length=1, max_length=80)
    minimum_version: str = Field(default="", max_length=80)
    download_url: str = Field(min_length=8, max_length=2048)
    notes: str = Field(default="", max_length=10000)


def _store(request: Request) -> AdminStore:
    return request.app.state.admin_store


def _same_origin(request: Request) -> None:
    origin = request.headers.get("origin", "").strip()
    if not origin:
        return
    parsed = urlparse(origin)
    if parsed.hostname != request.url.hostname:
        raise HTTPException(status_code=403, detail="cross_origin_admin_request")


async def _require_admin(request: Request) -> AdminSession:
    token = request.cookies.get(ADMIN_COOKIE, "")
    session = await _store(request).get_session(token)
    if session is None:
        raise HTTPException(status_code=401, detail="admin_login_required")
    return session


def _set_admin_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        ADMIN_COOKIE,
        token,
        max_age=12 * 60 * 60,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )


def _environment_defaults() -> dict[str, Any]:
    return {
        "api.relay_base_url": os.getenv("OPENAI_RELAY_BASE_URL", ""),
        "api.chat_model": os.getenv("OPENAI_CHAT_MODEL", ""),
        "api.memory_model": os.getenv("OPENAI_MEMORY_MODEL", ""),
        "api.embedding_model": os.getenv("OPENAI_EMBEDDING_MODEL", ""),
        "api.model_list": os.getenv("OPENAI_MODEL_LIST", ""),
        "storage.endpoint": os.getenv("S3_ENDPOINT", ""),
        "storage.bucket": os.getenv("RUSTFS_LOBE_BUCKET", ""),
        "storage.private_bucket": os.getenv("RUSTFS_PRIVATE_BUCKET", "sumeme-vaults"),
        "storage.region": os.getenv("S3_REGION", "auto"),
        "storage.path_style": True,
        "modules.mempalace_enabled": os.getenv("MEMPALACE_ENABLED", "true").lower()
        == "true",
        "modules.letta_enabled": os.getenv("LETTA_ENABLED", "true").lower()
        == "true",
        "modules.object_api_enabled": os.getenv("OBJECT_API_ENABLED", "true").lower()
        == "true",
        "modules.searxng_enabled": True,
        "modules.public_registration_enabled": True,
        "modes.memory_provider": os.getenv("MEMORY_PROVIDER", "mempalace-letta"),
        "modes.default_storage_mode": os.getenv("DEFAULT_STORAGE_MODE", "cloud"),
        "modes.identity_mode": os.getenv("IDENTITY_MODE", "legacy-client-asserted"),
        "modes.release_channel": "stable",
    }


def _validate_setting(key: str, value: Any) -> Any:
    if key not in _ALLOWED_SETTINGS:
        raise HTTPException(status_code=400, detail=f"unsupported_setting:{key}")
    if key.startswith("modules.") or key == "storage.path_style":
        if not isinstance(value, bool):
            raise HTTPException(status_code=400, detail=f"setting_must_be_boolean:{key}")
        return value
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=f"setting_must_be_string:{key}")
    normalized = value.strip()
    if len(normalized) > 10000:
        raise HTTPException(status_code=400, detail=f"setting_too_long:{key}")
    if key == "api.relay_base_url" and normalized:
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=400, detail="invalid_relay_base_url")
    if key == "storage.endpoint" and normalized:
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=400, detail="invalid_storage_endpoint")
    if key == "modes.memory_provider" and normalized not in {
        "mempalace-letta",
        "supermemory",
    }:
        raise HTTPException(status_code=400, detail="invalid_memory_provider")
    if key == "modes.default_storage_mode" and normalized not in {
        "local-only",
        "cloud",
        "hybrid",
    }:
        raise HTTPException(status_code=400, detail="invalid_storage_mode")
    if key == "modes.identity_mode" and normalized not in {
        "legacy-client-asserted",
        "trusted-openai-user",
        "jwt-preferred",
        "jwt-required",
    }:
        raise HTTPException(status_code=400, detail="invalid_identity_mode")
    if key == "modes.release_channel" and normalized not in {"stable", "beta"}:
        raise HTTPException(status_code=400, detail="invalid_release_channel")
    return normalized


def build_admin_router() -> APIRouter:
    router = APIRouter(prefix="/api/admin", tags=["admin"])

    @router.get("/bootstrap/status")
    async def bootstrap_status(request: Request) -> dict[str, bool]:
        return {"initialized": await _store(request).has_admin()}

    @router.post("/bootstrap")
    async def bootstrap(
        body: BootstrapBody,
        request: Request,
        response: Response,
    ) -> dict[str, Any]:
        _same_origin(request)
        try:
            session, token = await _store(request).bootstrap_admin(
                email=body.email,
                password=body.password,
                display_name=body.display_name,
            )
        except ValueError as exc:
            code = str(exc)
            status = 409 if code == "admin_already_initialized" else 400
            raise HTTPException(status_code=status, detail=code) from exc
        _set_admin_cookie(response, token)
        return {"admin": {"email": session.email, "display_name": session.display_name}}

    @router.post("/login")
    async def login(
        body: LoginBody,
        request: Request,
        response: Response,
    ) -> dict[str, Any]:
        _same_origin(request)
        result = await _store(request).authenticate(email=body.email, password=body.password)
        if result is None:
            raise HTTPException(status_code=401, detail="invalid_admin_credentials")
        session, token = result
        _set_admin_cookie(response, token)
        return {
            "admin": {
                "email": session.email,
                "display_name": session.display_name,
                "expires_at": session.expires_at.isoformat(),
            }
        }

    @router.post("/logout")
    async def logout(
        request: Request,
        response: Response,
        session: AdminSession = Depends(_require_admin),
    ) -> dict[str, bool]:
        _same_origin(request)
        token = request.cookies.get(ADMIN_COOKIE, "")
        await _store(request).revoke_session(token, admin_id=session.admin_id)
        response.delete_cookie(ADMIN_COOKIE, path="/")
        return {"ok": True}

    @router.get("/session")
    async def session_info(session: AdminSession = Depends(_require_admin)) -> dict[str, Any]:
        return {
            "admin": {
                "email": session.email,
                "display_name": session.display_name,
                "expires_at": session.expires_at.isoformat(),
            }
        }

    @router.get("/settings")
    async def settings_view(
        request: Request,
        _session: AdminSession = Depends(_require_admin),
    ) -> dict[str, Any]:
        stored = await _store(request).get_settings()
        merged = _environment_defaults()
        merged.update(stored)
        secret_defaults = {
            "api.relay_api_key": bool(os.getenv("OPENAI_RELAY_API_KEY", "")),
            "storage.access_key": bool(os.getenv("RUSTFS_ACCESS_KEY", "")),
            "storage.secret_key": bool(os.getenv("RUSTFS_SECRET_KEY", "")),
        }
        for key in _SECRET_KEYS:
            merged.setdefault(key, {"configured": secret_defaults[key], "masked": ""})
        return {
            "values": merged,
            "restart_required_keys": [
                "storage.endpoint",
                "storage.bucket",
                "storage.private_bucket",
                "storage.region",
                "storage.path_style",
                "storage.access_key",
                "storage.secret_key",
                "modules.letta_enabled",
                "modules.object_api_enabled",
                "modules.searxng_enabled",
                "modes.memory_provider",
                "modes.default_storage_mode",
                "modes.identity_mode",
            ],
        }

    @router.put("/settings")
    async def settings_update(
        body: SettingsBody,
        request: Request,
        session: AdminSession = Depends(_require_admin),
    ) -> dict[str, Any]:
        _same_origin(request)
        values = {key: _validate_setting(key, value) for key, value in body.values.items()}
        await _store(request).update_settings(
            admin_id=session.admin_id,
            values=values,
            secret_keys=_SECRET_KEYS,
        )
        return {
            "ok": True,
            "updated": sorted(values),
            "restart_required": any(
                key.startswith("storage.")
                or key.startswith("modules.")
                or key.startswith("modes.")
                for key in values
            ),
            "runtime_applied": [
                key
                for key in values
                if key.startswith("api.")
                or key == "modules.public_registration_enabled"
                or key == "modes.release_channel"
            ],
        }

    @router.get("/users")
    async def users(
        request: Request,
        search: str = Query(default="", max_length=200),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        _session: AdminSession = Depends(_require_admin),
    ) -> dict[str, Any]:
        try:
            return await _store(request).list_lobe_users(
                search=search,
                limit=limit,
                offset=offset,
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail="user_database_unavailable") from exc

    @router.patch("/users/{user_id}")
    async def user_update(
        user_id: str,
        body: UserUpdateBody,
        request: Request,
        session: AdminSession = Depends(_require_admin),
    ) -> dict[str, Any]:
        _same_origin(request)
        try:
            user = await _store(request).update_lobe_user(
                admin_id=session.admin_id,
                user_id=user_id,
                role=body.role,
                banned=body.banned,
                ban_reason=body.ban_reason,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="user_not_found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"user": user}

    @router.get("/releases")
    async def releases(
        request: Request,
        _session: AdminSession = Depends(_require_admin),
    ) -> dict[str, Any]:
        return {"releases": await _store(request).list_releases()}

    @router.put("/releases")
    async def release_update(
        body: ReleaseBody,
        request: Request,
        session: AdminSession = Depends(_require_admin),
    ) -> dict[str, Any]:
        _same_origin(request)
        try:
            release = await _store(request).upsert_release(
                admin_id=session.admin_id,
                platform=body.platform,
                channel=body.channel,
                latest_version=body.latest_version,
                minimum_version=body.minimum_version,
                download_url=body.download_url,
                notes=body.notes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"release": release}

    @router.get("/audit")
    async def audit(
        request: Request,
        limit: int = Query(default=100, ge=1, le=500),
        _session: AdminSession = Depends(_require_admin),
    ) -> dict[str, Any]:
        return {"events": await _store(request).audit_log(limit)}

    @router.get("/system")
    async def system_status(
        request: Request,
        _session: AdminSession = Depends(_require_admin),
    ) -> dict[str, Any]:
        health = {
            "memory_provider": getattr(request.app.state.memory, "provider_name", "unknown"),
            "vault_registry": "sqlite",
            "objects_enabled": hasattr(request.app.state, "objects"),
            "admin_database": str(_store(request).path),
            "lobe_database_configured": bool(_store(request).lobe_database_url),
        }
        return {"status": "ok", "components": health}

    return router
