#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/sumeme}"
STATE_DIR="${DEPLOY_DIR}/.deploy"
OUTPUT_PATH="${PRIVATE_OBJECT_SMOKE_OUTPUT_PATH:-${STATE_DIR}/smoke/private-object.json}"
SMOKE_ACCOUNT_ID="sumeme-smoke"
SMOKE_VAULT_ID="production-smoke"

read_env() {
  local key="$1"
  local fallback="${2:-}"
  local value
  value="$(grep -m1 -E "^${key}=" "${DEPLOY_DIR}/.env" 2>/dev/null | cut -d= -f2- || true)"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  printf '%s' "${value:-${fallback}}"
}

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing command: $1" >&2
    exit 127
  }
}

need docker
need python3

if [[ ! -f "${DEPLOY_DIR}/.env" ]]; then
  echo "Missing ${DEPLOY_DIR}/.env" >&2
  exit 64
fi

RUSTFS_ACCESS_KEY="$(read_env RUSTFS_ACCESS_KEY)"
RUSTFS_SECRET_KEY="$(read_env RUSTFS_SECRET_KEY)"
RUSTFS_PRIVATE_BUCKET="$(read_env RUSTFS_PRIVATE_BUCKET sumeme-vaults)"

for key in RUSTFS_ACCESS_KEY RUSTFS_SECRET_KEY RUSTFS_PRIVATE_BUCKET; do
  if [[ -z "${!key}" ]]; then
    echo "Private object smoke configuration is incomplete: ${key}" >&2
    exit 64
  fi
done

started_at="$(date --iso-8601=seconds)"
started_epoch="$(date +%s)"
marker="SUMEME_PRIVATE_OBJECT_$(date -u +%Y%m%dT%H%M%SZ)_${RANDOM}"
object_key="services/${SMOKE_ACCOUNT_ID}/vaults/${SMOKE_VAULT_ID}/objects/${marker}.txt"
ok=false
error_codes=()

mkdir -p "$(dirname "${OUTPUT_PATH}")"
cd "${DEPLOY_DIR}"

if docker compose run --rm --no-deps -T \
  -e "RUSTFS_ACCESS_KEY=${RUSTFS_ACCESS_KEY}" \
  -e "RUSTFS_SECRET_KEY=${RUSTFS_SECRET_KEY}" \
  -e "RUSTFS_PRIVATE_BUCKET=${RUSTFS_PRIVATE_BUCKET}" \
  -e "SMOKE_MARKER=${marker}" \
  -e "SMOKE_OBJECT_KEY=${object_key}" \
  --entrypoint /bin/sh rustfs-init -c '
    set -eu
    mc alias set smoke http://rustfs:9000 "$RUSTFS_ACCESS_KEY" "$RUSTFS_SECRET_KEY" >/dev/null
    target="smoke/$RUSTFS_PRIVATE_BUCKET/$SMOKE_OBJECT_KEY"
    cleanup() {
      mc rm --force "$target" >/dev/null 2>&1 || true
    }
    trap cleanup EXIT

    printf "%s" "$SMOKE_MARKER" | mc pipe "$target" >/dev/null
    actual="$(mc cat "$target")"
    test "$actual" = "$SMOKE_MARKER"
    mc rm "$target" >/dev/null
    if mc stat "$target" >/dev/null 2>&1; then
      echo "Private smoke object still exists after deletion" >&2
      exit 1
    fi
    trap - EXIT
  ' >/dev/null 2>&1; then
  ok=true
else
  error_codes+=("private_object_roundtrip_failed")
fi

finished_at="$(date --iso-8601=seconds)"
duration_seconds="$(( $(date +%s) - started_epoch ))"

python3 - \
  "${OUTPUT_PATH}" \
  "${started_at}" \
  "${finished_at}" \
  "${duration_seconds}" \
  "${ok}" \
  "${RUSTFS_PRIVATE_BUCKET}" \
  "${SMOKE_ACCOUNT_ID}" \
  "${SMOKE_VAULT_ID}" \
  "${error_codes[*]:-}" <<'PY'
import json
import sys

(
    path,
    started_at,
    finished_at,
    duration,
    ok,
    bucket,
    account_id,
    vault_id,
    errors,
) = sys.argv[1:]
value = {
    "schema_version": 1,
    "generated_at": finished_at,
    "started_at": started_at,
    "finished_at": finished_at,
    "duration_seconds": int(duration),
    "overall": "success" if ok == "true" else "failure",
    "mode": "private-scoped-roundtrip",
    "scope": f"service:{account_id}/{vault_id}",
    "bucket_configured": bool(bucket),
    "checks": {
        "upload": ok == "true",
        "read_back": ok == "true",
        "delete": ok == "true",
    },
    "error_codes": [item for item in errors.split() if item],
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(value, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
PY

printf 'Private RustFS object smoke: %s\n' "${ok}"
[[ "${ok}" == "true" ]]
