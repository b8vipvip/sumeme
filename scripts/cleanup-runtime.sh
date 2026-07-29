#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/sumeme}"
STATE_DIR="${DEPLOY_DIR}/.deploy"
RELEASE_DIR="${STATE_DIR}/releases"
KEEP_RELEASES="${KEEP_RELEASES:-5}"
DOCKER_PRUNE_UNTIL="${DOCKER_PRUNE_UNTIL:-168h}"
DRY_RUN=false

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
fi

if ! [[ "${KEEP_RELEASES}" =~ ^[0-9]+$ ]] || (( KEEP_RELEASES < 2 )); then
  echo "KEEP_RELEASES must be an integer of at least 2." >&2
  exit 64
fi

command -v docker >/dev/null 2>&1 || {
  echo "Docker is required." >&2
  exit 127
}

mkdir -p "${STATE_DIR}" "${RELEASE_DIR}"
exec 9>"${STATE_DIR}/cleanup.lock"
if ! flock -n 9; then
  echo "Another SuMeMe cleanup is already running." >&2
  exit 1
fi

usage_line() {
  df -hP "${DEPLOY_DIR}" | awk 'NR == 2 {print "disk=" $5 " used=" $3 " free=" $4 " total=" $2}'
}

echo "Before cleanup: $(usage_line)"
echo "Policy: keep ${KEEP_RELEASES} code snapshots; prune only old build cache and dangling images."
echo "Data volumes are never pruned by this script."

if [[ "${DRY_RUN}" == "true" ]]; then
  echo "[dry-run] docker builder prune --filter until=${DOCKER_PRUNE_UNTIL}"
  echo "[dry-run] docker image prune --filter until=${DOCKER_PRUNE_UNTIL}"
else
  docker builder prune --force --filter "until=${DOCKER_PRUNE_UNTIL}" || true
  docker image prune --force --filter "until=${DOCKER_PRUNE_UNTIL}" || true
fi

mapfile -t release_files < <(
  find "${RELEASE_DIR}" -maxdepth 1 -type f -name '*.tar.gz' -printf '%T@ %p\n' \
    | sort -nr \
    | awk '{sub(/^[^ ]+ /, ""); print}'
)

if (( ${#release_files[@]} > KEEP_RELEASES )); then
  for file in "${release_files[@]:KEEP_RELEASES}"; do
    if [[ "${DRY_RUN}" == "true" ]]; then
      echo "[dry-run] remove old release snapshot: ${file}"
    else
      rm -f -- "${file}"
      echo "Removed old release snapshot: ${file}"
    fi
  done
else
  echo "Release snapshot retention already satisfied (${#release_files[@]}/${KEEP_RELEASES})."
fi

if [[ "${DRY_RUN}" != "true" ]]; then
  find "${STATE_DIR}" -maxdepth 1 -type f -name '*.tmp' -mtime +1 -delete
fi

echo "After cleanup:  $(usage_line)"
