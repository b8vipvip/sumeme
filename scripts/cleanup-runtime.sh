#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/sumeme}"
STATE_DIR="${DEPLOY_DIR}/.deploy"
RELEASE_DIR="${STATE_DIR}/releases"
ADOB_STAGING_ROOT="${ADOB_STAGING_ROOT:-${DEPLOY_DIR}.adob}"
INCOMING_DIR="${ADOB_STAGING_ROOT}/incoming"
KEEP_RELEASES="${KEEP_RELEASES:-5}"
KEEP_STAGING_RELEASES="${KEEP_STAGING_RELEASES:-3}"
DOCKER_PRUNE_UNTIL="${DOCKER_PRUNE_UNTIL:-168h}"
AGGRESSIVE_CLEANUP="${AGGRESSIVE_CLEANUP:-false}"
SOURCE_DIR="${SOURCE_DIR:-}"
DRY_RUN=false

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
fi

if ! [[ "${KEEP_RELEASES}" =~ ^[0-9]+$ ]] || (( KEEP_RELEASES < 2 )); then
  echo "KEEP_RELEASES must be an integer of at least 2." >&2
  exit 64
fi
if ! [[ "${KEEP_STAGING_RELEASES}" =~ ^[0-9]+$ ]] || (( KEEP_STAGING_RELEASES < 1 )); then
  echo "KEEP_STAGING_RELEASES must be an integer of at least 1." >&2
  exit 64
fi
if [[ "${AGGRESSIVE_CLEANUP}" != "true" && "${AGGRESSIVE_CLEANUP}" != "false" ]]; then
  echo "AGGRESSIVE_CLEANUP must be true or false." >&2
  exit 64
fi

for command in docker flock find sort awk df; do
  command -v "${command}" >/dev/null 2>&1 || {
    echo "Required cleanup command is missing: ${command}" >&2
    exit 127
  }
done

mkdir -p "${STATE_DIR}" "${RELEASE_DIR}"
exec 9>"${STATE_DIR}/cleanup.lock"
if ! flock -n 9; then
  echo "Another SuMeMe cleanup is already running." >&2
  exit 1
fi

usage_line() {
  df -hP "${DEPLOY_DIR}" | awk 'NR == 2 {print "disk=" $5 " used=" $3 " free=" $4 " total=" $2}'
}

is_protected_release() {
  local file="$1"
  local sha
  for marker in current_sha previous_sha; do
    sha="$(cat "${STATE_DIR}/${marker}" 2>/dev/null || true)"
    if [[ -n "${sha}" && "${file}" == "${RELEASE_DIR}/${sha}.tar.gz" ]]; then
      return 0
    fi
  done
  return 1
}

remove_path() {
  local label="$1"
  local path="$2"
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[dry-run] remove ${label}: ${path}"
  else
    rm -rf -- "${path}"
    echo "Removed ${label}: ${path}"
  fi
}

echo "Before cleanup: $(usage_line)"
echo "Policy: preserve data volumes, active containers and current/previous rollback snapshots."
echo "Retention: ${KEEP_RELEASES} code snapshots and ${KEEP_STAGING_RELEASES} uploaded source trees."
echo "Data volumes are never pruned by this script."

if [[ "${AGGRESSIVE_CLEANUP}" == "true" ]]; then
  echo "Critical disk pressure detected: removing all rebuildable Docker build cache and unused images."
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[dry-run] docker builder prune --all --force"
    echo "[dry-run] docker image prune --all --force"
  else
    docker builder prune --all --force || true
    # Docker does not remove images referenced by any container. No volume prune
    # is performed, so PostgreSQL, Redis, RustFS and memory data remain untouched.
    docker image prune --all --force || true
  fi
else
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[dry-run] docker builder prune --force --filter until=${DOCKER_PRUNE_UNTIL}"
    echo "[dry-run] docker image prune --force --filter until=${DOCKER_PRUNE_UNTIL}"
  else
    docker builder prune --force --filter "until=${DOCKER_PRUNE_UNTIL}" || true
    docker image prune --force --filter "until=${DOCKER_PRUNE_UNTIL}" || true
  fi
fi

# Failed GHS deployments leave immutable uploads under /opt/sumeme.adob/incoming.
# They are complete copies of GitHub source and can always be re-uploaded. Keep
# the newest few and never remove the source tree executing this cleanup.
if [[ -d "${INCOMING_DIR}" ]]; then
  mapfile -t incoming_dirs < <(
    find "${INCOMING_DIR}" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' \
      | sort -nr \
      | awk '{sub(/^[^ ]+ /, ""); print}'
  )
  resolved_source=""
  if [[ -n "${SOURCE_DIR}" ]]; then
    resolved_source="$(readlink -f "${SOURCE_DIR}" 2>/dev/null || true)"
  fi

  if (( ${#incoming_dirs[@]} > KEEP_STAGING_RELEASES )); then
    for index in "${!incoming_dirs[@]}"; do
      directory="${incoming_dirs[$index]}"
      resolved_directory="$(readlink -f "${directory}" 2>/dev/null || true)"
      if [[ -n "${resolved_source}" && "${resolved_directory}" == "${resolved_source}" ]]; then
        echo "Preserved active uploaded source tree: ${directory}"
        continue
      fi
      if (( index < KEEP_STAGING_RELEASES )); then
        continue
      fi
      remove_path "old uploaded source tree" "${directory}"
    done
  else
    echo "Uploaded source retention already satisfied (${#incoming_dirs[@]}/${KEEP_STAGING_RELEASES})."
  fi
else
  echo "No uploaded source staging directory found at ${INCOMING_DIR}."
fi

mapfile -t release_files < <(
  find "${RELEASE_DIR}" -maxdepth 1 -type f -name '*.tar.gz' -printf '%T@ %p\n' \
    | sort -nr \
    | awk '{sub(/^[^ ]+ /, ""); print}'
)

if (( ${#release_files[@]} > KEEP_RELEASES )); then
  for index in "${!release_files[@]}"; do
    file="${release_files[$index]}"
    if (( index < KEEP_RELEASES )); then
      continue
    fi
    if is_protected_release "${file}"; then
      echo "Preserved protected rollback snapshot: ${file}"
      continue
    fi
    remove_path "old release snapshot" "${file}"
  done
else
  echo "Release snapshot retention already satisfied (${#release_files[@]}/${KEEP_RELEASES})."
fi

if [[ "${DRY_RUN}" != "true" ]]; then
  find "${STATE_DIR}" -maxdepth 1 -type f -name '*.tmp' -mtime +1 -delete
fi

echo "After cleanup:  $(usage_line)"
