#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/sumeme}"
OUTPUT_PATH="${SMOKE_OUTPUT_PATH:-${DEPLOY_DIR}/.deploy/smoke/latest.json}"
GATEWAY_PORT="${GATEWAY_PORT:-8010}"
SMOKE_MEMORY_ATTEMPTS="${SMOKE_MEMORY_ATTEMPTS:-4}"
SMOKE_MEMORY_DELAY_SECONDS="${SMOKE_MEMORY_DELAY_SECONDS:-12}"
SMOKE_ACCOUNT_ID="sumeme-smoke"
SMOKE_VAULT_ID="production-smoke"
SMOKE_SCOPE="service:${SMOKE_ACCOUNT_ID}/${SMOKE_VAULT_ID}"

cd "${DEPLOY_DIR}"
mkdir -p "$(dirname "${OUTPUT_PATH}")"

read_env() {
  local key="$1"
  local fallback="${2:-}"
  local value
  value="$(grep -m1 -E "^${key}=" .env 2>/dev/null | cut -d= -f2- || true)"
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

need curl
need python3
need docker

GATEWAY_API_KEY="$(read_env GATEWAY_API_KEY)"
GATEWAY_ADMIN_TOKEN="$(read_env GATEWAY_ADMIN_TOKEN)"
OPENAI_CHAT_MODEL="$(read_env OPENAI_CHAT_MODEL)"
MEMORY_PROVIDER="$(read_env MEMORY_PROVIDER mempalace-letta)"
SMOKE_REQUIRE_RECALL="$(read_env SMOKE_REQUIRE_RECALL false)"
RUSTFS_ACCESS_KEY="$(read_env RUSTFS_ACCESS_KEY)"
RUSTFS_SECRET_KEY="$(read_env RUSTFS_SECRET_KEY)"
RUSTFS_LOBE_BUCKET="$(read_env RUSTFS_LOBE_BUCKET lobe)"

case "${MEMORY_PROVIDER}" in
  default|mempalace+letta|mempalace_letta)
    MEMORY_PROVIDER="mempalace-letta"
    ;;
  mempalace-letta|supermemory)
    ;;
  *)
    echo "Unsupported MEMORY_PROVIDER: ${MEMORY_PROVIDER}" >&2
    exit 64
    ;;
esac

case "${SMOKE_REQUIRE_RECALL,,}" in
  1|true|yes|on)
    SMOKE_REQUIRE_RECALL=true
    ;;
  0|false|no|off)
    SMOKE_REQUIRE_RECALL=false
    ;;
  *)
    echo "Invalid SMOKE_REQUIRE_RECALL=${SMOKE_REQUIRE_RECALL}" >&2
    exit 64
    ;;
esac

for key in GATEWAY_API_KEY GATEWAY_ADMIN_TOKEN OPENAI_CHAT_MODEL RUSTFS_ACCESS_KEY RUSTFS_SECRET_KEY; do
  if [[ -z "${!key}" ]]; then
    echo "Smoke test configuration is incomplete: ${key}" >&2
    exit 64
  fi
done

started_at="$(date --iso-8601=seconds)"
started_epoch="$(date +%s)"
marker="SUMEME_SMOKE_$(date -u +%Y%m%dT%H%M%SZ)_${RANDOM}"
temp_dir="$(mktemp -d)"
trap 'rm -rf "${temp_dir}"' EXIT

models_ok=false
chat_ok=false
scope_ok=false
write_ok=false
recall_ok=false
mempalace_write_ok=false
letta_write_ok=false
supermemory_write_ok=false
mempalace_recall_ok=false
letta_recall_ok=false
supermemory_recall_ok=false
s3_ok=false
error_codes=()

http_code="$(curl --silent --show-error --max-time 30 \
  --output "${temp_dir}/models.json" \
  --write-out '%{http_code}' \
  --header "Authorization: Bearer ${GATEWAY_API_KEY}" \
  "http://127.0.0.1:${GATEWAY_PORT}/v1/models" || true)"
if [[ "${http_code}" =~ ^2 ]]; then
  if python3 - "${temp_dir}/models.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    value = json.load(handle)
if not isinstance(value, dict):
    raise SystemExit(1)
if "data" not in value and "object" not in value:
    raise SystemExit(1)
PY
  then
    models_ok=true
  else
    error_codes+=("models_invalid_json")
  fi
else
  error_codes+=("models_http_${http_code:-000}")
fi

python3 - \
  "${temp_dir}/chat-request.json" \
  "${OPENAI_CHAT_MODEL}" "${marker}" "${SMOKE_VAULT_ID}" <<'PY'
