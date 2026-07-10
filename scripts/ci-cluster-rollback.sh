#!/usr/bin/env bash
# Roll back the four-droplet cluster to the previous git commit on each node.
# Usage (from CI or ops shell with SSH access):
#   EDGE_PUBLIC_IP=... APP_PRIVATE_IP=... DATA_PRIVATE_IP=... LABS_PRIVATE_IP=... \
#   PROD_SSH_KEY=... ./scripts/ci-cluster-rollback.sh
#
# DRY_RUN=1 prints commands without executing them.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
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

remote() {
  local target_ip="$1" via_edge="$2"; shift 2
  local script="$*"
  local opts=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes)
  [ -n "$KEY_FILE" ] && opts+=(-i "$KEY_FILE" -o IdentitiesOnly=yes)
  if [ "$via_edge" = "via-edge" ]; then
    local jopts="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -o ConnectTimeout=10"
    [ -n "$KEY_FILE" ] && jopts="$jopts -i $KEY_FILE -o IdentitiesOnly=yes"
    opts+=(-o "ProxyCommand=ssh $jopts -W %h:%p root@${EDGE_PUBLIC_IP}")
  fi
  if _is_true "$DRY_RUN"; then
    local hop=""; [ "$via_edge" = "via-edge" ] && hop=" -J root@${EDGE_PUBLIC_IP}"
    echo "DRY_RUN ssh${hop} root@${target_ip} '${script%%$'\n'*} ...'"
    return 0
  fi
  ssh "${opts[@]}" "root@${target_ip}" "bash -s" <<EOF
set -e
cd /opt/fixitlab
git fetch origin main
git reset --hard HEAD~1
chmod +x scripts/platform-start.sh scripts/ci-remote-platform.sh 2>/dev/null || true
${script}
EOF
}

ROLLBACK_SCRIPT='
PREV="$(git rev-parse --short HEAD)"
echo "Rolling back on $(hostname) from $PREV"
CLUSTER_ROLE="${CLUSTER_ROLE}" ./scripts/platform-start.sh
echo "Rollback complete on $(hostname) — now at $(git rev-parse --short HEAD)"
'

echo "=== Four-droplet rollback: git reset --hard HEAD~1 + platform-start ==="

remote "$DATA_PRIVATE_IP" via-edge "CLUSTER_ROLE=data ${ROLLBACK_SCRIPT}"
remote "$EDGE_PUBLIC_IP" direct "CLUSTER_ROLE=edge ${ROLLBACK_SCRIPT}"
remote "$APP_PRIVATE_IP" via-edge "CLUSTER_ROLE=app ${ROLLBACK_SCRIPT}"
remote "$LABS_PRIVATE_IP" via-edge "CLUSTER_ROLE=labs ${ROLLBACK_SCRIPT}"

echo "=== Rollback finished — verify /api/health/ready/ on the edge ==="
