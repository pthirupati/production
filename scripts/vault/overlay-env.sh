#!/usr/bin/env bash
# Overlay ROTATED secrets from Vault onto a freshly-built .env (Vault wins).
#
# Runs on EVERY deploy, right after .env.production is built from PRODUCTION_ENV_B64
# + ci-generate-secrets. If Vault is enabled AND the overlay path (secret/fixitlab/env,
# written by scripts/vault/persist-env.sh only on a run that rotated) EXISTS, its keys
# are written over the env file so the rotated SUPERUSER_PASSWORD + rotated keys win —
# even if the GitHub PRODUCTION_ENV_B64 secret is stale (couldn't be written back due
# to the 403). Once rotation persisted to Vault, every later deploy reads the rotated
# admin password from Vault → login persists WITHOUT a GitHub PAT.
#
# GREEN-PATH SAFETY: this is a NO-OP unless ALL hold —
#   * VAULT_ENABLED truthy in the env file, AND
#   * VAULT_ROLE_ID + VAULT_SECRET_ID present (AppRole, read-only is enough), AND
#   * the overlay path EXISTS with data.
# When no rotation has ever happened the overlay path is ABSENT → we exit 0 and leave
# the env file byte-for-byte as built. A Vault miss/timeout/error NEVER fails the
# deploy (always exit 0). Reads only — never writes Vault, never touches secrets/files
# other than the target env.
#
# Usage:
#   ./scripts/vault/overlay-env.sh [ENV_FILE]
#
# Env:
#   VAULT_OVERLAY_PATH  Vault KV v2 path to read (default secret/fixitlab/env)
#   VAULT_OVERLAY_ADDR  override the host-reachable Vault address (else derived from
#                       the env file's VAULT_ADDR; vault:8200 -> 127.0.0.1:8200)
set -uo pipefail   # NOTE: no -e — every failure here must be non-fatal (exit 0)

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="${1:-$ROOT/.env.production}"
KV_PATH="${VAULT_OVERLAY_PATH:-secret/fixitlab/env}"

_env_true() { case "${1:-}" in 1|true|TRUE|True|yes|YES|on|ON) return 0 ;; *) return 1 ;; esac; }

[ -f "$ENV_FILE" ] || { echo "[vault-overlay] no env file at $ENV_FILE — skip"; exit 0; }

_envget() { { grep -E "^$1=" "$ENV_FILE" 2>/dev/null || true; } | head -n1 | cut -d= -f2- | tr -d '\r'; }

# Gate 1: Vault enabled in the env file (the green non-Vault path skips entirely).
if ! _env_true "$(_envget VAULT_ENABLED)" && ! _env_true "${VAULT_ENABLED:-}"; then
  echo "[vault-overlay] VAULT_ENABLED not set — skip (no overlay)"
  exit 0
fi

# Gate 2: AppRole creds (read-only token is enough to READ the overlay path).
ROLE_ID="${VAULT_ROLE_ID:-$(_envget VAULT_ROLE_ID)}"
SECRET_ID="${VAULT_SECRET_ID:-$(_envget VAULT_SECRET_ID)}"
APPROLE_FILE="${VAULT_APPROLE_FILE:-$ROOT/deploy/vault-approle.env}"
if { [ -z "$ROLE_ID" ] || [ -z "$SECRET_ID" ]; } && [ -f "$APPROLE_FILE" ]; then
  # shellcheck disable=SC1090
  . "$APPROLE_FILE" 2>/dev/null || true
  ROLE_ID="${ROLE_ID:-${VAULT_ROLE_ID:-}}"
  SECRET_ID="${SECRET_ID:-${VAULT_SECRET_ID:-}}"
fi
if [ -z "$ROLE_ID" ] || [ -z "$SECRET_ID" ]; then
  echo "[vault-overlay] no AppRole creds — skip (no overlay)"
  exit 0
fi

# Resolve a HOST-reachable Vault address. Inside-container service name 'vault'
# is not resolvable from the host; single-host reaches Vault on 127.0.0.1.
ADDR="${VAULT_OVERLAY_ADDR:-$(_envget VAULT_ADDR)}"
case "$ADDR" in
  ""|*//vault:*) ADDR="http://127.0.0.1:8200" ;;
esac

# Read + overlay via the Vault HTTP API using python3 stdlib only (no vault binary
# or hvac needed on the host; works on single-host AND the cluster app node which
# has no local Vault container and reaches the edge at VAULT_ADDR). Vault must
# already be unsealed by the deploy (platform-start unseals on the edge/single-host).
OVERLAID="$(python3 - "$ENV_FILE" "$ADDR" "$ROLE_ID" "$SECRET_ID" "$KV_PATH" <<'PY'
import json, sys, urllib.request, urllib.error

env_path, addr, role_id, secret_id, kv_path = sys.argv[1:6]
addr = addr.rstrip("/")

def api(path, data=None):
    url = f"{addr}/v1/{path}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method="POST" if data is not None else "GET")
    req.add_header("Content-Type", "application/json")
    if TOKEN:
        req.add_header("X-Vault-Token", TOKEN)
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read() or b"{}")

TOKEN = ""
try:
    resp = api("auth/approle/login", {"role_id": role_id, "secret_id": secret_id})
    TOKEN = resp["auth"]["client_token"]
except Exception as e:
    sys.stderr.write(f"[vault-overlay] AppRole login failed ({type(e).__name__}) — skip\n")
    sys.exit(0)

# KV v2 read path: <mount>/data/<rest>
mount, _, rest = kv_path.partition("/")
read_path = f"{mount}/data/{rest}" if rest else kv_path
try:
    resp = api(read_path)
    overlay = resp.get("data", {}).get("data") or {}
except urllib.error.HTTPError as e:
    if e.code == 404:
        sys.stderr.write("[vault-overlay] overlay path absent (no rotation persisted) — leaving env unchanged\n")
    else:
        sys.stderr.write(f"[vault-overlay] read failed (HTTP {e.code}) — skip\n")
    sys.exit(0)
except Exception as e:
    sys.stderr.write(f"[vault-overlay] read failed ({type(e).__name__}) — skip\n")
    sys.exit(0)

if not isinstance(overlay, dict) or not overlay:
    sys.stderr.write("[vault-overlay] overlay path empty — leaving env unchanged\n")
    sys.exit(0)

# Rewrite the env file: Vault wins for keys it holds; all other lines/order kept.
lines = open(env_path, encoding="utf-8").read().splitlines()
seen = set()
out = []
for raw in lines:
    s = raw.strip()
    if s and not s.startswith("#") and "=" in s:
        k = s.split("=", 1)[0].strip()
        if k in overlay:
            v = overlay[k]
            v = "" if v is None else str(v)
            out.append(f"{k}={v}")
            seen.add(k)
            continue
    out.append(raw)
# Append overlay keys not already present in the file.
for k in sorted(overlay):
    if k not in seen:
        v = overlay[k]
        v = "" if v is None else str(v)
        out.append(f"{k}={v}")
open(env_path, "w", encoding="utf-8").write("\n".join(out).rstrip("\n") + "\n")
print(len(overlay))
PY
)"

RC=$?
if [ "$RC" -eq 0 ] && [ -n "${OVERLAID:-}" ]; then
  chmod 600 "$ENV_FILE" 2>/dev/null || true
  echo "[vault-overlay] applied ${OVERLAID} rotated key(s) from Vault $KV_PATH (Vault wins) → $ENV_FILE"
else
  echo "[vault-overlay] no overlay applied (path absent or Vault unavailable) — env unchanged"
fi
exit 0
