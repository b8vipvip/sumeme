# Scoped private-object access

Updated: 2026-07-30

## Purpose

SuMeMe stores new private attachments in the non-anonymous RustFS bucket configured by
`RUSTFS_PRIVATE_BUCKET` (default `sumeme-vaults`). Clients never choose an S3 object key
and never receive the internal bucket coordinate from the API.

The access layer sits on top of the existing `ObjectRegistry` and enforces the same
canonical scope used by memory:

```text
principal_type + account_id + vault_id
```

Production deployment and verification remain **GHS — GitHub-hosted SSH**. This feature
does not add a VSR-only path.

## Trust boundary

Every request requires the gateway Bearer credential and one trusted identity source:

- verified JWT/OIDC identity;
- LobeHub's server-injected OpenAI `user` value in `trusted-openai-user` mode;
- a verified SuMeMe service token and service ID.

Normal account access is rejected while `IDENTITY_MODE=legacy-client-asserted`. This is
intentional: a client-asserted account ID is not a sufficient authorization boundary for
private object URLs. Service identities remain available because their token is verified
with a constant-time comparison.

The gateway derives the scope and then queries the registry using all of:

```text
object_id + principal_type + account_id + vault_id
```

A valid object ID from another account or Vault therefore returns `object_not_found`
rather than revealing that the object exists.

## Configuration

The production image enables the object API. The existing Compose `.env` supplies the
RustFS credentials and public S3 endpoint.

```dotenv
OBJECT_API_ENABLED=true
OBJECT_REGISTRY_PATH=/data/gateway/objects.sqlite3
OBJECT_MAX_SIZE_BYTES=2147483648
OBJECT_PRESIGN_TTL_SECONDS=600
OBJECT_RESERVATION_TTL_SECONDS=3600
OBJECT_CLEANUP_INTERVAL_SECONDS=300
OBJECT_CLEANUP_BATCH_SIZE=100
OBJECT_OPERATION_LEASE_SECONDS=7200
OBJECT_ALLOW_INSECURE_PUBLIC_ENDPOINT=false
RUSTFS_INTERNAL_ENDPOINT=http://rustfs:9000
# RUSTFS_PUBLIC_ENDPOINT takes precedence; otherwise existing S3_ENDPOINT is used.
RUSTFS_PUBLIC_ENDPOINT=https://s3.example.com
RUSTFS_PRIVATE_BUCKET=sumeme-vaults
RUSTFS_REGION=us-east-1
```

The public endpoint must use HTTPS unless insecure URLs are explicitly allowed for a
non-production environment. Upload and download URLs use S3 Signature Version 4 and
path-style addressing.

The reservation TTL cannot be shorter than the signed URL TTL. The operation lease also
cannot be shorter than the signed URL TTL. Initial uploads use one S3 PUT and are bounded
to 5 GiB; larger objects require a future multipart protocol.

## Upload protocol

### 1. Reserve

```http
POST /api/objects/reserve-upload
Authorization: Bearer <gateway credential>
X-SuMeMe-Identity-Token: <verified JWT when applicable>
Content-Type: application/json
```

Example body for a trusted upstream user:

```json
{
  "user": "server-injected-user-id",
  "metadata": {"vault_id": "default"},
  "filename": "document.pdf",
  "content_type": "application/pdf",
  "size_bytes": 12345,
  "sha256": "<64 lowercase hex characters>",
  "object_kind": "raw",
  "sanitized_for_cloud": false
}
```

The server:

1. resolves a trusted scope;
2. enforces the Vault policy;
3. generates a random 128-bit object ID;
4. generates the scoped internal object key;
5. records a `reserved` registry row;
6. returns a short-lived presigned `PUT` URL and the exact required headers.

The response intentionally omits `object_key`, bucket name and access credentials.

### 2. Upload directly to RustFS

The client sends the bytes to the returned URL using the returned method and headers.
The `Content-Type` header must match the signed value.

### 3. Complete and verify

```http
POST /api/objects/complete-upload
```

```json
{
  "user": "server-injected-user-id",
  "metadata": {"vault_id": "default"},
  "object_id": "<32 lowercase hex characters>"
}
```

