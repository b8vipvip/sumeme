from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - surfaced by admin health and CI container build
    psycopg = None
    dict_row = None


_SESSION_TTL = timedelta(hours=12)
_SECRET_PREFIX = "enc:v1:"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None = None) -> str:
    return (value or _utcnow()).isoformat()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _password_digest(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )


@dataclass(frozen=True, slots=True)
class AdminSession:
    admin_id: int
    email: str
    display_name: str
    expires_at: datetime


class AdminStore:
    """Persistent control-plane state stored outside the public client surface."""

    def __init__(
        self,
        path: str,
        *,
        master_secret: str,
        lobe_database_url: str,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        secret = master_secret.strip()
        if not secret:
            raise RuntimeError(
                "SUMEME_ADMIN_MASTER_KEY or GATEWAY_ADMIN_TOKEN is required"
            )
        self._cipher = AESGCM(hashlib.sha256(secret.encode("utf-8")).digest())
        self.lobe_database_url = lobe_database_url.strip()

    async def initialize(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._initialize_sync)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize_sync(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS admin_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT,
                    disabled INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS admin_sessions (
                    token_hash TEXT PRIMARY KEY,
                    admin_id INTEGER NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS admin_sessions_admin_id_idx
                    ON admin_sessions(admin_id);
                CREATE INDEX IF NOT EXISTS admin_sessions_expires_idx
                    ON admin_sessions(expires_at);
                CREATE TABLE IF NOT EXISTS system_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    is_secret INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS release_channels (
                    platform TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    latest_version TEXT NOT NULL,
                    minimum_version TEXT NOT NULL DEFAULT '',
                    download_url TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    published_at TEXT NOT NULL,
                    PRIMARY KEY(platform, channel)
                );
                CREATE TABLE IF NOT EXISTS admin_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER,
                    action TEXT NOT NULL,
                    target TEXT NOT NULL,
                    detail_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            connection.execute(
                "DELETE FROM admin_sessions WHERE expires_at <= ?",
                (_iso(),),
            )

    async def has_admin(self) -> bool:
        async with self._lock:
            return await asyncio.to_thread(self._has_admin_sync)

    def _has_admin_sync(self) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM admin_users WHERE disabled = 0 LIMIT 1"
            ).fetchone()
            return row is not None

    async def bootstrap_admin(
        self,
        *,
        email: str,
        password: str,
        display_name: str,
    ) -> tuple[AdminSession, str]:
        normalized = _normalize_email(email)
        if "@" not in normalized:
            raise ValueError("invalid_email")
        if len(password) < 12:
            raise ValueError("password_too_short")
        if len(password) > 512:
            raise ValueError("password_too_long")
        name = display_name.strip() or normalized.split("@", 1)[0]
        async with self._lock:
            return await asyncio.to_thread(
                self._bootstrap_admin_sync,
                normalized,
                password,
                name[:120],
            )

    def _bootstrap_admin_sync(
        self,
        email: str,
        password: str,
        display_name: str,
    ) -> tuple[AdminSession, str]:
        salt = secrets.token_bytes(16)
        digest = _password_digest(password, salt)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT 1 FROM admin_users LIMIT 1"
            ).fetchone()
            if existing is not None:
                raise ValueError("admin_already_initialized")
            cursor = connection.execute(
                """
                INSERT INTO admin_users(
                    email, display_name, password_hash, password_salt, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    email,
                    display_name,
                    base64.b64encode(digest).decode("ascii"),
                    base64.b64encode(salt).decode("ascii"),
                    _iso(),
                ),
            )
            admin_id = int(cursor.lastrowid)
            token, session = self._create_session_sync(
                connection,
                admin_id=admin_id,
                email=email,
                display_name=display_name,
            )
            self._audit_sync(
                connection,
                admin_id,
                "admin.bootstrap",
                email,
                {"display_name": display_name},
            )
            return session, token

    async def authenticate(
        self,
        *,
        email: str,
        password: str,
    ) -> tuple[AdminSession, str] | None:
        normalized = _normalize_email(email)
        async with self._lock:
            return await asyncio.to_thread(
                self._authenticate_sync,
                normalized,
                password,
            )

    def _authenticate_sync(
        self,
        email: str,
        password: str,
    ) -> tuple[AdminSession, str] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, email, display_name, password_hash, password_salt
                FROM admin_users
                WHERE email = ? AND disabled = 0
                """,
                (email,),
            ).fetchone()
            if row is None:
                _password_digest(password, secrets.token_bytes(16))
                return None
            salt = base64.b64decode(row["password_salt"])
            expected = base64.b64decode(row["password_hash"])
            supplied = _password_digest(password, salt)
            if not hmac.compare_digest(expected, supplied):
                return None
            connection.execute(
                "UPDATE admin_users SET last_login_at = ? WHERE id = ?",
                (_iso(), row["id"]),
            )
            token, session = self._create_session_sync(
                connection,
                admin_id=int(row["id"]),
                email=str(row["email"]),
                display_name=str(row["display_name"]),
            )
            self._audit_sync(
                connection,
                int(row["id"]),
                "admin.login",
                str(row["email"]),
                {},
            )
            return session, token

    def _create_session_sync(
        self,
        connection: sqlite3.Connection,
        *,
        admin_id: int,
        email: str,
        display_name: str,
    ) -> tuple[str, AdminSession]:
        token = secrets.token_urlsafe(48)
        expires_at = _utcnow() + _SESSION_TTL
        connection.execute(
            """
            INSERT INTO admin_sessions(token_hash, admin_id, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (_hash_token(token), admin_id, _iso(), _iso(expires_at)),
        )
        return token, AdminSession(
            admin_id=admin_id,
            email=email,
            display_name=display_name,
            expires_at=expires_at,
        )

    async def get_session(self, token: str) -> AdminSession | None:
        if not token:
            return None
        async with self._lock:
            return await asyncio.to_thread(self._get_session_sync, token)

    def _get_session_sync(self, token: str) -> AdminSession | None:
        now = _utcnow()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT u.id, u.email, u.display_name, s.expires_at
                FROM admin_sessions s
                JOIN admin_users u ON u.id = s.admin_id
                WHERE s.token_hash = ? AND s.expires_at > ? AND u.disabled = 0
                """,
                (_hash_token(token), _iso(now)),
            ).fetchone()
            if row is None:
                return None
            return AdminSession(
                admin_id=int(row["id"]),
                email=str(row["email"]),
                display_name=str(row["display_name"]),
                expires_at=datetime.fromisoformat(str(row["expires_at"])),
            )

    async def revoke_session(self, token: str, *, admin_id: int | None = None) -> None:
        if not token:
            return
        async with self._lock:
            await asyncio.to_thread(self._revoke_session_sync, token, admin_id)

    def _revoke_session_sync(self, token: str, admin_id: int | None) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM admin_sessions WHERE token_hash = ?",
                (_hash_token(token),),
            )
            self._audit_sync(connection, admin_id, "admin.logout", "session", {})

    def _encrypt(self, value: str) -> str:
        nonce = secrets.token_bytes(12)
        ciphertext = self._cipher.encrypt(nonce, value.encode("utf-8"), b"sumeme-admin")
        return _SECRET_PREFIX + base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")

    def _decrypt(self, value: str) -> str:
        if not value.startswith(_SECRET_PREFIX):
            return value
        raw = base64.urlsafe_b64decode(value[len(_SECRET_PREFIX) :])
        return self._cipher.decrypt(raw[:12], raw[12:], b"sumeme-admin").decode("utf-8")

    async def get_settings(self, *, include_secrets: bool = False) -> dict[str, Any]:
        async with self._lock:
            return await asyncio.to_thread(self._get_settings_sync, include_secrets)

    def _get_settings_sync(self, include_secrets: bool) -> dict[str, Any]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT key, value_json, is_secret FROM system_settings"
            ).fetchall()
        values: dict[str, Any] = {}
        for row in rows:
            raw = json.loads(str(row["value_json"]))
            if bool(row["is_secret"]):
                if include_secrets:
                    values[str(row["key"])] = self._decrypt(str(raw))
                else:
                    values[str(row["key"])] = {"configured": True, "masked": ""}
            else:
                values[str(row["key"])] = raw
        return values

    async def update_settings(
        self,
        *,
        admin_id: int,
        values: dict[str, Any],
        secret_keys: set[str],
    ) -> None:
        async with self._lock:
            await asyncio.to_thread(
                self._update_settings_sync,
                admin_id,
                values,
                secret_keys,
            )

    def _update_settings_sync(
        self,
        admin_id: int,
        values: dict[str, Any],
        secret_keys: set[str],
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for key, value in values.items():
                is_secret = key in secret_keys
                if is_secret and value in (None, ""):
                    continue
                stored: Any = self._encrypt(str(value)) if is_secret else value
                connection.execute(
                    """
                    INSERT INTO system_settings(key, value_json, is_secret, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value_json = excluded.value_json,
                        is_secret = excluded.is_secret,
                        updated_at = excluded.updated_at
                    """,
                    (key, json.dumps(stored), 1 if is_secret else 0, _iso()),
                )
            self._audit_sync(
                connection,
                admin_id,
                "settings.update",
                "system",
                {"keys": sorted(values)},
            )

    async def get_release(self, platform: str, channel: str) -> dict[str, str] | None:
        async with self._lock:
            return await asyncio.to_thread(
                self._get_release_sync,
                platform,
                channel,
            )

    def _get_release_sync(self, platform: str, channel: str) -> dict[str, str] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT platform, channel, latest_version, minimum_version,
                       download_url, notes, published_at
                FROM release_channels
                WHERE platform = ? AND channel = ?
                """,
                (platform, channel),
            ).fetchone()
            return dict(row) if row is not None else None

    async def list_releases(self) -> list[dict[str, str]]:
        async with self._lock:
            return await asyncio.to_thread(self._list_releases_sync)

    def _list_releases_sync(self) -> list[dict[str, str]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT platform, channel, latest_version, minimum_version,
                       download_url, notes, published_at
                FROM release_channels
                ORDER BY platform, channel
                """
            ).fetchall()
            return [dict(row) for row in rows]

    async def upsert_release(
        self,
        *,
        admin_id: int,
        platform: str,
        channel: str,
        latest_version: str,
        minimum_version: str,
        download_url: str,
        notes: str,
    ) -> dict[str, str]:
        platform_value = platform.strip().lower()
        channel_value = channel.strip().lower()
        if platform_value not in {"android", "windows"}:
            raise ValueError("invalid_platform")
        if channel_value not in {"stable", "beta"}:
            raise ValueError("invalid_channel")
        if not latest_version.strip() or not download_url.strip().startswith("https://"):
            raise ValueError("invalid_release")
        async with self._lock:
            return await asyncio.to_thread(
                self._upsert_release_sync,
                admin_id,
                platform_value,
                channel_value,
                latest_version.strip(),
                minimum_version.strip(),
                download_url.strip(),
                notes.strip(),
            )

    def _upsert_release_sync(
        self,
        admin_id: int,
        platform: str,
        channel: str,
        latest_version: str,
        minimum_version: str,
        download_url: str,
        notes: str,
    ) -> dict[str, str]:
        published_at = _iso()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO release_channels(
                    platform, channel, latest_version, minimum_version,
                    download_url, notes, published_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, channel) DO UPDATE SET
                    latest_version = excluded.latest_version,
                    minimum_version = excluded.minimum_version,
                    download_url = excluded.download_url,
                    notes = excluded.notes,
                    published_at = excluded.published_at
                """,
                (
                    platform,
                    channel,
                    latest_version,
                    minimum_version,
                    download_url,
                    notes,
                    published_at,
                ),
            )
            self._audit_sync(
                connection,
                admin_id,
                "release.update",
                f"{platform}/{channel}",
                {"version": latest_version, "url": download_url},
            )
        return {
            "platform": platform,
            "channel": channel,
            "latest_version": latest_version,
            "minimum_version": minimum_version,
            "download_url": download_url,
            "notes": notes,
            "published_at": published_at,
        }

    async def list_lobe_users(
        self,
        *,
        search: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        if psycopg is None or not self.lobe_database_url:
            return {"users": [], "total": 0, "available": False}
        query = search.strip()
        pattern = f"%{query}%"
        async with await psycopg.AsyncConnection.connect(
            self.lobe_database_url,
            row_factory=dict_row,
        ) as connection:
            where = ""
            params: list[Any] = []
            if query:
                where = (
                    "WHERE COALESCE(email, '') ILIKE %s "
                    "OR COALESCE(username, '') ILIKE %s "
                    "OR COALESCE(full_name, '') ILIKE %s"
                )
                params.extend([pattern, pattern, pattern])
            async with connection.cursor() as cursor:
                await cursor.execute(f"SELECT COUNT(*) AS total FROM users {where}", params)
                count_row = await cursor.fetchone()
                await cursor.execute(
                    f"""
                    SELECT u.id, u.email, u.username, u.full_name, u.role,
                           u.banned, u.ban_reason, u.created_at, u.last_active_at,
                           COALESCE((
                               SELECT COUNT(*) FROM auth_sessions s
                               WHERE s.user_id = u.id AND s.expires_at > NOW()
                           ), 0) AS active_sessions
                    FROM users u
                    {where}
                    ORDER BY u.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    [*params, max(1, min(limit, 200)), max(0, offset)],
                )
                rows = await cursor.fetchall()
        return {
            "users": [self._serialize_user(row) for row in rows],
            "total": int((count_row or {}).get("total", 0)),
            "available": True,
        }

    async def update_lobe_user(
        self,
        *,
        admin_id: int,
        user_id: str,
        role: str | None,
        banned: bool | None,
        ban_reason: str | None,
    ) -> dict[str, Any]:
        if psycopg is None or not self.lobe_database_url:
            raise RuntimeError("lobe_database_unavailable")
        updates: list[str] = []
        values: list[Any] = []
        if role is not None:
            normalized_role = role.strip().lower()
            if normalized_role not in {"user", "admin"}:
                raise ValueError("invalid_role")
            updates.append("role = %s")
            values.append(normalized_role)
        if banned is not None:
            updates.append("banned = %s")
            values.append(bool(banned))
            updates.append("ban_reason = %s")
            values.append((ban_reason or "").strip() or None)
            if not banned:
                updates.append("ban_expires = NULL")
        if not updates:
            raise ValueError("no_changes")
        values.append(user_id)
        async with await psycopg.AsyncConnection.connect(
            self.lobe_database_url,
            row_factory=dict_row,
        ) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    f"""
                    UPDATE users
                    SET {', '.join(updates)}, updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, email, username, full_name, role, banned,
                              ban_reason, created_at, last_active_at
                    """,
                    values,
                )
                row = await cursor.fetchone()
                if row is None:
                    raise LookupError("user_not_found")
                if banned:
                    await cursor.execute(
                        "DELETE FROM auth_sessions WHERE user_id = %s",
                        (user_id,),
                    )
            await connection.commit()
        async with self._lock:
            await asyncio.to_thread(
                self._audit_only_sync,
                admin_id,
                "user.update",
                user_id,
                {"role": role, "banned": banned, "ban_reason": ban_reason},
            )
        serialized = self._serialize_user(row)
        serialized["active_sessions"] = 0 if banned else None
        return serialized

    def _serialize_user(self, row: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, datetime):
                result[key] = value.astimezone(UTC).isoformat()
            else:
                result[key] = value
        return result

    def _audit_only_sync(
        self,
        admin_id: int,
        action: str,
        target: str,
        detail: dict[str, Any],
    ) -> None:
        with self._connect() as connection:
            self._audit_sync(connection, admin_id, action, target, detail)

    def _audit_sync(
        self,
        connection: sqlite3.Connection,
        admin_id: int | None,
        action: str,
        target: str,
        detail: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO admin_audit_log(
                admin_id, action, target, detail_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (admin_id, action, target, json.dumps(detail), _iso()),
        )

    async def audit_log(self, limit: int = 100) -> list[dict[str, Any]]:
        async with self._lock:
            return await asyncio.to_thread(self._audit_log_sync, limit)

    def _audit_log_sync(self, limit: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT a.id, a.action, a.target, a.detail_json, a.created_at,
                       u.email AS admin_email
                FROM admin_audit_log a
                LEFT JOIN admin_users u ON u.id = a.admin_id
                ORDER BY a.id DESC
                LIMIT ?
                """,
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "action": str(row["action"]),
                "target": str(row["target"]),
                "detail": json.loads(str(row["detail_json"])),
                "created_at": str(row["created_at"]),
                "admin_email": row["admin_email"],
            }
            for row in rows
        ]


def admin_store_from_environment() -> AdminStore:
    path = os.getenv("SUMEME_ADMIN_DB_PATH", "/data/gateway/admin.sqlite3")
    master_secret = os.getenv("SUMEME_ADMIN_MASTER_KEY", "") or os.getenv(
        "GATEWAY_ADMIN_TOKEN", ""
    )
    lobe_database_url = os.getenv("LOBE_DATABASE_URL", "")
    return AdminStore(
        path,
        master_secret=master_secret,
        lobe_database_url=lobe_database_url,
    )
