#!/usr/bin/env bash
# Bootstrap every droplet in the FixitLab four-droplet cluster (parallel SSH).
#
# Each node runs infra/digitalocean/bootstrap-platform.sh (Docker + base setup)
# plus role-specific steps:
#   edge : clone repo, create fixitlab_net
#   app  : clone repo, create fixitlab_net + fixitlab_labs, install labs SSH key
#   data : clone repo (compose/env only), create fixitlab_net
#   labs : create fixitlab_labs network, pre-pull nothing (images built later),
#          authorize D2's ed25519 key for remote docker
#
# Idempotent. DRY_RUN=1 prints the ssh commands instead of running them.
#
# Required env:
#   EDGE_PUBLIC_IP                 (CI reaches the cluster through the edge node)
#   EDGE_PRIVATE_IP APP_PRIVATE_IP DATA_PRIVATE_IP LABS_PRIVATE_IP
#   PROD_SSH_KEY                   (private key for root)
#   GIT_REPO                       (https://x-access-token:TOKEN@github.com/owner/repo.git)
#   GIT_REF                        (branch/tag, default main)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DRY_RUN="${DRY_RUN:-0}"
GIT_REF="${GIT_REF:-main}"

EDGE_PUBLIC_IP="${EDGE_PUBLIC_IP:?EDGE_PUBLIC_IP required}"
EDGE_PRIVATE_IP="${EDGE_PRIVATE_IP:?EDGE_PRIVATE_IP required}"
APP_PRIVATE_IP="${APP_PRIVATE_IP:?APP_PRIVATE_IP required}"
DATA_PRIVATE_IP="${DATA_PRIVATE_IP:?DATA_PRIVATE_IP required}"
LABS_PRIVATE_IP="${LABS_PRIVATE_IP:?LABS_PRIVATE_IP required}"

_is_true() { case "${1:-}" in 1|true|TRUE|yes|on) return 0;; *) return 1;; esac; }

# Mask the repo URL (may carry a token) for GitHub logs.
[ -n "${GIT_REPO:-}" ] && [ -n "${GITHUB_ACTIONS:-}" ] && echo "::add-mask::${GIT_REPO}"

KEY_FILE=""
ssh_setup() {
  if [ -n "${PROD_SSH_KEY:-}" ] && ! _is_true "$DRY_RUN"; then
    KEY_FILE="$(mktemp)"; printf '%s\n' "$PROD_SSH_KEY" | tr -d '\r' > "$KEY_FILE"; chmod 600 "$KEY_FILE"
  fi
}
ssh_cleanup() { [ -n "$KEY_FILE" ] && rm -f "$KEY_FILE" || true; }
trap ssh_cleanup EXIT

# Run a command on a node. We hop through the edge node for private droplets
# (ProxyJump) since D2/D3/D4 have no public IP.
# Build SSH options into the global SSH_OPTS array (shared by remote() and the
# env writer). via_edge="via-edge" routes through the edge with an explicit
# ProxyCommand — ProxyJump does not reliably pass our -i key / StrictHostKeyChecking
# to the jump-host connection, so the hop would fail with "Permission denied
# (publickey)" / "Host key verification failed". UserKnownHostsFile=/dev/null also
# avoids the parallel known_hosts race.
_build_ssh_opts() {
  local via_edge="$1"
  SSH_OPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes)
  [ -n "$KEY_FILE" ] && SSH_OPTS+=(-i "$KEY_FILE" -o IdentitiesOnly=yes)
  if [ "$via_edge" = "via-edge" ]; then
    local jopts="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -o ConnectTimeout=10"
    [ -n "$KEY_FILE" ] && jopts="$jopts -i $KEY_FILE -o IdentitiesOnly=yes"
    SSH_OPTS+=(-o "ProxyCommand=ssh $jopts -W %h:%p root@${EDGE_PUBLIC_IP}")
  fi
}

remote() {
  local target_ip="$1" via_edge="$2"; shift 2
  local script="$*"
  if _is_true "$DRY_RUN"; then
    local hop=""; [ "$via_edge" = "via-edge" ] && hop=" -J root@${EDGE_PUBLIC_IP}"
    echo "DRY_RUN ssh${hop} root@${target_ip} '<bootstrap script: ${script%%$'\n'*} ...>'"
    return 0
  fi
  _build_ssh_opts "$via_edge"
  ssh "${SSH_OPTS[@]}" "root@${target_ip}" "bash -s" <<EOF
set -e
${script}
EOF
}

