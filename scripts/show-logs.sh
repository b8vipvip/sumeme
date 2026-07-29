#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/sumeme}"
SERVICE="${1:-memory-gateway}"
LINES="${2:-200}"
SINCE="${3:-30m}"

allowed_services=(
  lobe
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

cd "${DEPLOY_DIR}"

docker compose logs --no-color --tail "${LINES}" --since "${SINCE}" "${SERVICE}" 2>&1 \
  | sed -E \
      -e 's/(Authorization:[[:space:]]*Bearer[[:space:]]+)[A-Za-z0-9._~+\/-]+/\1[REDACTED]/Ig' \
      -e 's/(api[_-]?key["'"'=: ]+)[A-Za-z0-9._~+\/-]{8,}/\1[REDACTED]/Ig' \
      -e 's/(password["'"'=: ]+)[^ ,}"'"']{6,}/\1[REDACTED]/Ig' \
      -e 's/sk-[A-Za-z0-9_-]{10,}/sk-[REDACTED]/g' \
      -e 's/(postgresql:\/\/[^:[:space:]]+:)[^@[:space:]]+@/\1[REDACTED]@/Ig'