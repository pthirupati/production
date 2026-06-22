#!/usr/bin/env bash
# Bootstrap HashiCorp Vault on the D1 Edge droplet for the four-droplet cluster.
#
# Vault runs on the edge node (reachable at http://<EDGE_PRIVATE_IP>:8200 from
# D2/D4). This script SSHes into the edge node and reuses the existing Vault
# tooling there:
#   scripts/vault/start.sh        — start the Vault container on fixitlab_net
#   scripts/vault/bootstrap.sh    — init + unseal + KV v2 + AppRole + seed KV
#   scripts/vault/seed-from-env.sh — re-seed KV from the rendered env
#
# The KV is seeded from the cluster env file already present on the edge node
# (rendered by sync-production-env.sh during deploy / placed at deploy/production.env).
#
# After bootstrap it reads back VAULT_ROLE_ID / VAULT_SECRET_ID / VAULT_UNSEAL_KEY
# from deploy/vault-approle.env and emits them as MASKED GitHub outputs so the
# caller can store them as GitHub secrets (see ci-sync-droplet-secrets.sh VAULT_*).
#
# Idempotent (vault/bootstrap.sh detects an already-initialized Vault).
# DRY_RUN=1 prints the ssh/vault commands instead of running them.
#
# Required env: EDGE_PUBLIC_IP, PROD_SSH_KEY
# Optional    : VAULT_ENV_FILE (path on edge node; default deploy/production.env)
#               PERSIST_OVERLAY (1/0) — when 1 (a rotating run), ALSO write the
#                 rotated env into the stable Vault overlay path secret/fixitlab/env
#                 (scripts/vault/persist-env.sh) so the rotated SUPERUSER_PASSWORD +
#                 rotated keys survive across deploys WITHOUT a GitHub PAT. This is
#                 the real login fix: the overlay path is the cross-deploy source of
#                 truth, separate from secret/fixitlab/config (which a no-rotation
#                 relaunch re-seeds from the distributed env). Default 0 → no write,
#                 green path byte-for-byte unchanged.
set -euo pipefail

DRY_RUN="${DRY_RUN:-0}"
EDGE_PUBLIC_IP="${EDGE_PUBLIC_IP:?EDGE_PUBLIC_IP required}"
VAULT_ENV_FILE="${VAULT_ENV_FILE:-/opt/fixitlab/deploy/production.env}"
PERSIST_OVERLAY="${PERSIST_OVERLAY:-0}"

_is_true() { case "${1:-}" in 1|true|TRUE|yes|on) return 0;; *) return 1;; esac; }

KEY_FILE=""
if [ -n "${PROD_SSH_KEY:-}" ] && ! _is_true "$DRY_RUN"; then
  KEY_FILE="$(mktemp)"; printf '%s\n' "$PROD_SSH_KEY" | tr -d '\r' > "$KEY_FILE"; chmod 600 "$KEY_FILE"
  trap 'rm -f "$KEY_FILE"' EXIT
fi

edge_ssh() {
  local script="$*"
  local opts=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes)
  [ -n "$KEY_FILE" ] && opts+=(-i "$KEY_FILE" -o IdentitiesOnly=yes)
  if _is_true "$DRY_RUN"; then
    echo "DRY_RUN ssh root@${EDGE_PUBLIC_IP} '${script%%$'\n'*} ...'"
    return 0
  fi
  ssh "${opts[@]}" "root@${EDGE_PUBLIC_IP}" "bash -s" <<EOF
set -e
cd /opt/fixitlab
${script}
EOF
}

echo "=== FixitLab cluster Vault bootstrap on edge $EDGE_PUBLIC_IP (dry_run=$DRY_RUN) ==="

