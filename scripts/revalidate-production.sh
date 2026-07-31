#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/sumeme}"
REMOTE_DIR="${REMOTE_DIR:?REMOTE_DIR is required}"

cd "${DEPLOY_DIR}"
test -f .env
docker compose config >/dev/null

sanitized_ps() {
  docker compose ps -a --format json 2>/dev/null | python3 -c '
import json, sys
rows=[]
for line in sys.stdin:
    line=line.strip()
    if not line:
        continue
    item=json.loads(line)
    rows.append({
        "service": item.get("Service"),
        "state": item.get("State"),
        "health": item.get("Health"),
        "exit_code": item.get("ExitCode"),
    })
print(json.dumps(rows, ensure_ascii=False, sort_keys=True))
' || true
}

diagnose_failure() {
  local exit_code=$?
  trap - ERR
  echo "== Sanitized production revalidation failure ==" >&2
  sanitized_ps >&2
  for service in rustfs-init letta memory-gateway; do
    echo "== Redacted ${service} logs ==" >&2
    docker compose logs --no-color --tail 120 --since 30m "${service}" 2>&1 \
      | python3 "${REMOTE_DIR}/redact-log-stream.py" >&2 || true
  done
  echo "== End sanitized production revalidation failure ==" >&2
  exit "${exit_code}"
}
trap diagnose_failure ERR

echo "== Disk protection revalidation =="
set +e
disk_json="$(DEPLOY_DIR="${DEPLOY_DIR}" bash "${REMOTE_DIR}/preflight-disk.sh" --json)"
disk_status=$?
set -e
printf '%s\n' "${disk_json}"
disk_level="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read()).get("level", "unknown"))' <<<"${disk_json}")"
if [[ "${disk_level}" == "warning" || "${disk_status}" -eq 2 ]]; then
  DEPLOY_DIR="${DEPLOY_DIR}" bash "${REMOTE_DIR}/cleanup-runtime.sh"
  DEPLOY_DIR="${DEPLOY_DIR}" bash "${REMOTE_DIR}/preflight-disk.sh" --json
elif [[ "${disk_status}" -ne 0 ]]; then
  exit "${disk_status}"
fi

recreate_project_containers() {
  echo "Recreating Compose project containers without removing volumes."
  mapfile -t ids < <(docker ps -aq --filter label=com.docker.compose.project=sumeme)
  if (( ${#ids[@]} > 0 )); then
    docker rm -f "${ids[@]}"
  fi
  docker network rm sumeme >/dev/null 2>&1 || true
  docker compose up -d --remove-orphans
}

echo "== Production container recovery =="
if ! docker compose up -d --remove-orphans; then
  recreate_project_containers
fi
if ! DEPLOY_DIR="${DEPLOY_DIR}" bash "${REMOTE_DIR}/health-check.sh"; then
  echo "Existing images were not healthy; rebuilding local runtime services."
  docker compose build memory-gateway ai-provider-proxy
  recreate_project_containers
  DEPLOY_DIR="${DEPLOY_DIR}" bash "${REMOTE_DIR}/health-check.sh"
fi

echo "== Sanitized deployment state =="
printf 'current_sha=%s\n' "$(cat .deploy/current_sha 2>/dev/null || echo unknown)"
printf 'deploying_sha=%s\n' "$(cat .deploy/deploying_sha 2>/dev/null || echo empty)"
sanitized_ps

private_report="${REMOTE_DIR}/private-object.json"
application_report="${REMOTE_DIR}/application.json"
rm -f "${private_report}" "${application_report}"
set +e
PRIVATE_OBJECT_SMOKE_OUTPUT_PATH="${private_report}" \
  DEPLOY_DIR="${DEPLOY_DIR}" bash "${REMOTE_DIR}/smoke-private-object.sh"
private_status=$?
SMOKE_OUTPUT_PATH="${application_report}" \
  DEPLOY_DIR="${DEPLOY_DIR}" bash "${REMOTE_DIR}/smoke-test.sh"
application_status=$?
set -e

python3 - "${private_report}" "${application_report}" <<'PY'
import json
import sys

output = {}
for name, path in (("private_object", sys.argv[1]), ("application", sys.argv[2])):
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
    except Exception:
        output[name] = {"available": False}
        continue
    output[name] = {
        "available": True,
        "overall": value.get("overall"),
        "deployment_gate": value.get("deployment_gate"),
        "scope": value.get("scope") or value.get("test_scope"),
        "checks": value.get("checks"),
        "write_components": value.get("write_components"),
        "recall_components": value.get("recall_components"),
        "error_codes": value.get("error_codes"),
        "duration_seconds": value.get("duration_seconds"),
    }
print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
PY

test "${private_status}" -eq 0
test "${application_status}" -eq 0
trap - ERR
echo "Production revalidation succeeded."
