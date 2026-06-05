#!/usr/bin/env bash
# Full production E2E: API tests + Django unit tests + Docker log audit
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"
BASE_URL="${BASE_URL:-https://fixitlab.in}"
LOG_DIR="${LOG_DIR:-/tmp/fixitlab-e2e-logs-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$LOG_DIR"

echo "=== FixitLab Full E2E Test Run ==="
echo "Log directory: $LOG_DIR"
echo "E2E_SKIP_LAB=${E2E_SKIP_LAB:-0} RUN_FULL_E2E=${RUN_FULL_E2E:-1}"
echo ""

# ── 0. Scenario images must exist ──
echo ">>> [0/5] Scenario image check"
chmod +x "$ROOT/scripts/validate-scenario-images.sh"
bash "$ROOT/scripts/validate-scenario-images.sh" | tee "$LOG_DIR/scenario-images.txt"

# ── 1. Container health ──
echo ">>> [1/5] Container status"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps | tee "$LOG_DIR/containers.txt"

UNHEALTHY=$(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps --format json 2>/dev/null | grep -c '"Health":"unhealthy"' || true)
if [ "$UNHEALTHY" -gt 0 ]; then
  echo "WARNING: $UNHEALTHY unhealthy container(s)"
fi

# ── 2. Collect logs from all services ──
echo ""
echo ">>> [2/5] Collecting Docker logs"
SERVICES=(gateway backend frontend-prod database redis rabbitmq celery_worker celery_provisioning celery_maintenance celery_beat certbot)
for svc in "${SERVICES[@]}"; do
  echo "  logs: $svc"
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs "$svc" --tail 200 > "$LOG_DIR/${svc}.log" 2>&1 || true
done

# ── 3. Scan logs for errors ──
echo ""
echo ">>> [3/5] Log error scan"
ERROR_PATTERNS='ERROR|CRITICAL|Traceback|Exception|failed|FATAL'
for f in "$LOG_DIR"/*.log; do
  name=$(basename "$f" .log)
  count=$(grep -cE "$ERROR_PATTERNS" "$f" 2>/dev/null | head -1 || echo 0)
  count="${count//[^0-9]/}"
  count="${count:-0}"
  if [ "$count" -gt 0 ]; then
    echo "  $name: $count error lines (see $f)"
    grep -E "$ERROR_PATTERNS" "$f" | tail -5 >> "$LOG_DIR/error-summary.txt" 2>/dev/null || true
  else
    echo "  $name: clean"
  fi
done

# ── 4. Django unit tests (inside backend) ──
echo ""
echo ">>> [4/5] Django unit tests"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend \
  python manage.py test tests.test_jira_webhooks tests.test_api_security tests.test_billing_webhooks --verbosity=1 \
  2>&1 | tee "$LOG_DIR/unit-tests.log" || UNIT_FAIL=1

# ── 5. E2E API tests (inside + external) ──
echo ""
echo ">>> [5/5] E2E API tests"

# Internal (backend localhost — bypasses nginx)
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend \
  env E2E_SKIP_LAB="${E2E_SKIP_LAB:-0}" RUN_FULL_E2E="${RUN_FULL_E2E:-1}" \
  python /scripts/e2e_production_test.py \
  2>&1 | tee "$LOG_DIR/e2e-internal.log" || E2E_INTERNAL_FAIL=1

# External (through gateway + TLS)
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend \
  env BASE_URL="$BASE_URL" E2E_SKIP_LAB="${E2E_SKIP_LAB:-0}" RUN_FULL_E2E="${RUN_FULL_E2E:-1}" \
  python /scripts/e2e_production_test.py \
  2>&1 | tee "$LOG_DIR/e2e-external.log" || E2E_EXTERNAL_FAIL=1

echo ""
echo "=== E2E Summary ==="
echo "Logs saved to: $LOG_DIR"
[ -f "$LOG_DIR/error-summary.txt" ] && echo "Error summary:" && tail -20 "$LOG_DIR/error-summary.txt"

EXIT=0
[ "${UNIT_FAIL:-0}" = "1" ] && EXIT=1 && echo "UNIT TESTS: FAILED"
[ "${E2E_INTERNAL_FAIL:-0}" = "1" ] && EXIT=1 && echo "E2E INTERNAL: FAILED"
[ "${E2E_EXTERNAL_FAIL:-0}" = "1" ] && EXIT=1 && echo "E2E EXTERNAL: FAILED"

if [ "$EXIT" -eq 0 ]; then
  echo "ALL CHECKS PASSED"
fi

# ── 6. Remove all test users/data created during this run ──
echo ""
echo ">>> [6/6] Test data cleanup"
if [ "${E2E_SKIP_CLEANUP:-0}" != "1" ]; then
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend \
    python /scripts/cleanup-test-data.py 2>&1 | tee "$LOG_DIR/cleanup.log" || CLEANUP_FAIL=1
else
  echo "  Skipped (E2E_SKIP_CLEANUP=1)"
fi

[ "${CLEANUP_FAIL:-0}" = "1" ] && EXIT=1 && echo "CLEANUP: FAILED"

exit "$EXIT"