# Init / unseal / AppRole / seed KV from the env file already on the edge node.
edge_ssh "
chmod +x scripts/vault/*.sh scripts/vault/*.py 2>/dev/null || true
# Ensure an env source exists for seeding (sync from GitHub secret if needed)
if [ ! -f '${VAULT_ENV_FILE}' ]; then
  echo '[vault] seeding source env from .env.production'
  mkdir -p \$(dirname '${VAULT_ENV_FILE}')
  cp .env.production '${VAULT_ENV_FILE}' 2>/dev/null || true
fi
bash scripts/vault/start.sh
if docker exec fixitlab_vault vault status -format=json 2>/dev/null | grep -q '\"initialized\":true'; then
  echo '[vault] already initialized — re-seeding KV'
  bash scripts/vault/seed-from-env.sh '${VAULT_ENV_FILE}'
else
  bash scripts/vault/bootstrap.sh '${VAULT_ENV_FILE}'
fi
"

# When this run ROTATED secrets, ALSO persist the rotated env into the stable Vault
# overlay path (secret/fixitlab/env) so the rotated SUPERUSER_PASSWORD + rotated keys
# survive future no-rotation deploys WITHOUT a GitHub PAT. This is SEPARATE from the
# config-path re-seed above (which a stale relaunch would clobber). No-op when this
# run did not rotate → green path unchanged.
OVERLAY_STATUS="skipped"
if _is_true "$PERSIST_OVERLAY"; then
  echo "[vault] rotation ran — persisting rotated env to overlay path secret/fixitlab/env"
  if _is_true "$DRY_RUN"; then
    echo "DRY_RUN ssh root@${EDGE_PUBLIC_IP} 'bash scripts/vault/persist-env.sh /opt/fixitlab/.env.production'"
    OVERLAY_STATUS="ok"
  elif edge_ssh "
chmod +x scripts/vault/*.sh scripts/vault/*.py 2>/dev/null || true
# Persist the freshest deployed env (.env.production if present, else the seed file).
SRC=/opt/fixitlab/.env.production
[ -f \"\$SRC\" ] || SRC='${VAULT_ENV_FILE}'
bash scripts/vault/persist-env.sh \"\$SRC\"
"; then
    OVERLAY_STATUS="ok"
    echo "[vault] overlay persist OK — rotated secrets are the cross-deploy source of truth"
  else
    OVERLAY_STATUS="failed"
    echo "::warning::Vault overlay persist failed — rotated secrets may not survive the next deploy. Check Vault on the edge node."
  fi
else
  echo "[vault] no rotation this run — overlay path left as-is (green path unchanged)"
fi
# Emit the overlay sync outcome so the credentials email can state a REAL,
# independent Vault status (ok|failed|skipped), not a mirror of the GitHub sync.
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "vault_overlay_status=${OVERLAY_STATUS}" >> "$GITHUB_OUTPUT"
fi

# Read back AppRole creds (masked) and emit as GitHub outputs for secret storage.
if _is_true "$DRY_RUN"; then
  echo "DRY_RUN ssh root@${EDGE_PUBLIC_IP} 'cat /opt/fixitlab/deploy/vault-approle.env'  # -> VAULT_ROLE_ID/SECRET_ID/UNSEAL_KEY (masked)"
  echo "DRY_RUN would emit MASKED GitHub outputs: vault_role_id, vault_secret_id, vault_unseal_key"
else
  APPROLE_CONTENT="$(edge_ssh "cat deploy/vault-approle.env 2>/dev/null || true")"
  emit_masked() {
    local key="$1" gh_key="$2"
    local val
    val="$(printf '%s\n' "$APPROLE_CONTENT" | { grep "^${key}=" || true; } | cut -d= -f2- | tr -d '\r')"
    [ -z "$val" ] && return 0
    [ -n "${GITHUB_ACTIONS:-}" ] && echo "::add-mask::${val}"
    if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "${gh_key}=${val}" >> "$GITHUB_OUTPUT"; fi
    echo "  ${gh_key} captured (masked)"
  }
  emit_masked VAULT_ROLE_ID vault_role_id
  emit_masked VAULT_SECRET_ID vault_secret_id
  emit_masked VAULT_UNSEAL_KEY vault_unseal_key
fi

echo "=== Vault cluster bootstrap done ==="
