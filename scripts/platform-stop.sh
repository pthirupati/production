#!/usr/bin/env bash
# Stop FixitLab platform WITHOUT deleting user data
# NEVER runs `docker compose down -v` — volumes persist across stop/start/reboot
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

echo "=== FixitLab Platform STOP (data preserved) ==="
docker compose -f "$COMPOSE_FILE" stop

echo ""
echo "✅ All services stopped."
echo "   Database volume fixitlab_db_data is UNTOUCHED."
echo "   Restart anytime: ./scripts/platform-start.sh"
echo ""
echo "   ⚠️  NEVER run: docker compose down -v  (that deletes user data)"
