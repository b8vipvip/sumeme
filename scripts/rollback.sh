#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/sumeme}"
STATE_DIR="${DEPLOY_DIR}/.deploy"
RELEASE_DIR="${STATE_DIR}/releases"
LOCK_FILE="${STATE_DIR}/deploy.lock"
TARGET_SHA="${1:-$(cat "${STATE_DIR}/previous_sha" 2>/dev/null || true)}"

if [[ -z "${TARGET_SHA}" ]]; then
  echo "No rollback target was supplied and previous_sha is empty." >&2
  exit 1
fi

for command in docker rsync tar curl flock; do
  command -v "${command}" >/dev/null 2>&1 || {
    echo "Missing command: ${command}" >&2
    exit 1
  }
done

mkdir -p "${STATE_DIR}" "${RELEASE_DIR}"
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "Another SuMeMe deployment or rollback is running." >&2
  exit 1
fi

archive="${RELEASE_DIR}/${TARGET_SHA}.tar.gz"
if [[ ! -f "${archive}" ]]; then
  echo "Rollback archive not found: ${archive}" >&2
  echo "Available releases:"
  find "${RELEASE_DIR}" -maxdepth 1 -type f -name '*.tar.gz' -printf '  %f\n' 2>/dev/null || true
  exit 1
fi

CURRENT_SHA="$(cat "${STATE_DIR}/current_sha" 2>/dev/null || echo unknown)"
temp_dir="$(mktemp -d)"
trap 'rm -rf "${temp_dir}"' EXIT

tar -xzf "${archive}" -C "${temp_dir}"
rsync -a --delete \
  --exclude=.env \
  --exclude=.git \
  --exclude=.deploy \
  --exclude=backups \
  "${temp_dir}/" "${DEPLOY_DIR}/"

chmod +x "${DEPLOY_DIR}"/scripts/*.sh
cd "${DEPLOY_DIR}"
docker compose config >/dev/null
docker compose build memory-gateway
docker compose up -d --remove-orphans
DEPLOY_DIR="${DEPLOY_DIR}" bash scripts/health-check.sh

printf '%s\n' "${CURRENT_SHA}" > "${STATE_DIR}/previous_sha"
printf '%s\n' "${TARGET_SHA}" > "${STATE_DIR}/current_sha"
printf '%s rollback %s -> %s\n' "$(date --iso-8601=seconds)" "${CURRENT_SHA}" "${TARGET_SHA}" >> "${STATE_DIR}/history.log"

echo "SuMeMe rollback succeeded: ${CURRENT_SHA} -> ${TARGET_SHA}"
echo "Important: this restores application code only; database migrations are not reversed."