The gateway does not trust a client-supplied size or completion hash. It reads the
object through the Compose-internal RustFS endpoint, streams it through SHA-256, and
compares the actual byte count and digest with the reservation. Only then does the
registry transition from `reserved` to `ready`.

A size or hash mismatch causes the uploaded blob to be deleted and the completion call
to fail. Hash verification is streaming and does not load the whole attachment into
memory.

## Reservation cleanup and operation leases

A client may reserve an object and then never upload or complete it. The gateway owns a
background cleanup task tied to the FastAPI lifespan. It runs immediately at startup and
then at `OBJECT_CLEANUP_INTERVAL_SECONDS` intervals.

Cleanup selects at most `OBJECT_CLEANUP_BATCH_SIZE` rows that are still `reserved` and
older than `OBJECT_RESERVATION_TTL_SECONDS`. Before deleting anything it reloads the
record and rechecks both state and timestamp.

Completion, authenticated deletion and expiration cleanup all acquire the same SQLite
operation lease keyed by `object_id`:

```text
object_id + unique lease_id + operation + acquired_at + expires_at
```

Lease acquisition uses `BEGIN IMMEDIATE`, removes only expired leases, and inserts the
new lease atomically. A concurrent operation receives `object_operation_in_progress` or
is skipped by background cleanup.

Lease release includes both `object_id` and the unique `lease_id`. Therefore an old
operation whose lease expired cannot accidentally remove a replacement lease acquired by
a newer operation. A crashed process leaves only a bounded lease that becomes reclaimable
after `OBJECT_OPERATION_LEASE_SECONDS`.

Expired cleanup deletes the physical blob first and then soft-deletes the registry row.
If RustFS deletion fails, the row remains `reserved` and a later cleanup cycle retries it.
Logs contain only object IDs, counters and stable error codes, never object content or
credentials.

The cleanup task is cancelled and awaited when the gateway shuts down, so it cannot
remain as an orphan process after application shutdown.

## Download protocol

```http
POST /api/objects/create-download
```

The gateway re-resolves the identity and Vault, loads only a `ready` record in that
scope, checks that the physical object exists, and returns a short-lived presigned
`GET` URL. A reserved, deleted, missing or cross-scope object is not downloadable.

The current Vault policy is rechecked before URL issuance. A previous cloud reservation
cannot bypass a later switch to `local-only` or a stricter hybrid policy.

## Delete protocol

```http
POST /api/objects/delete
```

Deletion is deliberately server-mediated rather than delegated to an unconfirmed
direct DELETE URL:

1. re-authorize the current scope;
2. acquire the object operation lease;
3. reload the scoped registry record;
4. delete the physical RustFS object through the internal endpoint;
5. mark the registry row `deleted`;
6. return only scoped metadata.

The operation is idempotent for an already deleted registry record. If physical deletion
succeeds but the registry update fails, retrying the request safely repeats the delete
and attempts the metadata transition again.

## List protocol

```http
POST /api/objects/list
```

The result contains only records belonging to the resolved account/service and Vault.
Deleted records are excluded unless `include_deleted=true`. The limit is bounded to
500 records.

## Vault policy behavior

| Storage mode | Object behavior |
|---|---|
| `local-only` | Cloud object reservation, completion and download are rejected |
| `cloud` | Raw or derived objects may be reserved |
| `hybrid` | Only explicitly sanitized, non-raw derivatives may be reserved |

The object API does not change or bypass the existing Vault policy.

## Stable error classes

Representative safe errors include:

```text
object_api_disabled
object_trusted_identity_required
object_not_found
object_not_ready
object_operation_in_progress
object_cloud_storage_disabled
object_sanitized_cloud_copy_required
object_raw_hybrid_upload_forbidden
object_size_mismatch
object_sha256_mismatch
object_blob_not_found
object_store_access_denied
object_store_rate_limited
```

Errors do not include S3 credentials, internal object keys, provider response bodies or
user file content.

## Current limitations and next work

- Multipart upload is not exposed yet; the initial API uses one presigned PUT.
- LobeHub's legacy public attachment bucket is unchanged and requires a separate
  migration.
- Direct untrusted browser/mobile clients still need an approved user-facing auth
  gateway; the shared gateway credential must not be embedded in a public application.
- Production acceptance requires CI, a GHS deployment, a private-bucket roundtrip and
  cross-account negative tests against the deployed service.