# Write the cluster-wired env onto a node from the file in CLUSTER_ENV_FILE. The
# base64 is sent over SSH stdin — never as an argument — so it is not logged or
# visible in the node's process list. Vault reads deploy/production.env and the
# deploy reads .env.production. No-op if CLUSTER_ENV_FILE is unset/missing.
write_node_env() {
  local ip="$1" via_edge="$2"
  [ -n "${CLUSTER_ENV_FILE:-}" ] && [ -f "${CLUSTER_ENV_FILE:-}" ] || return 0
  if _is_true "$DRY_RUN"; then
    echo "DRY_RUN write env -> root@${ip}:/opt/fixitlab/.env.production (+ deploy/production.env)"
    return 0
  fi
  _build_ssh_opts "$via_edge"
  base64 < "$CLUSTER_ENV_FILE" | tr -d '\n' | ssh "${SSH_OPTS[@]}" "root@${ip}" \
    'umask 077; mkdir -p /opt/fixitlab/deploy; base64 -d > /opt/fixitlab/.env.production && cp /opt/fixitlab/.env.production /opt/fixitlab/deploy/production.env && echo "[env] wrote .env.production ($(wc -l < /opt/fixitlab/.env.production) lines) on $(hostname)"'
}

BOOTSTRAP_COMMON='
apt-get update -y >/dev/null 2>&1 || true
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
mkdir -p /opt/fixitlab
# 4GB swap so the 8GB nodes do not OOM-kill (status 137) when the backend + 4
# celery containers + a test/migration process run together (seen in unit tests).
if [ ! -f /swapfile ]; then
  fallocate -l 4G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=4096 2>/dev/null || true
  if [ -f /swapfile ]; then
    chmod 600 /swapfile; mkswap /swapfile >/dev/null 2>&1 || true; swapon /swapfile 2>/dev/null || true
    grep -q "^/swapfile" /etc/fstab || echo "/swapfile none swap sw 0 0" >> /etc/fstab
  fi
fi
'

clone_repo='
REPO="__GIT_REPO__"
REF="__GIT_REF__"
if [ ! -d /opt/fixitlab/.git ]; then git clone "$REPO" /opt/fixitlab; fi
cd /opt/fixitlab
git remote set-url origin "$REPO"
git fetch origin
git checkout "$REF"
git reset --hard "origin/$REF"
'
clone_repo="${clone_repo//__GIT_REPO__/${GIT_REPO:-}}"
clone_repo="${clone_repo//__GIT_REF__/$GIT_REF}"

NET_NET='docker network inspect fixitlab_net >/dev/null 2>&1 || docker network create fixitlab_net'
NET_LABS='docker network inspect fixitlab_labs >/dev/null 2>&1 || docker network create fixitlab_labs'

bootstrap_edge() {
  echo "[edge] bootstrapping $EDGE_PUBLIC_IP"
  remote "$EDGE_PUBLIC_IP" direct "$BOOTSTRAP_COMMON
$clone_repo
$NET_NET
echo '[edge] ready'"
}

bootstrap_app() {
  echo "[app] bootstrapping $APP_PRIVATE_IP (via edge)"
  remote "$APP_PRIVATE_IP" via-edge "$BOOTSTRAP_COMMON
$clone_repo
$NET_NET
$NET_LABS
mkdir -p /opt/fixitlab/deploy/labs_ssh
echo '[app] ready'"
}

bootstrap_data() {
  echo "[data] bootstrapping $DATA_PRIVATE_IP (via edge)"
  remote "$DATA_PRIVATE_IP" via-edge "$BOOTSTRAP_COMMON
$clone_repo
$NET_NET
echo '[data] ready'"
}

bootstrap_labs() {
  echo "[labs] bootstrapping $LABS_PRIVATE_IP (via edge)"
  remote "$LABS_PRIVATE_IP" via-edge "$BOOTSTRAP_COMMON
$NET_LABS
mkdir -p /root/.ssh
chmod 700 /root/.ssh
echo '[labs] ready (remote docker engine; scenario images built by ci-cluster-deploy.sh)'"
}

main() {
  echo "=== FixitLab cluster bootstrap (dry_run=$DRY_RUN ref=$GIT_REF) ==="
  ssh_setup

  if _is_true "$DRY_RUN"; then
    # Sequential in dry-run so the printed commands are readable and ordered.
    bootstrap_edge; bootstrap_app; bootstrap_data; bootstrap_labs
  else
    # Parallel bootstrap; collect exit codes.
    bootstrap_edge & pe=$!
    bootstrap_app  & pa=$!
    bootstrap_data & pd=$!
    bootstrap_labs & pl=$!
    rc=0
    wait $pe || rc=1
    wait $pa || rc=1
    wait $pd || rc=1
    wait $pl || rc=1
    [ "$rc" -eq 0 ] || { echo "ERROR: one or more nodes failed to bootstrap"; exit 1; }
  fi

  # Distribute the cluster-wired env to the app-bearing nodes (edge/app/data).
  # Vault reads deploy/production.env; deploy reads .env.production. Labs runs a
  # bare docker engine (no app stack) so it needs no env.
  if [ -n "${CLUSTER_ENV_FILE:-}" ] && [ -f "${CLUSTER_ENV_FILE:-}" ]; then
    echo "[env] distributing cluster env to edge/app/data"
    write_node_env "$EDGE_PUBLIC_IP" direct
    write_node_env "$APP_PRIVATE_IP" via-edge
    write_node_env "$DATA_PRIVATE_IP" via-edge
  else
    echo "[env] CLUSTER_ENV_FILE unset/missing — skipping env distribution (workflow sets it)"
  fi
  echo "=== cluster bootstrap done ==="
}

main "$@"
