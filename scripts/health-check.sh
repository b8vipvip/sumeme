#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/sumeme}"
cd "${DEPLOY_DIR}"

read_env() {
  local key="$1"
  local fallback="${2:-}"
  local value
  value="$(grep -m1 -E "^${key}=" .env 2>/dev/null | cut -d= -f2- || true)"
  printf '%s' "${value:-${fallback}}"
}

GATEWAY_PORT="$(read_env GATEWAY_PORT 8010)"
APP_URL="$(read_env APP_URL https://sumeme.mv3.cn)"
PUBLIC_HEALTH_URL="${PUBLIC_HEALTH_URL:-${APP_URL%/}/sumeme-health}"

expected_services=(
  lobe
  memory-gateway
  letta
  postgresql
  qdrant
  redis
  rustfs
  searxng
)

failed=0

echo "== Docker services =="
for service in "${expected_services[@]}"; do
  container_id="$(docker compose ps -q "${service}")"
  if [[ -z "${container_id}" ]]; then
    echo "[FAIL] ${service}: container not found"
    failed=1
    continue
  fi

  state="$(docker inspect -f '{{.State.Status}}' "${container_id}")"
  health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${container_id}")"

  if [[ "${state}" != "running" ]]; then
    echo "[FAIL] ${service}: state=${state}, health=${health}"
    failed=1
  elif [[ "${health}" == "unhealthy" ]]; then
    echo "[FAIL] ${service}: state=${state}, health=${health}"
    failed=1
  else
    echo "[ OK ] ${service}: state=${state}, health=${health}"
  fi
done

echo
echo "== HTTP checks =="
if curl --fail --silent --show-error --max-time 20 \
  "http://127.0.0.1:${GATEWAY_PORT}/health" >/dev/null; then
  echo "[ OK ] memory-gateway local health"
else
  echo "[FAIL] memory-gateway local health"
  failed=1
fi

if curl --fail --silent --show-error --location --max-time 30 \
  "${PUBLIC_HEALTH_URL}" >/dev/null; then
  echo "[ OK ] public health: ${PUBLIC_HEALTH_URL}"
else
  echo "[FAIL] public health: ${PUBLIC_HEALTH_URL}"
  failed=1
fi

if curl --fail --silent --show-error --location --max-time 30 \
  "${APP_URL}" >/dev/null; then
  echo "[ OK ] public app: ${APP_URL}"
else
  echo "[FAIL] public app: ${APP_URL}"
  failed=1
fi

if (( failed != 0 )); then
  echo "SuMeMe health check failed." >&2
  exit 1
fi

echo "SuMeMe health check passed."