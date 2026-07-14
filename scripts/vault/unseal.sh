#!/usr/bin/env bash
# Unseal Vault using VAULT_UNSEAL_KEY (env or deploy/vault-init.json).
#
# Robustness contract (why this script is shaped the way it is):
#   * The PRIMARY control path is a DIRECT `docker exec <vault-container> …`.
#     Direct exec is proven reliable against the edge Vault; the compose path
#     (`docker compose exec`) transiently returns empty/errored output, which
#     the old logic mis-read as initialized=False and so it NEVER unsealed.
#   * A transient/empty status probe is treated as UNKNOWN, never as
#     "initialized=False". We only conclude "not yet initialized" after the
#     probe genuinely returns initialized=false; and we only give up on
#     initialization after a long poll of *real* reads.
#   * Idempotent: exits 0 if Vault is already unsealed.
#   * Never prints key material.
#
# Exit codes (interface consumed by scripts/platform-start.sh auto-unseal loop):
#   0  = Vault is unsealed (already, or we unsealed it) — success
#   1  = could not unseal (no key, or never reached sealed=false)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib.sh
source "$ROOT/scripts/vault/lib.sh"

export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"

# Optional self-test / dry-run: exercises the status parser + container
# detection without touching a real Vault. Usage: unseal.sh --self-test
SELF_TEST=0
if [ "${1:-}" = "--self-test" ] || [ "${UNSEAL_SELF_TEST:-0}" = "1" ]; then
  SELF_TEST=1
fi

bash "$ROOT/scripts/vault/start.sh"

UNSEAL_KEY="${VAULT_UNSEAL_KEY:-}"
INIT_FILE="${VAULT_INIT_FILE:-$ROOT/deploy/vault-init.json}"

if [ -z "$UNSEAL_KEY" ] && [ -f "$INIT_FILE" ]; then
  UNSEAL_KEY="$(python3 -c "import json; d=json.load(open('$INIT_FILE')); print(d['unseal_keys_b64'][0])" 2>/dev/null || true)"
fi

if [ "$SELF_TEST" != "1" ] && [ -z "$UNSEAL_KEY" ]; then
  echo "ERROR: Set VAULT_UNSEAL_KEY or create $INIT_FILE via vault/bootstrap.sh"
  exit 1
fi

# ── Container detection ──────────────────────────────────────────────────────
# Prefer the canonical name (fixitlab_vault); fall back to whatever running
# container matches name=vault. Empty result means "no direct container found"
# and we fall back to the compose path.
detect_vault_container() {
  local canonical name
  canonical="$(vault_container_name)"  # "fixitlab_vault"
  if docker ps --filter "name=^/${canonical}\$" --format '{{.Names}}' 2>/dev/null | grep -qx "$canonical"; then
    echo "$canonical"; return 0
  fi
  # Fall back: first running container whose name contains "vault".
  name="$(docker ps --filter 'name=vault' --format '{{.Names}}' 2>/dev/null | head -1 || true)"
  echo "$name"
}

VAULT_CONTAINER="$(detect_vault_container || true)"

# ── Probe / command helpers ──────────────────────────────────────────────────
# vault_exec runs a vault CLI command inside the container. It uses the DIRECT
# `docker exec` path when we have a concrete container name (proven reliable),
# and only falls back to the compose exec path when no direct container was
# detected (e.g. the name differs in some topology). Both are wrapped so that a
# single transient failure returns non-zero without aborting the script.
vault_exec() {
  if [ -n "$VAULT_CONTAINER" ]; then
    docker exec "$VAULT_CONTAINER" vault "$@"
  else
    vault_compose exec -T vault vault "$@"
  fi
}

# vault_status_json prints the raw `vault status -format=json` output, or an
# empty string on any transient failure. `set -e` is intentionally NOT allowed
# to trip here: the caller decides how to interpret empty (== UNKNOWN).
vault_status_json() {
  vault_exec status -format=json 2>/dev/null || true
}

