#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_IMAGE="${1:-sumeme-lobehub:2.2.11-backend-reuse-1}"
CONTAINER_NAME="${2:-sumeme-lobehub}"

if docker image inspect "${TARGET_IMAGE}" >/dev/null 2>&1; then
  echo "LobeHub backend image alias already exists: ${TARGET_IMAGE}"
  exit 0
fi

container_image_id="$(docker inspect -f '{{.Image}}' "${CONTAINER_NAME}")"
if [[ -z "${container_image_id}" ]]; then
  echo "Unable to resolve the image ID for running container ${CONTAINER_NAME}." >&2
  exit 1
fi

docker image inspect "${container_image_id}" >/dev/null
docker tag "${container_image_id}" "${TARGET_IMAGE}"
docker image inspect "${TARGET_IMAGE}" >/dev/null

echo "Tagged the running ${CONTAINER_NAME} image as ${TARGET_IMAGE}."
