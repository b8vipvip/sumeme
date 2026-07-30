# SuMeMe development progress

Updated: 2026-07-30

## Operating contract

- Production deployment mode: **GHS — GitHub-hosted SSH**.
- VSR remains a declared fallback workflow but must not be selected or used silently.
- Every code change should pass GitHub Actions before merge when Actions produces a usable run.
- All AI, embedding, OCR, vision, transcription and memory extraction must use the configured OpenAI-compatible relay or an explicitly approved vendor API. Local model runtimes and model weights are forbidden.
- `mempalace-letta` is the default memory provider. `supermemory` is an explicit alternative only; no automatic failover or dual-write.
- Secrets, `.env`, user memory text and raw provider responses must not be committed or printed.

## Current target

Finish the production reliability and isolation work needed before Phase 2 attachment ingestion:

1. keep the chat gateway available when optional memory components fail;
2. make GHS deploy and rollback state deterministic;
3. rebuild every locally built runtime service from the exact tested revision;
4. complete sanitized production smoke and status reporting;
5. finish account/vault isolation before large-scale multimodal ingestion.

## Completed foundation

- LobeHub, PostgreSQL, Redis, RustFS, Qdrant, Letta, memory-gateway and ai-provider-proxy Compose stack.
- OpenAI-compatible `/v1/models` and `/v1/chat/completions` gateway.
- Streaming and non-streaming relay forwarding.
- Account/vault/service memory scopes and a persistent Vault registry.
- `local-only`, `cloud` and `hybrid` server policy semantics.
- Remote-only MemPalace embedding path through ai-provider-proxy; no local model loading.
- SQLite verbatim drawers plus Qdrant vectors with server-enforced scope filters.
- Optional Letta structured memory with stable degraded/error reporting.
- Pinned Letta Server `0.16.8` and Python SDK `1.12.1`.
- Bounded per-component memory recall and write timeouts.
- Isolated service identity for smoke tests.
- GHS deployment through pinned host-key SSH and an allow-listed deployment script.
- Deployment lock, disk preflight, release snapshots, health checks, smoke tests and rollback.
- Bounded production log collection with streaming secret redaction.

## Active reliability change

Branch: `agent/ghs-reliability-next`

Changes in progress:

- rebuild both `memory-gateway` and `ai-provider-proxy` during normal deployment and rollback;
- remove the Compose startup dependency that made optional Letta block memory-gateway startup;
- clear `.deploy/deploying_sha` after rollback and append a rollback history record;
- add contract tests that lock these behaviors and keep the production workflow explicitly GHS.

## Blocked or deferred stages

### Main-branch Actions status visibility

The latest merged `main` commit did not return readable combined status checks through the current GitHub connector. This is an observability/control-plane limitation, not evidence that the build passed or failed.

Handling:

- do not describe the latest main build as verified until a real workflow run is visible;
- continue changes that can be reviewed and tested on a pull request;
- record zero-step or missing-run failures rather than treating them as success.

### Real relay validation

The last server-side probe listed the configured model successfully but the chat request returned `403 Insufficient account balance`.

The relay test implementation remains part of the smoke suite, but real endpoint/key/balance verification is explicitly deferred to a server-side check by the operator. Lack of relay credentials in an external development session must not block pure code, tests or documentation.

### Letta production acceptance

Letta is currently observable but optional (`LETTA_REQUIRED=false`). Agent creation, structured-memory update and recall still need a successful production acceptance run. Until then:

- MemPalace remains the required durable write component;
- Letta failure must remain visible as degraded with a stable `letta_*` error code;
- the gateway must remain available when Letta is unavailable.

### Full local-only and hybrid clients

The server-side Vault policy exists, but encrypted local Vault storage, local search, hybrid sanitization, synchronization and conflict handling are not implemented yet. Do not describe these modes as complete client products.

## Next development queue

### Phase 1.5 reliability

- [ ] Verify the pull-request CI for `agent/ghs-reliability-next`.
- [ ] Merge only after gateway, provider-proxy, reliability and Compose jobs pass.
- [ ] Verify the merge commit's main workflow when a readable run is available.
- [ ] Deploy through GHS and verify exact production SHA, empty `deploying_sha`, local/public HTTP 200 and new runtime images.
- [ ] Add status `age_seconds`, `stale`, current/deploying SHA consistency and last deployment result.
- [ ] Complete RustFS upload/read/delete smoke coverage.
- [ ] Complete MemPalace write/recall production acceptance.
- [ ] Complete Letta write/recall production acceptance or keep the recorded blocker.

### Identity and storage isolation

- [ ] Move production away from `legacy-client-asserted` identity.
- [ ] Complete LobeHub trusted server-injected user integration or require verified JWT.
- [ ] Enforce Letta agent ownership by `account_id + vault_id`.
- [ ] Partition private RustFS objects by account and vault and issue short-lived signed URLs.
- [ ] Add cross-account negative tests for read, write, search, delete, export and restore.
- [ ] Implement encrypted local Vault and hybrid sanitized synchronization.

### Phase 2 multimodal ingestion

Start only after the required isolation boundary is demonstrably enforced:

- attachment worker and queue;
- image, audio, video, PDF and Office parsing through remote AI APIs;
- processing state, retry and idempotency;
- historical attachment backfill;
- traceable links between raw objects, verbatim memory and structured facts.

## Resume instructions

When continuing automated development:

1. read this file and the current open pull requests;
2. state that production mode is GHS;
3. inspect CI before merging;
4. if a stage is externally blocked but does not invalidate later code work, record it here and proceed to the next independent task;
5. never silently weaken security, smoke gates, account isolation or secret redaction to make a deployment appear successful.