import json
import sys

path, model, marker, vault_id = sys.argv[1:]
payload = {
    "model": model,
    "stream": False,
    "user": "__sumeme_smoke__",
    "metadata": {
        "conversation_id": "sumeme-production-smoke",
        "vault_id": vault_id,
        "device_id": "production-runner",
    },
    "messages": [
        {
            "role": "user",
            "content": (
                "这是 SuMeMe 隔离的自动健康测试。请记住唯一测试标记："
                f"{marker}。只回复这个测试标记，不要添加其它内容。"
            ),
        }
    ],
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False)
PY

http_code="$(curl --silent --show-error --max-time 180 \
  --output "${temp_dir}/chat-response.json" \
  --write-out '%{http_code}' \
  --header "Authorization: Bearer ${GATEWAY_API_KEY}" \
  --header 'Content-Type: application/json' \
  --data-binary "@${temp_dir}/chat-request.json" \
  "http://127.0.0.1:${GATEWAY_PORT}/v1/chat/completions" || true)"
if [[ "${http_code}" =~ ^2 ]]; then
  if python3 - "${temp_dir}/chat-response.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    value = json.load(handle)
choices = value.get("choices") if isinstance(value, dict) else None
if not isinstance(choices, list) or not choices:
    raise SystemExit(1)
message = choices[0].get("message") or {}
content = message.get("content")
if not isinstance(content, str) or not content.strip():
    raise SystemExit(1)
PY
  then
    chat_ok=true
  else
    error_codes+=("chat_invalid_response")
  fi
else
  error_codes+=("chat_http_${http_code:-000}")
fi

if [[ "${chat_ok}" == "true" ]]; then
  python3 - \
    "${temp_dir}/checkpoint-request.json" \
    "${temp_dir}/chat-request.json" \
    "${marker}" "${SMOKE_ACCOUNT_ID}" "${SMOKE_VAULT_ID}" <<'PY'
import json
import sys

output_path, chat_path, marker, account_id, vault_id = sys.argv[1:]
with open(chat_path, encoding="utf-8") as handle:
    chat_payload = json.load(handle)
body = {
    "principal_type": "service",
    "account_id": account_id,
    "vault_id": vault_id,
    "conversation_id": "sumeme-production-smoke",
    "request_payload": chat_payload,
    "assistant_text": marker,
}
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(body, handle, ensure_ascii=False)
PY

  http_code="$(curl --silent --show-error --max-time 360 \
    --output "${temp_dir}/checkpoint-response.json" \
    --write-out '%{http_code}' \
    --header "Authorization: Bearer ${GATEWAY_ADMIN_TOKEN}" \
    --header 'Content-Type: application/json' \
    --data-binary "@${temp_dir}/checkpoint-request.json" \
    "http://127.0.0.1:${GATEWAY_PORT}/api/memory/checkpoint" || true)"

  if [[ "${http_code}" =~ ^2 ]]; then
    read -r response_scope response_provider write_result mempalace_result letta_result supermemory_result write_errors < <(
      python3 - "${temp_dir}/checkpoint-response.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    value = json.load(handle)
write = value.get("write") if isinstance(value, dict) else {}
components = write.get("components") if isinstance(write, dict) else {}
errors = write.get("error_codes") if isinstance(write, dict) else []
print(
    value.get("scope", "unknown") if isinstance(value, dict) else "unknown",
    write.get("provider", "unknown") if isinstance(write, dict) else "unknown",
    "true" if write.get("success") is True else "false",
    "true" if components.get("mempalace") is True else "false",
    "true" if components.get("letta") is True else "false",
    "true" if components.get("supermemory") is True else "false",
    ",".join(str(item) for item in errors) or "none",
)
PY
    )

    [[ "${response_scope}" == "${SMOKE_SCOPE}" ]] && scope_ok=true
    [[ "${response_provider}" == "${MEMORY_PROVIDER}" && "${write_result}" == "true" ]] && write_ok=true
    [[ "${mempalace_result}" == "true" ]] && mempalace_write_ok=true
    [[ "${letta_result}" == "true" ]] && letta_write_ok=true
    [[ "${supermemory_result}" == "true" ]] && supermemory_write_ok=true

    [[ "${response_scope}" == "${SMOKE_SCOPE}" ]] || error_codes+=("checkpoint_scope_mismatch")
    [[ "${response_provider}" == "${MEMORY_PROVIDER}" ]] || error_codes+=("checkpoint_provider_mismatch")
    if [[ "${write_errors}" != "none" ]]; then
      IFS=',' read -ra checkpoint_errors <<<"${write_errors}"
      error_codes+=("${checkpoint_errors[@]}")
    fi
    [[ "${write_result}" == "true" ]] || error_codes+=("memory_checkpoint_failed")
  else
    error_codes+=("memory_checkpoint_http_${http_code:-000}")
  fi
