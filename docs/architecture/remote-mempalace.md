# Remote-AI MemPalace adapter

## Decision

SuMeMe keeps MemPalace's raw-memory responsibilities and its wing / room /
verbatim-drawer model, but does not execute MemPalace's bundled local embedding
models. The default memory stack remains:

```text
raw episodic memory: SuMeMe Remote-AI MemPalace adapter
structured memory:   Letta
backup provider:      SuMeMe-maintained Supermemory fork
```

Every embedding request is sent through the internal Remote AI Provider Proxy to
the configured OpenAI-compatible relay or an approved official vendor API. There
is no local model fallback.

## Data placement

```text
verbatim drawer content
  -> /data/gateway/mempalace-remote.sqlite3

embedding request
  -> ai-provider-proxy /v1/embeddings
  -> native remote embeddings or remote semantic canonicalization

vector + scope metadata + drawer_id
  -> Qdrant collection <namespace>_mempalace_remote_v1
```

Qdrant payloads do not contain raw prompts, assistant responses or attachments.
The full drawer is loaded from SQLite only after the Qdrant result passes a
second `principal_type + account_id + vault_id` ownership check.

## Isolation

Each query contains an exact Qdrant filter on the server-generated `scope_key`.
SQLite retrieval repeats the scope check. A malicious or stale Qdrant point that
references another account's drawer therefore cannot reveal that drawer.

Point IDs are UUIDv5 values derived from:

```text
scope + conversation_id + role + stable content hash
```

Repeating the same checkpoint is idempotent. Account and service principals with
the same display name still produce different IDs and storage scopes.

## Legacy data

The existing `mempalace-data` Docker volume is intentionally left untouched.
The new runtime neither imports it nor deletes it. A later migration tool must:

1. read legacy drawers without loading a local embedding model;
2. preserve their original text and timestamps;
3. request new vectors through the approved Remote AI Provider Proxy;
4. write the scoped SQLite/Qdrant representation;
5. produce a resumable, auditable migration report.

There is no automatic migration during deployment because an implicit rebuild
could make unbounded API calls or mix old single-user wings into the wrong Vault.

## Failure behavior

- remote embedding timeout: sanitized `mempalace_embedding_timeout`;
- provider authentication failure: `mempalace_embedding_auth_failed`;
- Qdrant timeout/unavailable: stable `mempalace_qdrant_*` category;
- recall failures degrade to an empty raw-memory result so chat continues;
- checkpoint failures remain visible to production smoke and do not silently
  switch to Supermemory or dual-write.
