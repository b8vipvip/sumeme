#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE_DIR="${SOURCE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DEPLOY_DIR="${DEPLOY_DIR:-/opt/sumeme}"
TARGET_SHA="${1:-${GITHUB_SHA:-unknown}}"
STATE_DIR="${DEPLOY_DIR}/.deploy"
RELEASE_DIR="${STATE_DIR}/releases"
LOCK_FILE="${STATE_DIR}/deploy.lock"
LOCK_OWNER_FILE="${STATE_DIR}/deploy.lock.owner"
DEPLOY_LOCK_WAIT_SECONDS="${DEPLOY_LOCK_WAIT_SECONDS:-1800}"

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

for command in docker rsync tar curl flock python3; do
  need "${command}"
done

if [[ ! "${DEPLOY_LOCK_WAIT_SECONDS}" =~ ^[0-9]+$ ]] || (( DEPLOY_LOCK_WAIT_SECONDS > 7200 )); then
  echo "Invalid DEPLOY_LOCK_WAIT_SECONDS=${DEPLOY_LOCK_WAIT_SECONDS}; expected 0-7200 seconds." >&2
  exit 64
fi

mkdir -p "${DEPLOY_DIR}" "${STATE_DIR}" "${RELEASE_DIR}"
exec 9>"${LOCK_FILE}"

echo "Waiting up to ${DEPLOY_LOCK_WAIT_SECONDS}s for the SuMeMe production deployment lock..."
if ! flock -w "${DEPLOY_LOCK_WAIT_SECONDS}" 9; then
  echo "Timed out waiting for the SuMeMe production deployment lock." >&2
  if [[ -s "${LOCK_OWNER_FILE}" ]]; then
    echo "Last recorded lock owner:" >&2
    sed -n '1,10p' "${LOCK_OWNER_FILE}" >&2 || true
  fi
  if command -v fuser >/dev/null 2>&1; then
    echo "Processes currently holding or using ${LOCK_FILE}:" >&2
    fuser -v "${LOCK_FILE}" >&2 || true
  fi
  exit 75
fi

cleanup_lock_owner() {
  rm -f "${LOCK_OWNER_FILE}"
}
trap cleanup_lock_owner EXIT

{
  printf 'pid=%s\n' "$$"
  printf 'target_sha=%s\n' "${TARGET_SHA}"
  printf 'started_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'source_dir=%s\n' "${SOURCE_DIR}"
} > "${LOCK_OWNER_FILE}"

echo "Acquired SuMeMe production deployment lock."

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

compose_project_name() {
  local configured
  configured="$(read_env COMPOSE_PROJECT_NAME)"
  if [[ -n "${configured}" ]]; then
    printf '%s' "${configured}"
  else
    basename "${DEPLOY_DIR}"
  fi
}

