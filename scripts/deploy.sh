#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ ! -f .env ]]; then
  echo "未找到 .env。先执行: cp .env.example .env && bash scripts/generate-secrets.sh" >&2
  exit 1
fi

docker compose config >/dev/null
docker compose pull
docker compose build memory-gateway
docker compose up -d --remove-orphans
docker compose ps

echo
echo "Gateway health:"
curl -fsS http://127.0.0.1:${GATEWAY_PORT:-8010}/health || true
echo
