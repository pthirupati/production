#!/usr/bin/env bash
# Give the public Edge (D1) node its OWN dedicated SSH key, authorized on the
# private nodes (D2/D3/D4), so post-deploy jobs that run on the edge and then hop
# inline `ssh root@<private-ip>` (unit tests, prepare-e2e, cleanup, health) work.
#
# We deliberately do NOT copy the master PROD_SSH_KEY onto the edge — the edge is
# the only public node. Instead the edge generates a throwaway ed25519 key and we
# authorize just its public half on the private droplets. Idempotent.
#
# Required env: EDGE_PUBLIC_IP APP_PRIVATE_IP DATA_PRIVATE_IP LABS_PRIVATE_IP PROD_SSH_KEY
set -euo pipefail

DRY_RUN="${DRY_RUN:-0}"
EDGE_PUBLIC_IP="${EDGE_PUBLIC_IP:?EDGE_PUBLIC_IP required}"
APP_PRIVATE_IP="${APP_PRIVATE_IP:?APP_PRIVATE_IP required}"
DATA_PRIVATE_IP="${DATA_PRIVATE_IP:?DATA_PRIVATE_IP required}"
LABS_PRIVATE_IP="${LABS_PRIVATE_IP:?LABS_PRIVATE_IP required}"

_is_true() { case "${1:-}" in 1|true|TRUE|yes|on) return 0;; *) return 1;; esac; }

KEY_FILE=""
if [ -n "${PROD_SSH_KEY:-}" ] && ! _is_true "$DRY_RUN"; then
  KEY_FILE="$(mktemp)"; printf '%s\n' "$PROD_SSH_KEY" | tr -d '\r' > "$KEY_FILE"; chmod 600 "$KEY_FILE"
  trap 'rm -f "$KEY_FILE"' EXIT
fi

# Build SSH opts; via-edge uses an explicit ProxyCommand (see ci-bootstrap-cluster.sh).
_opts() {
  local via="$1"
  SSH_OPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes)
  [ -n "$KEY_FILE" ] && SSH_OPTS+=(-i "$KEY_FILE" -o IdentitiesOnly=yes)
  if [ "$via" = "via-edge" ]; then
    local j="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -o ConnectTimeout=10"
    [ -n "$KEY_FILE" ] && j="$j -i $KEY_FILE -o IdentitiesOnly=yes"
    SSH_OPTS+=(-o "ProxyCommand=ssh $j -W %h:%p root@${EDGE_PUBLIC_IP}")
  fi
}

echo "=== FixitLab edge->internal SSH key (dry_run=$DRY_RUN) ==="

if _is_true "$DRY_RUN"; then
  echo "DRY_RUN ssh root@${EDGE_PUBLIC_IP} 'ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519' && authorize pubkey on D2/D3/D4"
  exit 0
fi

# 1. Ensure the edge has a dedicated key; emit its public half (not secret).
_opts direct
EDGE_PUB="$(ssh "${SSH_OPTS[@]}" "root@${EDGE_PUBLIC_IP}" '
  install -m 700 -d /root/.ssh
  [ -f /root/.ssh/id_ed25519 ] || ssh-keygen -t ed25519 -N "" -C "fixitlab-edge" -f /root/.ssh/id_ed25519 >/dev/null 2>&1
  cat /root/.ssh/id_ed25519.pub')"
[ -n "$EDGE_PUB" ] || { echo "ERROR: could not obtain edge public key"; exit 1; }
echo "  edge key ready"

# 2. Authorize the edge public key on each private node (via the edge proxy).
for ip in "$APP_PRIVATE_IP" "$DATA_PRIVATE_IP" "$LABS_PRIVATE_IP"; do
  _opts via-edge
  ssh "${SSH_OPTS[@]}" "root@${ip}" "
    install -m 700 -d /root/.ssh
    touch /root/.ssh/authorized_keys; chmod 600 /root/.ssh/authorized_keys
    grep -qF 'fixitlab-edge' /root/.ssh/authorized_keys || printf '%s\n' '${EDGE_PUB}' >> /root/.ssh/authorized_keys"
  echo "  authorized edge key on ${ip}"
done

echo "=== edge->internal SSH key done ==="
