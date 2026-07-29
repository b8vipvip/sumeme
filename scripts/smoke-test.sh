#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/sumeme}"
OUTPUT_PATH="${SMOKE_OUTPUT_PATH:-${DEPLOY_DIR}/.deploy/smoke/latest.json}"
GATEWAY_PORT="${GATEWAY_PORT:-8010}"
SMOKE_MEMORY_ATTEMPTS="${SMOKE_MEMORY_ATTEMPTS:-4}"
SMOKE_MEMORY_DELAY_SECONDS="${SMOKE_MEMORY_DELAY_SECONDS:-12}"

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
RUSTFS_ACCESS_KEY="$(read_env RUSTFS_ACCESS_KEY)"
RUSTFS_SECRET_KEY="$(read_env RUSTFS_SECRET_KEY)"
RUSTFS_LOBE_BUCKET="$(read_env RUSTFS_LOBE_BUCKET lobe)"

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
mempalace_ok=false
letta_ok=false
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

python3 - "${temp_dir}/chat-request.json" "${OPENAI_CHAT_MODEL}" "${marker}" <<'PY'
import json
import sys

path, model, marker = sys.argv[1:]
payload = {
    "model": model,
    "stream": False,
    "user": "__sumeme_smoke__",
    "metadata": {"conversation_id": "sumeme-production-smoke"},
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
  for ((attempt = 1; attempt <= SMOKE_MEMORY_ATTEMPTS; attempt++)); do
    python3 - "${temp_dir}/memory-request.json" "${marker}" <<'PY'
import json
import sys

path, marker = sys.argv[1:]
with open(path, "w", encoding="utf-8") as handle:
    json.dump(
        {"query": f"请召回唯一测试标记 {marker}", "user_id": "__sumeme_smoke__"},
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
      read -r mempalace_hit letta_hit < <(
        python3 - "${temp_dir}/memory-response.json" "${marker}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    value = json.load(handle)
context = value.get("context", "") if isinstance(value, dict) else ""
marker = sys.argv[2]
print(
    "true" if "MemPalace 原始历史片段" in context and marker in context else "false",
    "true" if "Letta 结构化个人记忆" in context else "false",
)
PY
      )
      [[ "${mempalace_hit}" == "true" ]] && mempalace_ok=true
      [[ "${letta_hit}" == "true" ]] && letta_ok=true
    fi

    if [[ "${mempalace_ok}" == "true" && "${letta_ok}" == "true" ]]; then
      break
    fi
    if (( attempt < SMOKE_MEMORY_ATTEMPTS )); then
      sleep "${SMOKE_MEMORY_DELAY_SECONDS}"
    fi
  done
fi

[[ "${mempalace_ok}" == "true" ]] || error_codes+=("mempalace_recall_failed")
[[ "${letta_ok}" == "true" ]] || error_codes+=("letta_recall_failed")

s3_object="sumeme-smoke/${marker}.txt"
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
overall="success"
if [[ "${models_ok}" != "true" || "${chat_ok}" != "true" || \
      "${mempalace_ok}" != "true" || "${letta_ok}" != "true" || "${s3_ok}" != "true" ]]; then
  overall="failure"
fi

errors_json="$(printf '%s\n' "${error_codes[@]:-}" | python3 -c 'import json,sys; print(json.dumps([x for x in (line.strip() for line in sys.stdin) if x]))')"
python3 - "${OUTPUT_PATH}.tmp" <<PY
import json

result = {
    "schema_version": 1,
    "generated_at": ${finished_at@Q},
    "started_at": ${started_at@Q},
    "finished_at": ${finished_at@Q},
    "duration_seconds": int(${duration_seconds}),
    "overall": ${overall@Q},
    "checks": {
        "models": ${models_ok},
        "chat": ${chat_ok},
        "mempalace": ${mempalace_ok},
        "letta": ${letta_ok},
        "s3": ${s3_ok},
    },
    "error_codes": json.loads(${errors_json@Q}),
    "test_user": "__sumeme_smoke__",
}
with open(${OUTPUT_PATH@Q} + ".tmp", "w", encoding="utf-8") as handle:
    json.dump(result, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
PY
mv "${OUTPUT_PATH}.tmp" "${OUTPUT_PATH}"

printf 'SuMeMe smoke test: overall=%s models=%s chat=%s mempalace=%s letta=%s s3=%s duration=%ss\n' \
  "${overall}" "${models_ok}" "${chat_ok}" "${mempalace_ok}" "${letta_ok}" "${s3_ok}" "${duration_seconds}"

[[ "${overall}" == "success" ]]
