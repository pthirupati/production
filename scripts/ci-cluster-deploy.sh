#!/usr/bin/env bash
# Deploy the FixitLab platform across the four-droplet cluster, in dependency order:
#
#   1. D3 Data  — postgres + pgbouncer        (CLUSTER_ROLE=data)
#   2. D1 Edge  — gateway/redis/rabbitmq/vault (CLUSTER_ROLE=edge)
#   3. D2 App   — backend + celery + migrate   (CLUSTER_ROLE=app)
#   4. D4 Labs  — build scenario lab images    (remote docker engine)
#
# Each node runs scripts/ci-remote-platform.sh with the matching CLUSTER_ROLE,
# which selects the per-role compose file via platform-start.sh.
#
# Idempotent. DRY_RUN=1 prints the ssh commands instead of running them.
#
# Required env:
#   EDGE_PUBLIC_IP EDGE_PRIVATE_IP APP_PRIVATE_IP DATA_PRIVATE_IP LABS_PRIVATE_IP
#   PROD_SSH_KEY
#   BUILD_SCENARIOS (default true)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DRY_RUN="${DRY_RUN:-0}"
BUILD_SCENARIOS="${BUILD_SCENARIOS:-true}"

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
    # Explicit ProxyCommand so the edge jump uses our key + skips host-key checks
    # (ProxyJump does not propagate -i / StrictHostKeyChecking to the jump host).
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
chmod +x scripts/ci-remote-platform.sh scripts/platform-start.sh scripts/sync-production-env.sh 2>/dev/null || true
${script}
EOF
}

deploy_data() {
  echo "[1/4] Deploy D3 Data (postgres + pgbouncer)"
  remote "$DATA_PRIVATE_IP" via-edge \
    "CLUSTER_ROLE=data BUILD_SCENARIOS=false ./scripts/ci-remote-platform.sh deploy"
}

deploy_edge() {
  echo "[2/4] Deploy D1 Edge (gateway/redis/rabbitmq/vault)"
  remote "$EDGE_PUBLIC_IP" direct \
    "CLUSTER_ROLE=edge APP_PRIVATE_IP=${APP_PRIVATE_IP} BUILD_SCENARIOS=false ./scripts/ci-remote-platform.sh deploy"
}

deploy_app() {
  echo "[3/4] Deploy D2 App (backend + celery + migrate)"
  if ! remote "$APP_PRIVATE_IP" via-edge \
    "CLUSTER_ROLE=app BUILD_SCENARIOS=false ./scripts/ci-remote-platform.sh deploy"; then
    echo "===== [diagnostic] D2 backend startup logs (last 120 lines) ====="
    remote "$APP_PRIVATE_IP" via-edge \
      "docker logs fixitlab-backend-1 --tail 120 2>&1 || (cd /opt/fixitlab && docker compose -f docker-compose.app.yml logs --tail 120 backend 2>&1) || true" || true
    echo "===== [diagnostic] end backend logs ====="
    return 1
  fi
}

build_labs_images() {
  echo "[4/4] Build scenario lab images on D4 Labs (remote docker engine)"
  if ! _is_true "$BUILD_SCENARIOS"; then
    echo "  BUILD_SCENARIOS=$BUILD_SCENARIOS — skipping scenario image build"
    return 0
  fi
  # The App droplet drives the build against D4's docker engine over ssh:// .
  remote "$APP_PRIVATE_IP" via-edge \
    "export DOCKER_HOST=ssh://root@${LABS_PRIVATE_IP}
chmod +x scripts/build-scenario-images.sh scripts/validate-scenario-images.sh 2>/dev/null || true
bash scripts/build-scenario-images.sh
bash scripts/validate-scenario-images.sh"
}

main() {
  echo "=== FixitLab cluster deploy (dry_run=$DRY_RUN build_scenarios=$BUILD_SCENARIOS) ==="
  deploy_data
  deploy_edge
  deploy_app
  build_labs_images
  echo "=== cluster deploy done ==="
}

main "$@"