fi

if [[ "${write_ok}" == "true" ]]; then
  for ((attempt = 1; attempt <= SMOKE_MEMORY_ATTEMPTS; attempt++)); do
    python3 - \
      "${temp_dir}/memory-request.json" \
      "${marker}" "${SMOKE_ACCOUNT_ID}" "${SMOKE_VAULT_ID}" <<'PY'
import json
import sys

path, marker, account_id, vault_id = sys.argv[1:]
with open(path, "w", encoding="utf-8") as handle:
    json.dump(
        {
            "query": f"请召回唯一测试标记 {marker}",
            "principal_type": "service",
            "account_id": account_id,
            "vault_id": vault_id,
        },
        handle,
        ensure_ascii=False,
    )
PY
    http_code="$(curl --silent --show-error --max-time 180 \
      --output "${temp_dir}/memory-response.json" \
      --write-out '%{http_code}' \
      --header "Authorization: Bearer ${GATEWAY_ADMIN_TOKEN}" \
      --header 'Content-Type: application/json' \
      --data-binary "@${temp_dir}/memory-request.json" \
      "http://127.0.0.1:${GATEWAY_PORT}/api/memory/search" || true)"

    if [[ "${http_code}" =~ ^2 ]]; then
      read -r response_provider response_scope mempalace_hit letta_hit supermemory_hit < <(
        python3 - "${temp_dir}/memory-response.json" "${marker}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    value = json.load(handle)
provider = value.get("provider", "") if isinstance(value, dict) else ""
scope = value.get("scope", "") if isinstance(value, dict) else ""
context = value.get("context", "") if isinstance(value, dict) else ""
marker = sys.argv[2]
print(
    provider or "unknown",
    scope or "unknown",
    "true" if "MemPalace 原始历史片段" in context and marker in context else "false",
    "true" if "Letta 结构化个人记忆" in context else "false",
    "true" if "Supermemory 个人记忆候选" in context and marker in context else "false",
)
PY
      )

      if [[ "${response_provider}" != "${MEMORY_PROVIDER}" ]]; then
        error_codes+=("memory_provider_mismatch")
        break
      fi
      if [[ "${response_scope}" != "${SMOKE_SCOPE}" ]]; then
        error_codes+=("memory_scope_mismatch")
        break
      fi

      mempalace_recall_ok="${mempalace_hit}"
      letta_recall_ok="${letta_hit}"
      supermemory_recall_ok="${supermemory_hit}"

      if [[ "${MEMORY_PROVIDER}" == "mempalace-letta" ]]; then
        [[ "${mempalace_recall_ok}" == "true" && "${letta_recall_ok}" == "true" ]] && recall_ok=true
      else
        [[ "${supermemory_recall_ok}" == "true" ]] && recall_ok=true
      fi
    fi

    [[ "${recall_ok}" == "true" ]] && break
    if (( attempt < SMOKE_MEMORY_ATTEMPTS )); then
      sleep "${SMOKE_MEMORY_DELAY_SECONDS}"
    fi
  done
fi

if [[ "${recall_ok}" != "true" ]]; then
  if [[ "${MEMORY_PROVIDER}" == "mempalace-letta" ]]; then
    [[ "${mempalace_recall_ok}" == "true" ]] || error_codes+=("mempalace_recall_delayed")
    [[ "${letta_recall_ok}" == "true" ]] || error_codes+=("letta_recall_delayed")
  else
    error_codes+=("supermemory_recall_delayed")
  fi
fi
[[ "${scope_ok}" == "true" ]] || error_codes+=("service_scope_verification_failed")

s3_object="services/${SMOKE_ACCOUNT_ID}/vaults/${SMOKE_VAULT_ID}/${marker}.txt"
if docker compose run --rm --no-deps -T \
  -e "RUSTFS_ACCESS_KEY=${RUSTFS_ACCESS_KEY}" \
  -e "RUSTFS_SECRET_KEY=${RUSTFS_SECRET_KEY}" \
  -e "RUSTFS_LOBE_BUCKET=${RUSTFS_LOBE_BUCKET}" \
  -e "SMOKE_MARKER=${marker}" \
  -e "SMOKE_OBJECT=${s3_object}" \
  --entrypoint /bin/sh rustfs-init -c '
    set -eu
    mc alias set smoke http://rustfs:9000 "$RUSTFS_ACCESS_KEY" "$RUSTFS_SECRET_KEY" >/dev/null
    printf "%s" "$SMOKE_MARKER" | mc pipe "smoke/$RUSTFS_LOBE_BUCKET/$SMOKE_OBJECT" >/dev/null
    actual="$(mc cat "smoke/$RUSTFS_LOBE_BUCKET/$SMOKE_OBJECT")"
    test "$actual" = "$SMOKE_MARKER"
    mc rm "smoke/$RUSTFS_LOBE_BUCKET/$SMOKE_OBJECT" >/dev/null
  ' >/dev/null 2>&1; then
  s3_ok=true
