# SuMeMe development progress

Updated: 2026-07-30

## Operating contract

- Production deployment mode: **GHS — GitHub-hosted SSH**.
- VSR remains a declared fallback workflow but must not be selected or used silently.
- Every code change must pass real GitHub Actions steps before merge when it affects executable code, deployment or production workflows.
- GitHub Actions is asynchronous: after a push, allow a reasonable queue/start window and continue independent work before deciding that a run is blocked.
- All AI, embedding, OCR, vision, transcription and memory extraction must use the configured OpenAI-compatible relay or an explicitly approved vendor API. Local model runtimes and model weights are forbidden.
- `mempalace-letta` is the default memory provider. `supermemory` is an explicit alternative only; no automatic failover or dual-write.
- Secrets, `.env`, user memory text and raw provider responses must not be committed or printed.

## Current target

Finish the production reliability and isolation work required before Phase 2 attachment ingestion:

1. keep the chat gateway available when optional memory components fail;
2. make GHS deployment, rollback and status state deterministic;
3. rebuild every locally built runtime service from the exact tested revision;
4. complete sanitized application, private-object and status reporting;
5. finish account/Vault isolation before large-scale multimodal ingestion.

## Completed foundation

- LobeHub, PostgreSQL, Redis, RustFS, Qdrant, Letta, memory-gateway and ai-provider-proxy Compose stack.
- OpenAI-compatible `/v1/models` and `/v1/chat/completions` gateway.
- Streaming and non-streaming relay forwarding.
- Account/Vault/service memory scopes and a persistent Vault registry.
- `local-only`, `cloud` and `hybrid` server policy semantics.
- Remote-only MemPalace embedding path through ai-provider-proxy; no local model loading.
- SQLite verbatim drawers plus Qdrant vectors with server-enforced scope filters.
- Optional Letta structured memory with stable degraded/error reporting.
- Pinned Letta Server `0.16.8` and Python SDK `1.12.1`.
- Bounded per-component memory recall and write timeouts.
- Isolated service identity for smoke tests.
- GHS deployment through pinned-host-key SSH and an allow-listed deployment script.
- Deployment lock, disk preflight, release snapshots, health checks, smoke tests and rollback.
- Bounded production log collection with streaming secret redaction.

## Active reliability pull request

Pull request: `#43`  
Branch: `agent/ghs-reliability-next`  
Merge status: **open and blocked until real CI steps pass**.

### Implemented on the branch

#### Deployment and recovery

- rebuild both `memory-gateway` and `ai-provider-proxy` during normal deployment and rollback;
- remove the Compose startup dependency that made optional Letta block memory-gateway startup;
- clear `.deploy/deploying_sha` after rollback;
- append a structured rollback history entry;
- retain explicit GHS production declarations and keep VSR as a non-silent fallback only.

#### Status freshness and consistency

- publish top-level `age_seconds` and `stale` fields;
- report `deploying_sha`, deployment state, current/main consistency and last deployment result;
- classify stale deployment markers separately from a real in-progress deployment;
- degrade the status snapshot when a stale marker is detected;
- add unit tests for freshness, stale markers, active deployment and rollback history.

#### GHS status publishing

- migrate `Publish project status` from a VPS self-hosted Runner to a GitHub-hosted Runner;
- keep `GITHUB_TOKEN` only on the GitHub-hosted Runner;
- generate a bounded, sanitized GitHub metadata snapshot locally;
- upload only collector scripts plus sanitized metadata to a temporary VPS directory;
- collect runtime state through pinned-host-key SSH;
- fetch sanitized JSON/Markdown and publish them to `ops-status` from GitHub;
- remove the remote temporary collector bundle after each run.

#### Private RustFS smoke

- add `scripts/smoke-private-object.sh`;
- use the private `sumeme-vaults` bucket rather than the legacy LobeHub-compatible bucket;
- write a random marker under a scoped service/Vault object key;
- verify upload, read-back, delete and post-delete absence;
- write only a sanitized report to `.deploy/smoke/private-object.json`;
- run private-object smoke before the application smoke in the deployment gate;
- migrate scheduled/manual production smoke from self-hosted Runner to GHS;
- keep exact Host Key verification and never print object content or credentials.

#### Documentation

- update `README.md` to the current remote-AI-only implementation;
- update `docs/architecture.md` for identity, Vault policies, MemPalace SQLite/Qdrant, optional Letta, Provider Proxy and GHS;
- maintain this file as the resumable development and blocker ledger.

## Active stacked isolation pull request

Pull request: `#44`  
Branch: `agent/scoped-object-access-api`  
Base: `agent/ghs-reliability-next` / PR #43  
Merge status: **open; PR #43 must merge first and PR #44 must then be retargeted to `main`**.

### Implemented on the stacked branch

