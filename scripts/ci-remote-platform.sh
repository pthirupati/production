#!/usr/bin/env bash
# Run on the production server via GitHub Actions SSH (single deploy entrypoint).
# Usage on server:  ./scripts/ci-remote-platform.sh deploy|stop
set -euo pipefail

ACTION="${1:-deploy}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"

chmod +x scripts/platform-start.sh scripts/platform-stop.sh scripts/build-scenario-images.sh \
  scripts/startup.sh scripts/ensure-ssl-certs.sh scripts/sync-production-env.sh 2>/dev/null || true

case "$ACTION" in
  deploy)
    export COMPOSE_FILE ENV_FILE
    export BUILD_SCENARIOS="${BUILD_SCENARIOS:-true}"
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
