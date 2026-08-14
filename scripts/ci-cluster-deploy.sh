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
MERGE_SEED_ONLY="${MERGE_SEED_ONLY:-true}"

# Docker Hub image pipeline (gated, additive). When the workflow has USE_DOCKERHUB
# on, deploy-cluster passes USE_DOCKERHUB=true + IMAGE_TAG=<git-sha> (+ optional
# FIXITLAB_IMAGE_NS) in the environment. We then tell the edge (D1) and app (D2)
# nodes — the only ones running pushed images — to PULL the pinned tag instead of
# rebuilding. When USE_DOCKERHUB is unset/false, IMG_ENV stays empty and every node
# deploys exactly as today (on-node `docker compose up --build`).
USE_DOCKERHUB="${USE_DOCKERHUB:-}"
IMG_ENV=""
case "${USE_DOCKERHUB}" in
  1|true|TRUE|yes|on)
    if [ -n "${IMAGE_TAG:-}" ]; then
      IMG_ENV="PULL_IMAGES=1 IMAGE_TAG=${IMAGE_TAG}"
      [ -n "${FIXITLAB_IMAGE_NS:-}" ] && IMG_ENV="${IMG_ENV} FIXITLAB_IMAGE_NS=${FIXITLAB_IMAGE_NS}"
      echo "Docker Hub pipeline ON — D1/D2 will pull ${FIXITLAB_IMAGE_NS:-fixitlab}/fixitlab-*:${IMAGE_TAG}"
    else
      echo "WARN: USE_DOCKERHUB set but IMAGE_TAG empty — falling back to on-node build"
    fi
    ;;
esac

EDGE_PUBLIC_IP="${EDGE_PUBLIC_IP:?EDGE_PUBLIC_IP required}"
APP_PRIVATE_IP="${APP_PRIVATE_IP:?APP_PRIVATE_IP required}"
DATA_PRIVATE_IP="${DATA_PRIVATE_IP:?DATA_PRIVATE_IP required}"
LABS_PRIVATE_IP="${LABS_PRIVATE_IP:?LABS_PRIVATE_IP required}"

_is_true() { case "${1:-}" in 1|true|TRUE|yes|on) return 0;; *) return 1;; esac; }

# Forward the Vault AppRole to the edge + app nodes so their sync-production-env.sh
# renders .env.production FROM Vault (the source of truth for rotated secrets such as
# the DB password / JWT keys) instead of falling back to the stale baked
# PRODUCTION_ENV_B64. The deploy-cluster job passes these from the vault-cluster job's
# outputs; if empty, the nodes fall back to the baked env exactly as before (no change).
VAULT_ENV=""
if [ -n "${VAULT_ROLE_ID:-}" ] && [ -n "${VAULT_SECRET_ID:-}" ]; then
  VAULT_ENV="VAULT_ENABLED=${VAULT_ENABLED:-true} VAULT_ROLE_ID=${VAULT_ROLE_ID} VAULT_SECRET_ID=${VAULT_SECRET_ID}"
  [ -n "${VAULT_UNSEAL_KEY:-}" ] && VAULT_ENV="${VAULT_ENV} VAULT_UNSEAL_KEY=${VAULT_UNSEAL_KEY}"
  echo "Vault AppRole present — edge+app will render .env.production from Vault (secrets source of truth)"
else
  echo "Vault AppRole absent — nodes use baked env (legacy path, unchanged)"
fi

KEY_FILE=""
if [ -n "${PROD_SSH_KEY:-}" ] && ! _is_true "$DRY_RUN"; then
  KEY_FILE="$(mktemp)"; printf '%s\n' "$PROD_SSH_KEY" | tr -d '\r' > "$KEY_FILE"; chmod 600 "$KEY_FILE"
  trap 'rm -f "$KEY_FILE"' EXIT
fi

remote() {
  local target_ip="$1" via_edge="$2"; shift 2
  local script="$*"
  # ServerAlive* keepalives: a role deploy can sit silent for minutes (e.g. the
  # backend readiness wait) with no stdout; without keepalives the idle two-hop
  # tunnel is torn down ("client_loop: send disconnect: Broken pipe") and reds the
  # job. 15s x 8 tolerates ~2min of silence on BOTH the target and the jump hop.
  local opts=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=8 -o TCPKeepAlive=yes)
  [ -n "$KEY_FILE" ] && opts+=(-i "$KEY_FILE" -o IdentitiesOnly=yes)
  if [ "$via_edge" = "via-edge" ]; then
    # Explicit ProxyCommand so the edge jump uses our key + skips host-key checks
    # (ProxyJump does not propagate -i / StrictHostKeyChecking to the jump host).
    local jopts="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=15 -o ServerAliveCountMax=8 -o TCPKeepAlive=yes"
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
    "${VAULT_ENV} ${IMG_ENV} CLUSTER_ROLE=edge APP_PRIVATE_IP=${APP_PRIVATE_IP} BUILD_SCENARIOS=false ./scripts/ci-remote-platform.sh deploy"
}

