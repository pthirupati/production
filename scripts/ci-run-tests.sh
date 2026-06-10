#!/usr/bin/env bash
# Run tests on the production server WITHOUT deploy (manual / CI tests workflow).
#
# Usage (on server):
#   RUN_UNIT=true RUN_E2E=true ./scripts/ci-run-tests.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"
RUN_UNIT="${RUN_UNIT:-true}"
RUN_E2E="${RUN_E2E:-true}"
RUN_LAB_VALIDATION="${RUN_LAB_VALIDATION:-true}"
SKIP_CLEANUP="${E2E_SKIP_CLEANUP:-0}"

# shellcheck source=env-helpers.sh
source "$ROOT/scripts/env-helpers.sh"
SITE_URL="${SITE_URL:-$(env_val SITE_URL "$ENV_FILE")}"
SITE_URL="${SITE_URL:-https://fixitlab.in}"
export SITE_URL

chmod +x scripts/run-full-e2e.sh scripts/cleanup-test-data.py \
  scripts/validate-scenario-images.sh scripts/validate-scenario-labs.py 2>/dev/null || true

echo "=== FixitLab Tests (no deploy) ==="
echo "RUN_UNIT=$RUN_UNIT RUN_E2E=$RUN_E2E RUN_LAB_VALIDATION=$RUN_LAB_VALIDATION"
echo "SITE_URL=$SITE_URL"

# Rebuild app images so server tests use latest code (backend is baked into image, not mounted)
if [ "$RUN_UNIT" = "true" ] || [ "$RUN_UNIT" = "1" ] || [ "$RUN_E2E" = "true" ] || [ "$RUN_E2E" = "1" ] || [ "$RUN_LAB_VALIDATION" = "true" ] || [ "$RUN_LAB_VALIDATION" = "1" ]; then
  echo ""
  echo ">>> Rebuild backend / frontend / gateway (latest code)"
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build backend frontend-prod gateway
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d backend frontend-prod gateway
  echo ">>> Waiting for backend healthy..."
  for _ in $(seq 1 90); do
    if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps backend 2>/dev/null | grep -q "(healthy)"; then
      break
    fi
    sleep 2
  done
fi

fail=0

if [ "$RUN_UNIT" = "true" ] || [ "$RUN_UNIT" = "1" ]; then
  echo ""
  echo ">>> Django unit tests"
  if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend \
    python manage.py test tests --settings=config.test_settings --verbosity=1; then
    echo "  ✓ Unit tests passed"
  else
    echo "ERROR: Unit tests failed"
    fail=1
  fi
fi

if [ "$RUN_LAB_VALIDATION" = "true" ] || [ "$RUN_LAB_VALIDATION" = "1" ]; then
  echo ""
  echo ">>> Scenario images"
  if bash "$ROOT/scripts/validate-scenario-images.sh"; then
    echo "  ✓ Scenario images OK"
  else
    echo "ERROR: Missing scenario images"
    fail=1
  fi

  echo ""
  echo ">>> All scenarios lab E2E (dynamic — every tech/scenario, 3 users)"
  if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend \
    env E2E_SKIP_LAB=0 E2E_MULTI_USERS=3 E2E_SKIP_CLEANUP=1 python /scripts/e2e_all_scenarios_labs.py; then
    echo "  ✓ All scenarios lab E2E passed"
  else
    echo "ERROR: All scenarios lab E2E failed"
    fail=1
  fi
fi

RUN_PLAYWRIGHT="${RUN_PLAYWRIGHT:-false}"
if [ "$RUN_PLAYWRIGHT" = "true" ] || [ "$RUN_PLAYWRIGHT" = "1" ]; then
  echo ""
  echo ">>> Playwright frontend E2E"
  if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend \
    env SITE_URL="$SITE_URL" E2E_SKIP_LAB=1 python /scripts/e2e_playwright_site.py 2>/dev/null; then
    echo "  ✓ Playwright passed"
  else
    echo "WARN: Playwright skipped or failed (install playwright in backend image for full UI tests)"
  fi
fi

if [ "$RUN_E2E" = "true" ] || [ "$RUN_E2E" = "1" ]; then
  echo ""
  echo ">>> Full E2E (all tabs, features, admin)"
  export E2E_SKIP_LAB=0
  export RUN_FULL_E2E=1
  export E2E_SKIP_DUPLICATE_LABS=1
  export BASE_URL="$SITE_URL"
  if bash "$ROOT/scripts/run-full-e2e.sh"; then
    echo "  ✓ E2E passed"
  else
    echo "ERROR: E2E failed"
    fail=1
  fi
fi

if [ "$SKIP_CLEANUP" != "1" ]; then
  echo ""
  echo ">>> Test data cleanup"
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend \
    python /scripts/cleanup-test-data.py || fail=1
fi

if [ "$fail" -ne 0 ]; then
  echo "=== TESTS FAILED ==="
  exit 1
fi
echo "=== ALL TESTS PASSED ==="
