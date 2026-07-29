#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE_DIR="${SOURCE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DEPLOY_DIR="${DEPLOY_DIR:-/opt/sumeme}"
TARGET_SHA="${1:-${GITHUB_SHA:-unknown}}"
STATE_DIR="${DEPLOY_DIR}/.deploy"
RELEASE_DIR="${STATE_DIR}/releases"
LOCK_FILE="${STATE_DIR}/deploy.lock"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing command: $1" >&2
    exit 1
  }
}

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

need docker
need rsync
need tar
need curl
need flock
need python3

mkdir -p "${DEPLOY_DIR}" "${STATE_DIR}" "${RELEASE_DIR}"
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "Another SuMeMe deployment is already running." >&2
  exit 1
fi

if [[ ! -f "${DEPLOY_DIR}/.env" ]]; then
  echo "Missing ${DEPLOY_DIR}/.env; refusing to deploy." >&2
  exit 1
fi

CURRENT_SHA="$(cat "${STATE_DIR}/current_sha" 2>/dev/null || true)"
if [[ -z "${CURRENT_SHA}" && -d "${DEPLOY_DIR}/.git" ]]; then
  CURRENT_SHA="$(git -C "${DEPLOY_DIR}" rev-parse HEAD 2>/dev/null || true)"
fi
CURRENT_SHA="${CURRENT_SHA:-initial}"

snapshot_current() {
  local snapshot_sha="$1"
  local archive="${RELEASE_DIR}/${snapshot_sha}.tar.gz"
  if [[ "${snapshot_sha}" == "initial" || -f "${archive}" ]]; then
    return 0
  fi

  echo "Creating code snapshot: ${archive}"
  tar \
    --exclude=.git \
    --exclude=.env \
    --exclude=.deploy \
    --exclude=backups \
    -C "${DEPLOY_DIR}" -czf "${archive}" .
}

restore_snapshot() {
  local snapshot_sha="$1"
  local archive="${RELEASE_DIR}/${snapshot_sha}.tar.gz"
  if [[ ! -f "${archive}" ]]; then
    echo "Rollback archive not found: ${archive}" >&2
    return 1
  fi

  local temp_dir
  temp_dir="$(mktemp -d)"
  tar -xzf "${archive}" -C "${temp_dir}"
  rsync -a --delete \
    --exclude=.env \
    --exclude=.git \
    --exclude=.deploy \
    --exclude=backups \
    "${temp_dir}/" "${DEPLOY_DIR}/"
  rm -rf "${temp_dir}"
}

rollback_on_error() {
  local exit_code=$?
  trap - ERR
  echo "Deployment failed with exit code ${exit_code}."

  if [[ "${CURRENT_SHA}" != "initial" ]]; then
    echo "Restoring previous code release ${CURRENT_SHA}..."
    restore_snapshot "${CURRENT_SHA}" || true
    cd "${DEPLOY_DIR}"
    docker compose build memory-gateway || true
    docker compose up -d --remove-orphans || true
    DEPLOY_DIR="${DEPLOY_DIR}" bash scripts/health-check.sh || true
    printf '%s\n' "${CURRENT_SHA}" > "${STATE_DIR}/current_sha"
  else
    echo "No previous code snapshot is available for automatic rollback."
  fi

  echo "Important: code rollback does not reverse database migrations." >&2
  exit "${exit_code}"
}
trap rollback_on_error ERR

run_disk_preflight() {
  local output status level
  set +e
  output="$(DEPLOY_DIR="${DEPLOY_DIR}" bash "${SOURCE_DIR}/scripts/preflight-disk.sh" --json)"
  status=$?
  set -e
  echo "Disk preflight: ${output}"
  level="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read()).get("level", "unknown"))' <<<"${output}" 2>/dev/null || echo unknown)"

  if [[ "${level}" == "warning" || "${status}" -eq 2 ]]; then
    echo "Running safe cleanup before image pull/build..."
    DEPLOY_DIR="${DEPLOY_DIR}" bash "${SOURCE_DIR}/scripts/cleanup-runtime.sh"
    set +e
    output="$(DEPLOY_DIR="${DEPLOY_DIR}" bash "${SOURCE_DIR}/scripts/preflight-disk.sh" --json)"
    status=$?
    set -e
    echo "Disk preflight after cleanup: ${output}"
  fi

  if [[ "${status}" -ne 0 ]]; then
    echo "Disk preflight failed; deployment is blocked to protect production data." >&2
    return "${status}"
  fi
}

run_disk_preflight
snapshot_current "${CURRENT_SHA}"

printf '%s\n' "${CURRENT_SHA}" > "${STATE_DIR}/previous_sha"
printf '%s\n' "${TARGET_SHA}" > "${STATE_DIR}/deploying_sha"

rsync -a --delete \
  --exclude=.env \
  --exclude=.git \
  --exclude=.deploy \
  --exclude=backups \
  "${SOURCE_DIR}/" "${DEPLOY_DIR}/"

chmod +x "${DEPLOY_DIR}"/scripts/*.sh
cd "${DEPLOY_DIR}"

docker compose config >/dev/null
docker compose pull
docker compose build memory-gateway
docker compose up -d --remove-orphans

DEPLOY_DIR="${DEPLOY_DIR}" bash scripts/health-check.sh

SMOKE_TEST_MODE="$(read_env SMOKE_TEST_MODE warn)"
case "${SMOKE_TEST_MODE}" in
  off)
    echo "Production smoke test is disabled."
    ;;
  warn|required)
    set +e
    DEPLOY_DIR="${DEPLOY_DIR}" bash scripts/smoke-test.sh
    smoke_status=$?
    set -e
    if (( smoke_status != 0 )); then
      if [[ "${SMOKE_TEST_MODE}" == "required" ]]; then
        echo "Required production smoke test failed." >&2
        false
      fi
      echo "WARNING: production smoke test failed; deployment remains active because mode=warn." >&2
    fi
    ;;
  *)
    echo "Invalid SMOKE_TEST_MODE=${SMOKE_TEST_MODE}; expected off, warn, or required." >&2
    false
    ;;
esac

printf '%s\n' "${TARGET_SHA}" > "${STATE_DIR}/current_sha"
rm -f "${STATE_DIR}/deploying_sha"
printf '%s %s\n' "$(date --iso-8601=seconds)" "${TARGET_SHA}" >> "${STATE_DIR}/history.log"

trap - ERR
echo "SuMeMe deployment succeeded: ${TARGET_SHA}"
