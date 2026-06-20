#!/usr/bin/env bash
# Run on the production server via GitHub Actions SSH (single deploy entrypoint).
# Usage on server:  ./scripts/ci-remote-platform.sh deploy|stop
set -euo pipefail

ACTION="${1:-deploy}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# CLUSTER_ROLE=edge|app|data|labs selects the per-role compose file (four-droplet
# topology). When unset, COMPOSE_FILE defaults to the single-host prod compose so
# existing behavior is unchanged. platform-start.sh resolves the same mapping.
CLUSTER_ROLE="${CLUSTER_ROLE:-}"
case "$CLUSTER_ROLE" in
  edge) COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.edge.yml}" ;;
  app)  COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.app.yml}" ;;
  data) COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.data.yml}" ;;
  *)    COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}" ;;
esac
ENV_FILE="${ENV_FILE:-.env.production}"

chmod +x scripts/platform-start.sh scripts/platform-stop.sh scripts/build-scenario-images.sh \
  scripts/startup.sh scripts/ensure-ssl-certs.sh scripts/sync-production-env.sh \
  scripts/validate-scenario-images.sh scripts/ci-post-deploy-verify.sh scripts/run-full-e2e.sh \
  scripts/vault/lib.sh scripts/vault/ensure-network.sh 2>/dev/null || true

case "$ACTION" in
  deploy)
    export COMPOSE_FILE ENV_FILE CLUSTER_ROLE
    export BUILD_SCENARIOS="${BUILD_SCENARIOS:-true}"
    # Edge gateway needs APP_PRIVATE_IP to render the cluster nginx upstream.
    [ -n "${APP_PRIVATE_IP:-}" ] && export APP_PRIVATE_IP
    bash scripts/sync-production-env.sh "$ROOT/.env.production"
    ./scripts/platform-start.sh
    ;;
  stop)
    COMPOSE_FILE="$COMPOSE_FILE" ./scripts/platform-stop.sh
    ;;
  *)
    echo "Usage: $0 deploy|stop"
    exit 1
    ;;
esac
