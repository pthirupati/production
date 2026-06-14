#!/usr/bin/env bash
# Push local env file into Vault KV and re-render .env.production (Mac/local workflow).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

ENV_FILE="${1:-$ROOT/deploy/production.env}"
OUT="${2:-$ROOT/.env.production}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE"
  exit 1
fi

chmod +x "$ROOT/scripts/vault/"*.sh "$ROOT/scripts/sync-production-env.sh"
bash "$ROOT/scripts/vault/start.sh"
bash "$ROOT/scripts/vault/seed-from-env.sh" "$ENV_FILE"
bash "$ROOT/scripts/vault/render-env.sh" "$OUT"

echo "[vault] Synced KV from $ENV_FILE → $OUT"
echo "Restart platform to apply: ./scripts/platform-start.sh"