- isolated object-access configuration with HTTPS, credential, bucket, TTL and single-PUT size validation;
- short-lived SigV4 upload URLs for server-generated, account/Vault-scoped object keys;
- short-lived download URLs only for `ready` objects in the resolved scope;
- server-mediated physical deletion followed by registry soft deletion;
- server-side streaming byte-count and SHA-256 verification before `reserved → ready`;
- automatic removal of blobs whose actual size or hash does not match the reservation;
- no internal object key, bucket credential or raw RustFS response in API output;
- ordinary account object access rejected in `legacy-client-asserted` mode;
- verified JWT, trusted LobeHub upstream identity and verified service identity support;
- current Vault policy rechecked before completion and download, preventing a cloud reservation from bypassing a later `local-only` or stricter `hybrid` policy;
- cross-account/cross-Vault lookup returns `object_not_found`;
- composed gateway entrypoint preserving the existing chat/memory lifespan;
- configuration, signing, hash-verification, route isolation and production-entry contract tests;
- protocol and limitation documentation in `docs/architecture/scoped-object-access.md`.

### Remaining acceptance for PR #44

- gateway Ruff, pytest and compileall must execute real steps and pass;
- the gateway container must build with boto3 and `app.entry:app`;
- after PR #43 merges, retarget PR #44 to `main` and rerun all checks;
- after merge, deploy only through GHS;
- verify reserve/upload/complete/download/delete against the private production bucket;
- verify deployed cross-account and cross-Vault negative cases;
- add cleanup for abandoned `reserved` rows after signed URLs expire;
- add multipart upload only if files above the bounded single-PUT limit are required.

## Blocked or deferred stages

### GitHub Actions zero-step startup failure

PR #43 produced these workflow runs:

- `30540407563`
- `30540470236`
- `30540713100`
- `30541223754`

Each run created the expected `gateway`, `provider-proxy`, `reliability` and `compose` jobs, but all four jobs failed before GitHub reported any executed steps. The job log endpoint had no log blob. GHS and VSR deployment jobs were correctly skipped for the pull request.

Run `30541223754` was not judged immediately. Independent object-isolation work continued, then the failed jobs were retried after the waiting window. The retry again completed with no reported steps or log blobs. This confirms the recorded startup/control-plane symptom without treating a newly queued run as failed.

This does not prove that the code or tests failed, and it does not count as a successful build.

Handling:

- keep PR #43 open and unmerged;
- retry after Actions can execute real steps;
- require all four test jobs to pass before merge;
- continue independent code/design work that does not rely on a successful production deployment;
- never bypass the build gate for production code or workflows.

### Main-branch Actions status visibility

The latest merged `main` commit did not return readable combined status checks through the current connector. This is an observability/control-plane limitation, not evidence that the build passed or failed.

Handling:

- do not describe the latest main build as verified until a real workflow run is visible;
- record missing or zero-step runs instead of treating them as success.

### Real relay validation

The last server-side probe listed the configured model successfully but the chat request returned `403 Insufficient account balance`.

The relay test implementation remains in the smoke suite. Real endpoint/key/model/balance verification is explicitly deferred to a server-side check by the operator. Missing relay credentials in an external development session must not block pure code, tests or documentation.

### Letta production acceptance

Letta is observable but optional (`LETTA_REQUIRED=false`). Agent creation, structured-memory update and recall still require a successful production acceptance run.

Until then:

- MemPalace remains the required durable write component;
- Letta failure must remain visible as degraded with a stable `letta_*` error code;
- the gateway must remain available when Letta is unavailable.

### Private-object production acceptance

Private-bucket roundtrip smoke is implemented on PR #43. Scoped application object APIs are implemented on stacked PR #44. Neither layer is production-accepted until its real CI gates pass and the resulting main revision completes a GHS deployment and production negative tests.

### Full local-only and hybrid clients

The server-side Vault policy exists, but encrypted local Vault storage, local search, hybrid sanitization, synchronization and conflict handling are not implemented. Do not describe these modes as complete client products.

## Next development queue

### Phase 1.5 reliability

- [ ] Re-run PR #43 when Actions can execute real steps.
- [ ] Merge only after gateway, provider-proxy, reliability and Compose jobs pass.
- [ ] Verify the merge commit's main workflow when a readable run is available.
- [ ] Deploy through GHS and verify exact production SHA, empty `deploying_sha`, local/public HTTP 200 and rebuilt runtime images.
- [ ] Run the GHS status publisher and verify freshness/consistency fields on `ops-status`.
- [ ] Run the GHS private-object and application smoke suites in production.
- [ ] Complete MemPalace write/recall production acceptance.
- [ ] Complete Letta write/recall production acceptance or retain the recorded blocker.

### Identity and storage isolation

- [ ] Move production away from `legacy-client-asserted` identity.
- [ ] Complete LobeHub trusted server-injected user integration or require verified JWT.
- [ ] Enforce Letta agent ownership by `account_id + vault_id`.
- [x] Implement scoped signed upload/download and authenticated delete APIs in PR #44.
- [ ] Pass CI, retarget and merge PR #44 after PR #43.
- [ ] Add abandoned reservation cleanup and production negative acceptance.
- [ ] Add cross-account negative tests for memory read/write/search/delete/export/restore.
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

1. read this file and current open pull requests;
2. state that production mode is GHS;
3. inspect CI before merging, but allow queued/new runs time to start while doing independent work;
4. when a stage is externally blocked but does not invalidate later independent work, record it here and continue;
5. never silently weaken security, smoke gates, account isolation or secret redaction to make a deployment appear successful.
