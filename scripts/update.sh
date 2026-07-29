#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

git fetch --all --prune
git pull --ff-only
docker compose pull
docker compose build --pull memory-gateway
docker compose up -d --remove-orphans
docker image prune -f
docker compose ps
