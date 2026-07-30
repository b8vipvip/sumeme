#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/sumeme}"
SERVICE="${1:-memory-gateway}"
LINES="${2:-200}"
SINCE="${3:-30m}"

allowed_services=(
  lobe
  ai-provider-proxy
  memory-gateway
  letta
  postgresql
  qdrant
  redis
  rustfs
  searxng
)

allowed=false
for item in "${allowed_services[@]}"; do
  if [[ "${SERVICE}" == "${item}" ]]; then
    allowed=true
    break
  fi
done

if [[ "${allowed}" != "true" ]]; then
  echo "Service is not allowed: ${SERVICE}" >&2
  exit 2
fi

if ! [[ "${LINES}" =~ ^[0-9]+$ ]] || (( LINES < 1 || LINES > 1000 )); then
  echo "LINES must be an integer between 1 and 1000." >&2
  exit 2
fi

if ! [[ "${SINCE}" =~ ^[0-9]+[smhd]$ ]]; then
  echo "SINCE must look like 30m, 2h, or 1d." >&2
  exit 2
fi

command -v docker >/dev/null 2>&1 || {
  echo "Missing command: docker" >&2
  exit 127
}
command -v python3 >/dev/null 2>&1 || {
  echo "Missing command: python3" >&2
  exit 127
}

cd "${DEPLOY_DIR}"

docker compose logs --no-color --tail "${LINES}" --since "${SINCE}" "${SERVICE}" 2>&1 \
  | python3 scripts/redact-log-stream.py
