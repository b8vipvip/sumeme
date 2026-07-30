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

Optional settings:

```dotenv
OBJECT_API_ENABLED=true
OBJECT_REGISTRY_PATH=/data/gateway/objects.sqlite3
OBJECT_MAX_SIZE_BYTES=2147483648
OBJECT_PRESIGN_TTL_SECONDS=600
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

## Download protocol

```http
POST /api/objects/create-download
```

The gateway re-resolves the identity and Vault, loads only a `ready` record in that
scope, checks that the physical object exists, and returns a short-lived presigned
`GET` URL. A reserved, deleted, missing or cross-scope object is not downloadable.

## Delete protocol

```http
POST /api/objects/delete
```

Deletion is deliberately server-mediated rather than delegated to an unconfirmed
direct DELETE URL:

1. re-authorize the current scope;
2. delete the physical RustFS object through the internal endpoint;
3. mark the registry row `deleted`;
4. return only scoped metadata.

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
| `local-only` | Cloud object reservation is rejected |
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

- Reserved rows whose upload URL expires are not yet garbage-collected automatically.
- Multipart upload is not exposed yet; the initial API uses one presigned PUT.
- LobeHub's legacy public attachment bucket is unchanged and requires a separate
  migration.
- Direct untrusted browser/mobile clients still need an approved user-facing auth
  gateway; the shared gateway credential must not be embedded in a public application.
- Production acceptance requires CI, a GHS deployment, a private-bucket roundtrip and
  cross-account negative tests against the deployed service.