build_local_services() {
  local configured_services
  local candidate
  local -a build_services=()

  configured_services="$(docker compose config --services)"
  for candidate in memory-gateway ai-provider-proxy; do
    if grep -Fxq "${candidate}" <<<"${configured_services}"; then
      build_services+=("${candidate}")
    fi
  done

  if (( ${#build_services[@]} == 0 )); then
    echo "No locally built runtime services are present in this Compose snapshot."
    return 0
  fi

  echo "Building local runtime services: ${build_services[*]}"
  docker compose build "${build_services[@]}"
}

compose_up_resilient() {
  if docker compose up -d --remove-orphans; then
    return 0
  fi

  local project
  project="$(compose_project_name)"
  echo "Compose convergence failed; recreating project containers without deleting volumes." >&2
  mapfile -t project_containers < <(
    docker ps -aq --filter "label=com.docker.compose.project=${project}"
  )
  if (( ${#project_containers[@]} > 0 )); then
    docker rm -f "${project_containers[@]}"
  fi
  docker network rm "${project}" >/dev/null 2>&1 || true
  docker compose up -d --remove-orphans
}

classify_and_annotate_smoke() {
  local smoke_path="$1"
  python3 - "${smoke_path}" <<'PY'
import json
import os
import sys
import tempfile
from pathlib import Path

path = Path(sys.argv[1])
try:
    value = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    print("unknown")
    raise SystemExit(0)

checks = value.get("checks") if isinstance(value, dict) else None
classification = "critical"
if isinstance(checks, dict) and (
    checks.get("models") is False or checks.get("chat") is False
):
    classification = "external_degraded"

value["deployment_classification"] = classification
if classification == "external_degraded":
    value["deployment_gate"] = "external_degraded"
    if value.get("overall") == "failure":
        value["overall"] = "degraded"

path.parent.mkdir(parents=True, exist_ok=True)
fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, path)
finally:
    try:
        os.unlink(temporary)
    except FileNotFoundError:
        pass

print(classification)
PY
}

print_failure_diagnostics() {
  local smoke_path="${STATE_DIR}/smoke/latest.json"

  echo "== Sanitized deployment failure diagnostics ==" >&2
  if [[ -f "${smoke_path}" ]]; then
    python3 - "${smoke_path}" <<'PY' >&2 || true
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        value = json.load(handle)
except Exception:
    print("smoke_result=unreadable")
    raise SystemExit(0)

summary = {
    "overall": value.get("overall"),
    "deployment_gate": value.get("deployment_gate"),
    "deployment_classification": value.get("deployment_classification"),
    "memory_provider": value.get("memory_provider"),
    "test_scope": value.get("test_scope"),
    "checks": value.get("checks"),
    "write_components": value.get("write_components"),
    "recall_components": value.get("recall_components"),
    "error_codes": value.get("error_codes"),
    "duration_seconds": value.get("duration_seconds"),
}
print("smoke_result=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
PY
  else
    echo "smoke_result=missing" >&2
  fi

  for service in memory-gateway letta; do
    echo "== Redacted ${service} logs (last 120 lines, 20m) ==" >&2
    DEPLOY_DIR="${DEPLOY_DIR}" bash "${DEPLOY_DIR}/scripts/show-logs.sh" \
      "${service}" 120 20m >&2 || true
  done
  echo "== End sanitized deployment failure diagnostics ==" >&2
}

record_history() {
  printf '%s %s\n' "$(date --iso-8601=seconds)" "$1" >> "${STATE_DIR}/history.log"
}

rollback_on_error() {
  local deployment_exit_code=$?
  local rollback_reason=""
  local rollback_succeeded=false
  trap - ERR

  echo "Deployment failed with exit code ${deployment_exit_code}." >&2
  print_failure_diagnostics

  if [[ "${CURRENT_SHA}" == "initial" ]]; then
    rollback_reason="no_previous_snapshot"
    echo "No previous code snapshot is available for automatic rollback." >&2
  elif ! restore_snapshot "${CURRENT_SHA}"; then
    rollback_reason="snapshot_restore_failed"
  else
    cd "${DEPLOY_DIR}"
    chmod +x "${DEPLOY_DIR}"/scripts/*.sh 2>/dev/null || true
    if docker compose config >/dev/null \
      && build_local_services \
      && compose_up_resilient \
      && DEPLOY_DIR="${DEPLOY_DIR}" bash scripts/health-check.sh; then
      rollback_succeeded=true
    else
      rollback_reason="runtime_recovery_failed"
    fi
  fi

  if [[ "${rollback_succeeded}" == "true" ]]; then
    printf '%s\n' "${CURRENT_SHA}" > "${STATE_DIR}/current_sha"
    record_history "rollback target=${CURRENT_SHA} failed=${TARGET_SHA}"
    echo "Rollback health verification passed for ${CURRENT_SHA}." >&2
  else
    record_history "rollback_failed target=${CURRENT_SHA} failed=${TARGET_SHA} reason=${rollback_reason:-unknown}"
    echo "CRITICAL: rollback did not restore a healthy runtime; current_sha was not rewritten." >&2
  fi

  rm -f "${STATE_DIR}/deploying_sha"
  echo "Important: code rollback does not reverse database migrations." >&2
  exit "${deployment_exit_code}"
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
build_local_services
compose_up_resilient
DEPLOY_DIR="${DEPLOY_DIR}" bash scripts/health-check.sh

SMOKE_TEST_MODE="$(read_env SMOKE_TEST_MODE warn)"
case "${SMOKE_TEST_MODE}" in
  off)
    echo "Production smoke test is disabled."
    ;;
  warn|required)
    if DEPLOY_DIR="${DEPLOY_DIR}" bash scripts/smoke-private-object.sh; then
      private_object_status=0
    else
      private_object_status=$?
    fi

    if DEPLOY_DIR="${DEPLOY_DIR}" bash scripts/smoke-test.sh; then
      smoke_status=0
    else
      smoke_status=$?
    fi

    if (( private_object_status != 0 )); then
      echo "Critical private-object smoke failed; refusing to publish the release." >&2
      false
    fi

    if (( smoke_status != 0 )); then
      smoke_classification="$(classify_and_annotate_smoke "${STATE_DIR}/smoke/latest.json")"
      if [[ "${smoke_classification}" == "external_degraded" ]]; then
        echo "WARNING: live provider smoke is degraded; local health and private storage passed, so the release remains active." >&2
      elif [[ "${SMOKE_TEST_MODE}" == "required" ]]; then
        echo "Required local application smoke failed with classification=${smoke_classification}." >&2
        false
      else
        echo "WARNING: local application smoke failed with classification=${smoke_classification}; deployment remains active because mode=warn." >&2
      fi
    fi
    ;;
  *)
    echo "Invalid SMOKE_TEST_MODE=${SMOKE_TEST_MODE}; expected off, warn, or required." >&2
    false
    ;;
esac

printf '%s\n' "${TARGET_SHA}" > "${STATE_DIR}/current_sha"
rm -f "${STATE_DIR}/deploying_sha"
record_history "${TARGET_SHA}"

trap - ERR
echo "SuMeMe deployment succeeded: ${TARGET_SHA}"
