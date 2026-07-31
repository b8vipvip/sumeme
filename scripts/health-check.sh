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
PUBLIC_UI_SMOKE_MODE="$(read_env PUBLIC_UI_SMOKE_MODE required)"

expected_services=(
  sumeme-web
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

public_app="$(curl --fail --silent --show-error --location --max-time 30 \
  "${APP_URL}" || true)"
if grep -Fq '<title>SuMeMe · 服务端</title>' <<<"${public_app}" && \
   grep -Fq '服务端管理中心' <<<"${public_app}"; then
  echo "[ OK ] native SuMeMe server UI: ${APP_URL}"
else
  echo "[FAIL] native SuMeMe server UI missing or invalid: ${APP_URL}"
  failed=1
fi

case "${PUBLIC_UI_SMOKE_MODE}" in
  off)
    echo "[SKIP] public UI smoke is disabled"
    ;;
  warn|required)
    ui_ok=false
    for attempt in 1 2 3 4 5; do
      echo "Public UI smoke attempt ${attempt}/5..."
      if python3 scripts/smoke-public-ui.py "${APP_URL%/}/" --timeout 30; then
        ui_ok=true
        break
      fi
      sleep 5
    done

    if [[ "${ui_ok}" == "true" ]]; then
      echo "[ OK ] public SuMeMe UI"
    elif [[ "${PUBLIC_UI_SMOKE_MODE}" == "required" ]]; then
      echo "[FAIL] public SuMeMe UI is unavailable or invalid"
      failed=1
    else
      echo "[WARN] public SuMeMe UI is unavailable or invalid"
    fi
    ;;
  *)
    echo "[FAIL] invalid PUBLIC_UI_SMOKE_MODE=${PUBLIC_UI_SMOKE_MODE}; expected off, warn, or required"
    failed=1
    ;;
esac

if (( failed != 0 )); then
  echo "SuMeMe health check failed." >&2
  exit 1
fi

echo "SuMeMe health check passed."
