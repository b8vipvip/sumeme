#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/sumeme}"
DISK_WARN_PERCENT="${DISK_WARN_PERCENT:-80}"
DISK_FAIL_PERCENT="${DISK_FAIL_PERCENT:-90}"
DISK_MIN_FREE_GIB="${DISK_MIN_FREE_GIB:-3}"
OUTPUT_JSON=false

if [[ "${1:-}" == "--json" ]]; then
  OUTPUT_JSON=true
fi

for value in "${DISK_WARN_PERCENT}" "${DISK_FAIL_PERCENT}" "${DISK_MIN_FREE_GIB}"; do
  if ! [[ "${value}" =~ ^[0-9]+$ ]]; then
    echo "Disk thresholds must be non-negative integers." >&2
    exit 64
  fi
done

if (( DISK_WARN_PERCENT >= DISK_FAIL_PERCENT )); then
  echo "DISK_WARN_PERCENT must be lower than DISK_FAIL_PERCENT." >&2
  exit 64
fi

if [[ ! -d "${DEPLOY_DIR}" ]]; then
  echo "Deploy directory does not exist: ${DEPLOY_DIR}" >&2
  exit 66
fi

read -r used_percent available_kib total_kib < <(
  df -Pk "${DEPLOY_DIR}" | awk 'NR == 2 {gsub(/%/, "", $5); print $5, $4, $2}'
)

if [[ -z "${used_percent:-}" || -z "${available_kib:-}" ]]; then
  echo "Could not read disk usage for ${DEPLOY_DIR}." >&2
  exit 1
fi

min_free_kib=$((DISK_MIN_FREE_GIB * 1024 * 1024))
level="ok"
exit_code=0
message="Disk capacity is within configured limits."

if (( used_percent >= DISK_FAIL_PERCENT || available_kib < min_free_kib )); then
  level="critical"
  exit_code=2
  message="Disk capacity is below the safe deployment threshold."
elif (( used_percent >= DISK_WARN_PERCENT )); then
  level="warning"
  message="Disk usage is high; safe cleanup is recommended before large builds or backups."
fi

if [[ "${OUTPUT_JSON}" == "true" ]]; then
  python3 - \
    "${level}" "${used_percent}" "${available_kib}" "${total_kib}" \
    "${DISK_WARN_PERCENT}" "${DISK_FAIL_PERCENT}" "${DISK_MIN_FREE_GIB}" "${message}" <<'PY'
import json
import sys

level, used, available_kib, total_kib, warn, fail, min_free_gib, message = sys.argv[1:]
print(json.dumps({
    "level": level,
    "used_percent": int(used),
    "available_bytes": int(available_kib) * 1024,
    "total_bytes": int(total_kib) * 1024,
    "warning_percent": int(warn),
    "failure_percent": int(fail),
    "minimum_free_gib": int(min_free_gib),
    "message": message,
}, ensure_ascii=False))
PY
else
  printf '[%s] disk=%s%% free_kib=%s warn=%s%% fail=%s%% min_free=%sGiB\n' \
    "${level^^}" "${used_percent}" "${available_kib}" \
    "${DISK_WARN_PERCENT}" "${DISK_FAIL_PERCENT}" "${DISK_MIN_FREE_GIB}"
  echo "${message}"
fi

exit "${exit_code}"
