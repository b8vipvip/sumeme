#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${ROOT_DIR}/.env.example" "${ENV_FILE}"
fi

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "缺少命令: $1" >&2
    exit 1
  }
}

need openssl
need docker
need python3

random_hex() {
  openssl rand -hex "${1:-32}"
}

random_base64() {
  openssl rand -base64 "${1:-32}" | tr -d '\n'
}

set_env() {
  local key="$1"
  local value="$2"
  python3 - "${ENV_FILE}" "${key}" "${value}" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
lines = path.read_text(encoding="utf-8").splitlines()
prefix = key + "="
for i, line in enumerate(lines):
    if line.startswith(prefix):
        lines[i] = prefix + value
        break
else:
    lines.append(prefix + value)
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

set_env GATEWAY_API_KEY "$(random_hex 32)"
set_env GATEWAY_ADMIN_TOKEN "$(random_hex 32)"
set_env POSTGRES_PASSWORD "$(random_hex 24)"
set_env AUTH_SECRET "$(random_hex 32)"
# LobeHub 要求 Base64 解码后恰好为 16、24 或 32 字节。
set_env KEY_VAULTS_SECRET "$(random_base64 32)"
set_env RUSTFS_SECRET_KEY "$(random_hex 24)"
set_env LETTA_SERVER_PASSWORD "$(random_hex 32)"
set_env LETTA_ENCRYPTION_KEY "$(random_hex 32)"

JWKS="$(
  docker run --rm node:22-alpine node - <<'NODE'
const { generateKeyPairSync, randomBytes } = require('crypto');
const { privateKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
const jwk = privateKey.export({ format: 'jwk' });
jwk.use = 'sig';
jwk.alg = 'RS256';
jwk.kid = randomBytes(8).toString('hex');
process.stdout.write(JSON.stringify({ keys: [jwk] }));
NODE
)"
set_env JWKS_KEY "${JWKS}"

chmod 600 "${ENV_FILE}"
echo "已生成服务器本地密钥: ${ENV_FILE}"
echo "请继续填写 OPENAI_RELAY_BASE_URL、OPENAI_RELAY_API_KEY 和模型名称。"