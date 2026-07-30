from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import anyio
import httpx

from .config import Settings
from .content import flatten_content, latest_user_message, safe_id
from .memory_deadlines import MemoryDeadlines
from .memory_result import MemoryOperationError
from .memory_scope import MemoryScope, coerce_scope
from .remote_embeddings import RemoteEmbeddingClient

logger = logging.getLogger(__name__)


class MemPalaceStore:
    """Remote-AI raw memory store with MemPalace wing/room semantics.

    Verbatim drawers live in SQLite. Search vectors live in Qdrant and contain
    only scope metadata plus a drawer identifier. Embeddings are always produced
    by the configured OpenAI-compatible relay; this class never imports or falls
    back to MemPalace's local ONNX embedding implementation.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.deadlines = MemoryDeadlines.from_environment()
        self._db_path = Path(settings.mempalace_remote_db_path)
        self._embedding = RemoteEmbeddingClient(settings)
        self._qdrant = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.mempalace_qdrant_timeout_seconds),
            follow_redirects=True,
        )
        self._initialize_lock = asyncio.Lock()
        self._collection_lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        async with self._initialize_lock:
            if self._initialized:
                return
            await anyio.to_thread.run_sync(self._initialize_sync)
            self._initialized = True

    async def search(
        self,
        query: str,
        scope: MemoryScope | str,
    ) -> list[dict[str, Any]]:
        if not self.settings.mempalace_enabled or not query.strip():
            return []

        await self.initialize()
        resolved = coerce_scope(scope, default_user_id=self.settings.sumeme_user_id)
        vector = (
            await self._embedding.embed(
                [query[: self.settings.mempalace_embedding_max_chars]],
                timeout_seconds=self.deadlines.recall_seconds,
            )
        )[0]
        await self._ensure_collection(len(vector))

        response = await self._qdrant_request(
            "POST",
            f"/collections/{self.settings.mempalace_collection_name}/points/query",
            json_body={
                "query": vector,
                "filter": {
                    "must": [
                        {
                            "key": "scope_key",
                            "match": {"value": resolved.storage_key},
                        }
                    ]
                },
                "limit": self.settings.mempalace_recall_limit,
                "with_payload": True,
                "with_vector": False,
            },
            operation="query",
        )
        points = self._query_points(response)
        ordered_ids: list[str] = []
        scores: dict[str, float] = {}
        for point in points:
            if not isinstance(point, dict):
                continue
            payload = point.get("payload")
            if not isinstance(payload, dict):
                continue
            drawer_id = str(payload.get("drawer_id") or "")
            if not drawer_id or drawer_id in scores:
                continue
            try:
                score = float(point.get("score") or 0)
            except (TypeError, ValueError):
                score = 0.0
            ordered_ids.append(drawer_id)
            scores[drawer_id] = score

        if not ordered_ids:
            return []
        rows = await anyio.to_thread.run_sync(
            self._read_drawers_sync,
            resolved,
            ordered_ids,
        )
        by_id = {str(row["drawer_id"]): row for row in rows}
        results: list[dict[str, Any]] = []
        for drawer_id in ordered_ids:
            row = by_id.get(drawer_id)
            if row is None:
                continue
            results.append(
                {
                    "wing": str(row["wing"]),
                    "room": str(row["room"]),
                    "text": str(row["content"]),
                    "similarity": scores.get(drawer_id, 0.0),
                    "drawer_id": drawer_id,
                }
            )
        return results[: self.settings.mempalace_recall_limit]

    async def add_exchange(
        self,
        *,
        scope: MemoryScope | str,
        conversation_id: str,
        request_payload: dict[str, Any],
        assistant: str,
    ) -> bool:
        if not self.settings.mempalace_enabled:
            return False

        await self.initialize()
        resolved = coerce_scope(scope, default_user_id=self.settings.sumeme_user_id)
        items = self._build_items(
            scope=resolved,
            conversation_id=conversation_id,
            request_payload=request_payload,
            assistant=assistant,
        )
        if not items:
            return True

        vectors = await self._embedding.embed(
            [str(item["search_text"]) for item in items],
            timeout_seconds=self.deadlines.write_seconds,
        )
        dimension = len(vectors[0])
        await self._ensure_collection(dimension)

        await anyio.to_thread.run_sync(self._store_drawers_sync, items)
        points = []
        for item, vector in zip(items, vectors, strict=True):
            points.append(
                {
                    "id": item["point_id"],
                    "vector": vector,
                    "payload": {
                        "drawer_id": item["drawer_id"],
                        "scope_key": resolved.storage_key,
                        "wing": item["wing"],
                        "room": item["room"],
                        "role": item["role"],
                        "content_hash": item["content_hash"],
                        "created_at": item["created_at"],
                    },
                }
            )

        await self._qdrant_request(
            "PUT",
            (
                f"/collections/{self.settings.mempalace_collection_name}"
                "/points?wait=true"
            ),
            json_body={"points": points},
            operation="write",
        )
        return True

    async def aclose(self) -> None:
        await self._embedding.aclose()
        await self._qdrant.aclose()

    def _build_items(
        self,
        *,
        scope: MemoryScope,
        conversation_id: str,
        request_payload: dict[str, Any],
        assistant: str,
    ) -> list[dict[str, Any]]:
        now = datetime.now(UTC).isoformat()
        source = f"lobe:{safe_id(conversation_id, 'unknown')}"
        wing = f"scope_{safe_id(scope.storage_key)}"
        common = {
            "timestamp": now,
            "conversation_id": conversation_id,
            "account_id": scope.account_id,
            "vault_id": scope.vault_id,
            "principal_type": scope.principal_type,
            "scope_key": scope.storage_key,
        }
        latest = latest_user_message(request_payload.get("messages") or [])
        user_search_text = flatten_content((latest or {}).get("content"))
        user_content = json.dumps(
            {**common, "role": "user", "request": request_payload},
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        raw_items: list[tuple[str, str, str]] = [
            ("user", user_content, user_search_text or user_content)
        ]
        if assistant and self.settings.store_assistant_verbatim:
            raw_items.append(
                (
                    "assistant",
                    json.dumps(
                        {**common, "role": "assistant", "content": assistant},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    assistant,
                )
            )

        items: list[dict[str, Any]] = []
        for role, content, search_text in raw_items:
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            identity = (
                f"{scope.storage_key}\n{conversation_id}\n{role}\n{content_hash}"
            )
            point_uuid = uuid.uuid5(uuid.NAMESPACE_URL, f"sumeme:mempalace:{identity}")
            items.append(
                {
                    "drawer_id": point_uuid.hex,
                    "point_id": str(point_uuid),
                    "principal_type": scope.principal_type,
                    "account_id": scope.account_id,
                    "vault_id": scope.vault_id,
                    "wing": wing,
                    "room": "conversation",
                    "role": role,
                    "conversation_id": conversation_id,
                    "source": source,
                    "content": content,
                    "content_hash": content_hash,
                    "search_text": search_text[
                        : self.settings.mempalace_embedding_max_chars
                    ],
                    "created_at": now,
                }
            )
        return items

    async def _ensure_collection(self, dimension: int) -> None:
        async with self._collection_lock:
            current = await self._collection_dimension()
            if current is None:
                response = await self._qdrant.put(
                    self._qdrant_url(
                        f"/collections/{self.settings.mempalace_collection_name}"
                    ),
                    json={
                        "vectors": {
                            "size": dimension,
                            "distance": "Cosine",
                            "on_disk": True,
                        }
                    },
                )
                if response.status_code not in {200, 201, 409}:
                    raise self._qdrant_error(response, "collection_create")
                current = await self._collection_dimension()
            if current is None:
                raise MemoryOperationError("mempalace_collection_unavailable")
            if current != dimension:
                raise MemoryOperationError("mempalace_embedding_dimension_changed")

            response = await self._qdrant.put(
                self._qdrant_url(
                    f"/collections/{self.settings.mempalace_collection_name}/index"
                    "?wait=true"
                ),
                json={"field_name": "scope_key", "field_schema": "keyword"},
            )
            if response.status_code not in {200, 201, 409}:
                logger.warning(
                    "MemPalace scope index creation failed status=%s",
                    response.status_code,
                )

    async def _collection_dimension(self) -> int | None:
        try:
            response = await self._qdrant.get(
                self._qdrant_url(
                    f"/collections/{self.settings.mempalace_collection_name}"
                )
            )
        except httpx.TimeoutException as exc:
            raise MemoryOperationError("mempalace_qdrant_timeout") from exc
        except httpx.HTTPError as exc:
            raise MemoryOperationError("mempalace_qdrant_unavailable") from exc
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise self._qdrant_error(response, "collection_read")
        try:
            data = response.json()
            vectors = data["result"]["config"]["params"]["vectors"]
            size = vectors["size"]
            return int(size)
        except (KeyError, TypeError, ValueError) as exc:
            raise MemoryOperationError("mempalace_qdrant_invalid_response") from exc

    async def _qdrant_request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any],
        operation: str,
    ) -> dict[str, Any]:
        try:
            response = await self._qdrant.request(
                method,
                self._qdrant_url(path),
                json=json_body,
            )
        except httpx.TimeoutException as exc:
            raise MemoryOperationError("mempalace_qdrant_timeout") from exc
        except httpx.HTTPError as exc:
            raise MemoryOperationError("mempalace_qdrant_unavailable") from exc
        if response.status_code >= 400:
            raise self._qdrant_error(response, operation)
        try:
            payload = response.json()
        except ValueError as exc:
            raise MemoryOperationError("mempalace_qdrant_invalid_response") from exc
        if not isinstance(payload, dict):
            raise MemoryOperationError("mempalace_qdrant_invalid_response")
        return payload

    @staticmethod
    def _query_points(payload: dict[str, Any]) -> list[Any]:
        result = payload.get("result")
        if isinstance(result, dict):
            points = result.get("points")
            return points if isinstance(points, list) else []
        return result if isinstance(result, list) else []

    @staticmethod
    def _qdrant_error(response: httpx.Response, operation: str) -> MemoryOperationError:
        if response.status_code in {401, 403}:
            return MemoryOperationError("mempalace_qdrant_auth_failed")
        if response.status_code == 429:
            return MemoryOperationError("mempalace_qdrant_rate_limited")
        if response.status_code >= 500:
            return MemoryOperationError("mempalace_qdrant_server_error")
        return MemoryOperationError(f"mempalace_qdrant_{operation}_rejected")

    def _qdrant_url(self, path: str) -> str:
        return f"{self.settings.mempalace_qdrant_url.rstrip('/')}/{path.lstrip('/')}"

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize_sync(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
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

    def _store_drawers_sync(self, items: list[dict[str, Any]]) -> None:
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO mempalace_drawers (
                    drawer_id, point_id, principal_type, account_id, vault_id,
                    wing, room, role, conversation_id, source, content,
                    content_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["drawer_id"],
                        item["point_id"],
                        item["principal_type"],
                        item["account_id"],
                        item["vault_id"],
                        item["wing"],
                        item["room"],
                        item["role"],
                        item["conversation_id"],
                        item["source"],
                        item["content"],
                        item["content_hash"],
                        item["created_at"],
                    )
                    for item in items
                ],
            )

    def _read_drawers_sync(
        self,
        scope: MemoryScope,
        drawer_ids: list[str],
    ) -> list[sqlite3.Row]:
        placeholders = ",".join("?" for _ in drawer_ids)
        with self._connect() as connection:
            return list(
                connection.execute(
                    f"""
                    SELECT drawer_id, wing, room, content
                    FROM mempalace_drawers
                    WHERE principal_type = ? AND account_id = ? AND vault_id = ?
                      AND drawer_id IN ({placeholders})
                    """,
                    (
                        scope.principal_type,
                        scope.account_id,
                        scope.vault_id,
                        *drawer_ids,
                    ),
                ).fetchall()
            )
