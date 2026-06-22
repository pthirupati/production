#!/usr/bin/env bash
# Persist ROTATED secrets into Vault as the cross-deploy source of truth.
#
# Problem this solves: when secrets rotate, the new admin password can't always be
# written back to the GitHub PRODUCTION_ENV_B64 secret (HTTP 403 without a classic
# PAT), so the next deploy rebuilds .env from the STALE PRODUCTION_ENV_B64 and the
# rotated SUPERUSER_PASSWORD is lost → "invalid credentials".
#
# Fix: write the rotated env into a STABLE Vault path (default secret/fixitlab/env)
# that is SEPARATE from the per-deploy config path (secret/fixitlab/config, which a
# no-rotation relaunch re-seeds from the — possibly stale — distributed env). The
# overlay path is only ever written here, on a run that actually rotated, so it
# always holds the freshest rotated SUPERUSER_PASSWORD + rotated keys. On every
# subsequent deploy scripts/vault/overlay-env.sh reads this path and lets Vault win,
# so admin login persists WITHOUT needing the GitHub PAT.
#
# Writing requires the Vault ROOT token (the FixitLab AppRole is read-only:
# `path "secret/data/fixitlab/*" { capabilities = ["read"] }`). The root token lives
# in deploy/vault-init.json on the edge node, so this script runs THERE.
#
# Idempotent. Safe: never touches secret/fixitlab/config and never fails the deploy
# on its own (callers treat a non-zero exit as best-effort).
#
# Usage (on the edge node):
#   ./scripts/vault/persist-env.sh [ENV_FILE]
#
# Env:
#   VAULT_OVERLAY_PATH  Vault KV path to write (default secret/fixitlab/env)
#   VAULT_INIT_FILE     path to vault-init.json (default deploy/vault-init.json)
#   PERSIST_KEYS        space/comma list to persist a SUBSET of keys (default: all
#                       keys in ENV_FILE). The whole env is the default per spec.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

ENV_FILE="${1:-$ROOT/.env.production}"
KV_PATH="${VAULT_OVERLAY_PATH:-secret/fixitlab/env}"
INIT_FILE="${VAULT_INIT_FILE:-$ROOT/deploy/vault-init.json}"
export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"

if [ ! -f "$ENV_FILE" ]; then
  echo "[vault-persist] no env file at $ENV_FILE — nothing to persist"
  exit 0
fi
if [ ! -f "$INIT_FILE" ]; then
  echo "[vault-persist] $INIT_FILE missing (no root token) — cannot persist overlay; skipping"
  exit 0
fi

chmod +x "$ROOT/scripts/vault/"*.sh "$ROOT/scripts/vault/env-kv-helper.py" 2>/dev/null || true
bash "$ROOT/scripts/vault/unseal.sh" || { echo "[vault-persist] unseal failed — skipping"; exit 0; }

# shellcheck source=lib.sh
source "$ROOT/scripts/vault/lib.sh"

export VAULT_TOKEN="$(python3 -c "import json; print(json.load(open('$INIT_FILE'))['root_token'])" 2>/dev/null || true)"
if [ -z "${VAULT_TOKEN:-}" ]; then
  echo "[vault-persist] could not read root token — skipping"
  exit 0
fi

# Build the JSON to write. Default = the whole env file; PERSIST_KEYS narrows it.
TMP_JSON="$(mktemp)"; chmod 600 "$TMP_JSON"
trap 'rm -f "$TMP_JSON"' EXIT
if [ -n "${PERSIST_KEYS:-}" ]; then
  KEYS_NORM="$(printf '%s' "$PERSIST_KEYS" | tr ', ' '\n\n' | sed '/^$/d')"
  python3 - "$ENV_FILE" "$TMP_JSON" <<'PY' "$KEYS_NORM"
import json, sys
env_path, out_path = sys.argv[1], sys.argv[2]
wanted = set(l.strip() for l in sys.argv[3].splitlines() if l.strip())
data = {}
for raw in open(env_path, encoding="utf-8"):
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    k = k.strip()
    if k in wanted:
        data[k] = v.strip()
json.dump(data, open(out_path, "w", encoding="utf-8"), ensure_ascii=False)
print(f"[vault-persist] persisting {len(data)} selected key(s)")
PY
else
  python3 "$ROOT/scripts/vault/env-kv-helper.py" env-to-json "$ENV_FILE" > "$TMP_JSON"
  echo "[vault-persist] persisting full env ($(grep -c '^[A-Z]' "$ENV_FILE" || echo 0) keys)"
fi

VAULT_CONTAINER="$(vault_container_name)"
docker cp "$TMP_JSON" "${VAULT_CONTAINER}:/tmp/vault-overlay.json"
vault_compose exec -T -e VAULT_TOKEN vault \
  vault kv put "$KV_PATH" @/tmp/vault-overlay.json
vault_compose exec -T vault rm -f /tmp/vault-overlay.json

echo "[vault-persist] wrote rotated secrets → Vault $KV_PATH (cross-deploy source of truth)"