deploy_app() {
  echo "[3/4] Deploy D2 App (backend + celery + migrate)"
  # NOTE: deliberately NO ${VAULT_ENV} here. The app node (D2) has no local Vault
  # container (Vault runs only on the edge), so forwarding the AppRole made
  # sync-production-env.sh attempt a local `vault_compose exec` render that hangs/
  # fails — the regression that broke the 4D deploy after commit 7f8e654. D2 renders
  # its env the same way the known-good 7f8e654 run did: baked PRODUCTION_ENV_B64 /
  # last-good .env.production. Vault stays the source of truth on the edge (deploy_edge
  # keeps ${VAULT_ENV}); the backend's runtime Vault loader still reads it when reachable.
  if ! remote "$APP_PRIVATE_IP" via-edge \
    "${IMG_ENV} CLUSTER_ROLE=app BUILD_SCENARIOS=false MERGE_SEED_ONLY=${MERGE_SEED_ONLY} ./scripts/ci-remote-platform.sh deploy"; then
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

prepull_grader_images() {
  # Pre-pull the code-exec grader's tiny base images onto the D4 Labs engine.
  # Runs on EVERY deploy (independent of BUILD_SCENARIOS). Fail-closed by
  # default: if images are still missing after pull, the deploy fails so coding
  # labs do not silently soft-fail into needs_review. Ops escape hatch:
  # ALLOW_MISSING_SANDBOX_IMAGES=1.
  echo "[grader] Pre-pull sandbox base images on D4 Labs"
  remote "$APP_PRIVATE_IP" via-edge \
    "set -e
LK=/opt/fixitlab/deploy/labs_ssh/id_ed25519
if [ ! -f \"\$LK\" ]; then
  echo '  labs key missing on D2 — cannot prepull sandbox images'
  if [ \"\${ALLOW_MISSING_SANDBOX_IMAGES:-0}\" = 1 ]; then exit 0; fi
  exit 1
fi
install -m 700 -d /root/.ssh
sed -i '/# fixitlab-labs-docker/,+5d' /root/.ssh/config 2>/dev/null || true
printf '# fixitlab-labs-docker\nHost ${LABS_PRIVATE_IP}\n  IdentityFile %s\n  IdentitiesOnly yes\n  StrictHostKeyChecking no\n  UserKnownHostsFile /dev/null\n  ConnectTimeout 10\n  ServerAliveInterval 10\n  ServerAliveCountMax 3\n' \"\$LK\" >> /root/.ssh/config
chmod 600 /root/.ssh/config
export DOCKER_HOST=ssh://root@${LABS_PRIVATE_IP}
export SANDBOX_PYTHON_IMAGE=\${SANDBOX_PYTHON_IMAGE:-python:3.12-alpine}
export SANDBOX_NODE_IMAGE=\${SANDBOX_NODE_IMAGE:-node:20-alpine}
export ALLOW_MISSING_SANDBOX_IMAGES=\${ALLOW_MISSING_SANDBOX_IMAGES:-0}
if [ -x /opt/fixitlab/scripts/ensure-sandbox-images.sh ]; then
  bash /opt/fixitlab/scripts/ensure-sandbox-images.sh
elif [ -x ./scripts/ensure-sandbox-images.sh ]; then
  bash ./scripts/ensure-sandbox-images.sh
else
  timeout 120 docker pull \"\$SANDBOX_PYTHON_IMAGE\" || true
  timeout 120 docker pull \"\$SANDBOX_NODE_IMAGE\" || true
  missing=0
  docker image inspect \"\$SANDBOX_PYTHON_IMAGE\" >/dev/null 2>&1 || missing=1
  docker image inspect \"\$SANDBOX_NODE_IMAGE\" >/dev/null 2>&1 || missing=1
  if [ \"\$missing\" = 1 ]; then
    echo '[grader] sandbox images still absent on D4'
    if [ \"\$ALLOW_MISSING_SANDBOX_IMAGES\" = 1 ]; then exit 0; fi
    exit 1
  fi
  echo '[grader] sandbox images present on D4'
fi"
}

main() {
  echo "=== FixitLab cluster deploy (dry_run=$DRY_RUN build_scenarios=$BUILD_SCENARIOS) ==="
  deploy_data
  deploy_edge
  deploy_app
  build_labs_images
  prepull_grader_images
  echo "=== cluster deploy done ==="
}

main "$@"