# parse_field <json> <field> <default>
# Prints "true"/"false" for the requested boolean field, or the supplied
# default when the JSON is empty/unparseable. Crucially the default is only
# used by callers to represent UNKNOWN, never to force a False decision.
parse_field() {
  local json="$1" field="$2" default="$3"
  if [ -z "$json" ]; then
    echo "$default"; return 0
  fi
  printf '%s' "$json" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    v = d.get('$field', None)
    if v is None:
        print('$default')
    else:
        print('true' if v else 'false')
except Exception:
    print('$default')
" 2>/dev/null || echo "$default"
}

# ── Self-test mode ───────────────────────────────────────────────────────────
if [ "$SELF_TEST" = "1" ]; then
  echo "[self-test] container detection => '${VAULT_CONTAINER:-<none, will use compose>}'"
  fail=0
  # parser: empty input yields the UNKNOWN default, never a hard False
  [ "$(parse_field '' initialized unknown)" = "unknown" ] || { echo "[self-test] FAIL empty->unknown"; fail=1; }
  # parser: real reads map to true/false
  [ "$(parse_field '{"initialized":true,"sealed":false}' initialized false)" = "true" ]  || { echo "[self-test] FAIL init true"; fail=1; }
  [ "$(parse_field '{"initialized":true,"sealed":false}' sealed true)" = "false" ]        || { echo "[self-test] FAIL sealed false"; fail=1; }
  [ "$(parse_field '{"initialized":false,"sealed":true}' initialized true)" = "false" ]   || { echo "[self-test] FAIL init false"; fail=1; }
  # parser: garbage input yields the default (transient tolerance)
  [ "$(parse_field 'not-json' initialized unknown)" = "unknown" ] || { echo "[self-test] FAIL garbage->unknown"; fail=1; }
  [ "$fail" = "0" ] && echo "[self-test] OK" || echo "[self-test] FAILED"
  exit "$fail"
fi

# ── Phase 1: poll until Vault reports initialized (tolerating transients) ─────
# We require CONSECUTIVE genuine "initialized:true" reads before proceeding, so
# one flaky/empty probe cannot short-circuit us — and, symmetrically, an empty
# probe (UNKNOWN) is NEVER interpreted as initialized=false. If we happen to see
# sealed=false at any point, we are already done.
REQUIRED_CONSECUTIVE=2
consec_init=0
initialized=unknown
sealed=unknown
for _i in $(seq 1 30); do
  st="$(vault_status_json)"
  initialized="$(parse_field "$st" initialized unknown)"
  sealed="$(parse_field "$st" sealed unknown)"

  if [ "$sealed" = "false" ]; then
    echo "Vault already unsealed"
    exit 0
  fi

  if [ "$initialized" = "true" ]; then
    consec_init=$((consec_init + 1))
    if [ "$consec_init" -ge "$REQUIRED_CONSECUTIVE" ]; then
      break
    fi
  else
    # UNKNOWN (empty/transient) OR a genuine false — either way keep polling;
    # a transient must not be allowed to reset us into a false conclusion, so
    # we only reset the consecutive counter, we do not abort.
    consec_init=0
  fi
  sleep 2
done

if [ "$initialized" != "true" ]; then
  echo "ERROR: Vault never reported initialized (last read: initialized=$initialized sealed=$sealed)"
  echo "       (container='${VAULT_CONTAINER:-compose}') — check the container and deploy/vault-init.json"
  exit 1
fi

# ── Phase 2: unseal, retrying until sealed=false ─────────────────────────────
for _i in $(seq 1 15); do
  # Re-check first: another process (or a prior iteration) may have unsealed it.
  sealed="$(parse_field "$(vault_status_json)" sealed unknown)"
  if [ "$sealed" = "false" ]; then
    echo "Vault unsealed"
    exit 0
  fi

  # Attempt the unseal. A single unseal key/threshold is assumed (see
  # bootstrap.sh: -key-shares=1 -key-threshold=1). Suppress output so the key
  # can never leak via stdout/stderr.
  vault_exec operator unseal "$UNSEAL_KEY" >/dev/null 2>&1 || true

  sealed="$(parse_field "$(vault_status_json)" sealed unknown)"
  if [ "$sealed" = "false" ]; then
    echo "Vault unsealed"
    exit 0
  fi
  sleep 2
done

echo "ERROR: Vault did not unseal (initialized=$initialized sealed=$sealed, container='${VAULT_CONTAINER:-compose}')"
exit 1
