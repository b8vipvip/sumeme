# SuMeMe development progress

Updated: 2026-07-31

## Operating contract

- Production deployment mode: **GHS — GitHub-hosted SSH**.
- VSR remains a declared fallback workflow but must not be selected or used silently.
- Every executable change must pass real GitHub Actions steps before merge.
- GitHub Actions is asynchronous: allow queued runs time to start and continue independent work before deciding that a run is blocked.
- All AI, embedding, OCR, vision, transcription and memory extraction must use the configured OpenAI-compatible relay or an explicitly approved vendor API. Local model runtimes and model weights are forbidden.
- `mempalace-letta` is the default memory provider. `supermemory` is an explicit alternative only; no automatic failover or dual-write.
- Secrets, `.env`, user memory text and raw provider responses must not be committed or printed.

## Acceptance model

SuMeMe now separates acceptance into two explicit classes.

### Simulated acceptance

Status label: `simulated_pass` or `simulated_failure`.

This is a required CI gate and uses deterministic non-secret fixtures. It validates:

- OpenAI-compatible `/models`, `/chat/completions` and `/embeddings` response contracts;
- MemPalace + Letta write and recall orchestration;
- account, Vault and account/service scope isolation;
- optional Letta degraded behavior;
- required Letta fail-closed behavior;
- safe, non-mutating memory context injection;
- the rest of the repository's identity, object-storage, rollback and reliability tests.

A simulated pass is sufficient to accept code logic and continue development when a real provider account is unavailable. It must never be represented as proof that a real external API is funded, authorized, low-latency or operational.

### Live provider and production acceptance

Status labels include `live_pass`, `external_degraded`, `production_pass` and `production_failure`.

These checks require real infrastructure and verify:

- relay credentials, account balance and provider authorization;
- actual model availability and compatibility;
- real chat and embedding latency and rate limits;
- production RustFS/Letta/Qdrant persistence;
- real GHS deployment, public health and rollback behavior;
- real-user interaction quality.

Live-provider failures do not invalidate a successful simulated code acceptance. They remain visible as an external or production degradation and must not be silently converted to success.

## Current verified state

- GitHub Actions runner/billing startup blocker: resolved after the repository became public.
- Gateway, Provider Proxy, reliability, Compose and container builds: real CI has executed successfully.
- Private RustFS production upload/read/delete/post-delete roundtrip: passed.
- Production container recovery and public/local HTTP health: passed on the previous stable release.
- Latest production status: degraded primarily by disk warning and external relay failure.
- Real relay `/models`: passed.
- Real relay chat and embeddings: HTTP 403, classified as `external_degraded`.
- MemPalace and Letta code paths: unit/integration coverage passed; deterministic simulated end-to-end acceptance is being added as a permanent CI gate.
- Real MemPalace/Letta end-to-end provider acceptance remains pending because both depend on the external relay returning 2xx.

## Active reliability pull request

Pull request: `#49`  
Branch: `agent/fix-production-reliability`  
State: draft while the updated simulated acceptance CI executes.

Implemented:

- verified rollback completion;
- `rollback_failed` history when recovery remains unhealthy;
- no false rewrite of `current_sha` after failed recovery;
- no-volume Compose container/network recovery;
- fresh per-run production smoke scripts and reports;
- scheduled smoke failures no longer appear green;
- deterministic simulated end-to-end acceptance for relay, memory and isolation contracts;
- production deployment jobs depend on the simulated acceptance gate.

## Remaining live-only acceptance

The following cannot be honestly replaced by simulated data:

- whether the configured relay account has balance and permission;
- whether the selected real model names are enabled by the relay;
- actual latency, throttling and provider-specific edge cases;
- persistence across real VPS/container restarts and external service upgrades;
- real user experience and subjective answer quality.

These items remain recorded as live acceptance, not code-development blockers.

## Next steps

1. Finish PR #49 CI, including the new simulated end-to-end job.
2. Fix any genuine test failure without weakening the gate.
3. Mark code logic as accepted when all real CI jobs pass.
4. Keep live relay 403 visible as `external_degraded`.
5. Continue development that does not depend on real provider behavior.
6. Re-run live chat, embeddings, MemPalace and Letta production acceptance when valid relay access is available.