else
  error_codes+=("s3_roundtrip_failed")
fi

finished_at="$(date --iso-8601=seconds)"
duration_seconds="$(( $(date +%s) - started_epoch ))"
deployment_gate="success"
overall="success"
if [[ "${models_ok}" != "true" || "${chat_ok}" != "true" || \
      "${scope_ok}" != "true" || "${write_ok}" != "true" || \
      "${s3_ok}" != "true" ]]; then
  deployment_gate="failure"
  overall="failure"
elif [[ "${recall_ok}" != "true" ]]; then
  overall="degraded"
  if [[ "${SMOKE_REQUIRE_RECALL}" == "true" ]]; then
    deployment_gate="failure"
  fi
fi

errors_json="$(printf '%s\n' "${error_codes[@]:-}" | python3 -c 'import json,sys; print(json.dumps(list(dict.fromkeys(x for x in (line.strip() for line in sys.stdin) if x))))')"
python3 - \
  "${OUTPUT_PATH}.tmp" \
  "${started_at}" "${finished_at}" "${duration_seconds}" "${overall}" \
  "${deployment_gate}" "${MEMORY_PROVIDER}" "${SMOKE_SCOPE}" \
  "${SMOKE_REQUIRE_RECALL}" "${models_ok}" "${chat_ok}" "${scope_ok}" \
  "${write_ok}" "${recall_ok}" "${mempalace_write_ok}" "${letta_write_ok}" \
  "${supermemory_write_ok}" "${mempalace_recall_ok}" "${letta_recall_ok}" \
  "${supermemory_recall_ok}" "${s3_ok}" "${errors_json}" <<'PY'
import json
import sys

(
    output_path,
    started_at,
    finished_at,
    duration_seconds,
    overall,
    deployment_gate,
    memory_provider,
    test_scope,
    require_recall,
    models_ok,
    chat_ok,
    scope_ok,
    write_ok,
    recall_ok,
    mempalace_write_ok,
    letta_write_ok,
    supermemory_write_ok,
    mempalace_recall_ok,
    letta_recall_ok,
    supermemory_recall_ok,
    s3_ok,
    errors_json,
) = sys.argv[1:]

checks = {
    "models": models_ok == "true",
    "chat": chat_ok == "true",
    "scope": scope_ok == "true",
    "memory_write": write_ok == "true",
    "memory_recall": recall_ok == "true",
    "s3": s3_ok == "true",
}
write_components = {}
recall_components = {}
if memory_provider == "mempalace-letta":
    write_components = {
        "mempalace": mempalace_write_ok == "true",
        "letta": letta_write_ok == "true",
    }
    recall_components = {
        "mempalace": mempalace_recall_ok == "true",
        "letta": letta_recall_ok == "true",
    }
else:
    write_components = {"supermemory": supermemory_write_ok == "true"}
    recall_components = {"supermemory": supermemory_recall_ok == "true"}

result = {
    "schema_version": 4,
    "generated_at": finished_at,
    "started_at": started_at,
    "finished_at": finished_at,
    "duration_seconds": int(duration_seconds),
    "overall": overall,
    "deployment_gate": deployment_gate,
    "memory_provider": memory_provider,
    "test_scope": test_scope,
    "require_recall": require_recall == "true",
    "checks": checks,
    "write_components": write_components,
    "recall_components": recall_components,
    "error_codes": json.loads(errors_json),
}
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(result, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
PY
mv "${OUTPUT_PATH}.tmp" "${OUTPUT_PATH}"

printf 'SuMeMe smoke test: overall=%s gate=%s provider=%s scope=%s models=%s chat=%s write=%s recall=%s s3=%s duration=%ss\n' \
  "${overall}" "${deployment_gate}" "${MEMORY_PROVIDER}" "${SMOKE_SCOPE}" \
  "${models_ok}" "${chat_ok}" "${write_ok}" "${recall_ok}" "${s3_ok}" \
  "${duration_seconds}"

[[ "${deployment_gate}" == "success" ]]
