#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="${ROOT_DIR}/backups/${STAMP}"
mkdir -p "${DEST}"

set -a
source ./.env
set +a

docker compose exec -T postgresql \
  pg_dump -U postgres -d "${LOBE_DB_NAME}" -Fc > "${DEST}/lobehub-postgres.dump"

for volume in rustfs-data qdrant-data letta-data mempalace-data gateway-data redis-data; do
  docker run --rm \
    -v "sumeme_${volume}:/source:ro" \
    -v "${DEST}:/backup" \
    alpine:3.20 \
    tar -C /source -czf "/backup/${volume}.tar.gz" .
done

cp .env "${DEST}/env.backup"
chmod 600 "${DEST}/env.backup"

echo "备份完成: ${DEST}"
