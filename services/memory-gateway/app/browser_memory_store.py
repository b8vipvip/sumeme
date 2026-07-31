from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import anyio
import httpx

from .config import Settings
from .content import flatten_content, latest_user_message
from .memory_result import MemoryOperationError
from .memory_scope import MemoryScope


class BrowserMemoryStore:
    """Account-scoped browser operations for MemPalace verbatim drawers.

    The existing MemPalace store remains the writer and semantic-search source.
    This class only exposes bounded list/detail/stat/delete operations over the
    same SQLite registry. Every query includes the canonical account + Vault
    scope, so a browser-supplied drawer id can never cross namespaces.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.db_path = Path(settings.mempalace_remote_db_path)

    async def initialize(self) -> None:
        await anyio.to_thread.run_sync(self._initialize_sync)

    async def list_drawers(
        self,
        scope: MemoryScope,
        *,
        limit: int = 50,
        offset: int = 0,
        query: str = "",
        role: str = "",
        conversation_id: str = "",
    ) -> dict[str, Any]:
        await self.initialize()
        bounded_limit = max(1, min(int(limit), 100))
        bounded_offset = max(0, int(offset))
        return await anyio.to_thread.run_sync(
            self._list_drawers_sync,
            scope,
            bounded_limit,
            bounded_offset,
            query.strip(),
            role.strip(),
            conversation_id.strip(),
        )

    async def get_drawer(self, scope: MemoryScope, drawer_id: str) -> dict[str, Any] | None:
        await self.initialize()
        return await anyio.to_thread.run_sync(
            self._get_drawer_sync,
            scope,
            drawer_id,
        )

    async def stats(self, scope: MemoryScope) -> dict[str, Any]:
        await self.initialize()
        return await anyio.to_thread.run_sync(self._stats_sync, scope)

    async def delete_drawer(self, scope: MemoryScope, drawer_id: str) -> bool:
        await self.initialize()
        record = await anyio.to_thread.run_sync(
            self._get_delete_target_sync,
            scope,
            drawer_id,
        )
        if record is None:
            return False

        point_id = str(record["point_id"])
        if self.settings.mempalace_enabled:
            await self._delete_qdrant_point(point_id)

        deleted = await anyio.to_thread.run_sync(
            self._delete_drawer_sync,
            scope,
            drawer_id,
        )
        return deleted > 0

    async def _delete_qdrant_point(self, point_id: str) -> None:
        url = (
            f"{self.settings.mempalace_qdrant_url.rstrip('/')}"
            f"/collections/{self.settings.mempalace_collection_name}/points/delete?wait=true"
        )
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.settings.mempalace_qdrant_timeout_seconds)
            ) as client:
                response = await client.post(url, json={"points": [point_id]})
        except httpx.TimeoutException as exc:
            raise MemoryOperationError("mempalace_qdrant_timeout") from exc
        except httpx.HTTPError as exc:
            raise MemoryOperationError("mempalace_qdrant_unavailable") from exc

        if response.status_code == 404:
            # The vector collection can be rebuilt from new writes. A missing
            # collection must not prevent a user from deleting the verbatim row.
            return
        if response.status_code in {401, 403}:
            raise MemoryOperationError("mempalace_qdrant_auth_failed")
        if response.status_code == 429:
            raise MemoryOperationError("mempalace_qdrant_rate_limited")
        if response.status_code >= 500:
            raise MemoryOperationError("mempalace_qdrant_server_error")
        if response.status_code >= 400:
            raise MemoryOperationError("mempalace_qdrant_delete_rejected")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize_sync(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mempalace_drawers (
                    drawer_id TEXT PRIMARY KEY,
                    point_id TEXT NOT NULL UNIQUE,
                    principal_type TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    vault_id TEXT NOT NULL,
                    wing TEXT NOT NULL,
                    room TEXT NOT NULL,
                    role TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS mempalace_drawers_scope_idx
                ON mempalace_drawers (
                    principal_type, account_id, vault_id, created_at DESC
                )
                """
            )

    @staticmethod
    def _scope_where(scope: MemoryScope) -> tuple[str, list[Any]]:
        return (
            "principal_type = ? AND account_id = ? AND vault_id = ?",
            [scope.principal_type, scope.account_id, scope.vault_id],
        )

    def _list_drawers_sync(
        self,
        scope: MemoryScope,
        limit: int,
        offset: int,
        query: str,
        role: str,
        conversation_id: str,
    ) -> dict[str, Any]:
        where, params = self._scope_where(scope)
        clauses = [where]
        if query:
            clauses.append("(content LIKE ? ESCAPE '\\' OR source LIKE ? ESCAPE '\\')")
            escaped = self._like_pattern(query)
            params.extend([escaped, escaped])
        if role in {"user", "assistant"}:
            clauses.append("role = ?")
            params.append(role)
        if conversation_id:
            clauses.append("conversation_id = ?")
            params.append(conversation_id)
        predicate = " AND ".join(clauses)

        with self._connect() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM mempalace_drawers WHERE {predicate}",
                    params,
                ).fetchone()[0]
            )
            rows = connection.execute(
                f"""
                SELECT drawer_id, point_id, wing, room, role, conversation_id,
                       source, content, content_hash, created_at
                FROM mempalace_drawers
                WHERE {predicate}
                ORDER BY created_at DESC, drawer_id DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()

        return {
            "items": [self._present_row(row, include_content=False) for row in rows],
            "limit": limit,
            "offset": offset,
            "total": total,
            "has_more": offset + len(rows) < total,
        }

    def _get_drawer_sync(
        self,
        scope: MemoryScope,
        drawer_id: str,
    ) -> dict[str, Any] | None:
        where, params = self._scope_where(scope)
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT drawer_id, point_id, wing, room, role, conversation_id,
                       source, content, content_hash, created_at
                FROM mempalace_drawers
                WHERE {where} AND drawer_id = ?
                LIMIT 1
                """,
                [*params, drawer_id],
            ).fetchone()
        return self._present_row(row, include_content=True) if row else None

    def _stats_sync(self, scope: MemoryScope) -> dict[str, Any]:
        where, params = self._scope_where(scope)
        with self._connect() as connection:
            aggregate = connection.execute(
                f"""
                SELECT COUNT(*) AS total,
                       COALESCE(SUM(LENGTH(CAST(content AS BLOB))), 0) AS bytes,
                       COUNT(DISTINCT conversation_id) AS conversations,
                       MAX(created_at) AS latest_at
                FROM mempalace_drawers
                WHERE {where}
                """,
                params,
            ).fetchone()
            role_rows = connection.execute(
                f"""
                SELECT role, COUNT(*) AS count
                FROM mempalace_drawers
                WHERE {where}
                GROUP BY role
                """,
                params,
            ).fetchall()

        return {
            "bytes": int(aggregate["bytes"] or 0),
            "conversations": int(aggregate["conversations"] or 0),
            "latest_at": aggregate["latest_at"],
            "roles": {str(row["role"]): int(row["count"]) for row in role_rows},
            "total": int(aggregate["total"] or 0),
        }

    def _get_delete_target_sync(
        self,
        scope: MemoryScope,
        drawer_id: str,
    ) -> sqlite3.Row | None:
        where, params = self._scope_where(scope)
        with self._connect() as connection:
            return connection.execute(
                f"""
                SELECT drawer_id, point_id
                FROM mempalace_drawers
                WHERE {where} AND drawer_id = ?
                LIMIT 1
                """,
                [*params, drawer_id],
            ).fetchone()

    def _delete_drawer_sync(
        self,
        scope: MemoryScope,
        drawer_id: str,
    ) -> int:
        where, params = self._scope_where(scope)
        with self._connect() as connection:
            cursor = connection.execute(
                f"DELETE FROM mempalace_drawers WHERE {where} AND drawer_id = ?",
                [*params, drawer_id],
            )
            return int(cursor.rowcount)

    @staticmethod
    def _like_pattern(query: str) -> str:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"

    @classmethod
    def _present_row(
        cls,
        row: sqlite3.Row,
        *,
        include_content: bool,
    ) -> dict[str, Any]:
        raw_content = str(row["content"])
        parsed = cls._parse_content(raw_content)
        text = cls._content_text(parsed, raw_content)
        item = {
            "content_hash": str(row["content_hash"]),
            "conversation_id": str(row["conversation_id"]),
            "created_at": str(row["created_at"]),
            "drawer_id": str(row["drawer_id"]),
            "point_id": str(row["point_id"]),
            "preview": text[:500],
            "role": str(row["role"]),
            "room": str(row["room"]),
            "source": str(row["source"]),
            "wing": str(row["wing"]),
        }
        if include_content:
            item["content"] = parsed
            item["text"] = text
        return item

    @staticmethod
    def _parse_content(content: str) -> Any:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return content

    @staticmethod
    def _content_text(parsed: Any, fallback: str) -> str:
        if isinstance(parsed, dict):
            role = str(parsed.get("role") or "")
            if role == "assistant":
                return flatten_content(parsed.get("content")) or fallback
            request_payload = parsed.get("request")
            if isinstance(request_payload, dict):
                latest = latest_user_message(request_payload.get("messages") or [])
                text = flatten_content((latest or {}).get("content"))
                if text:
                    return text
            if "content" in parsed:
                return flatten_content(parsed.get("content")) or fallback
        return flatten_content(parsed) or fallback
