#!/usr/bin/env bash
# Post-deploy verification on production server (health + scenario images + E2E).
# Called from GitHub Actions after deploy via SSH.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"
RUN_E2E="${RUN_E2E:-true}"
SITE_URL="${SITE_URL:-https://fixitlab.in}"

# shellcheck source=env-helpers.sh
source "$ROOT/scripts/env-helpers.sh"
PROD_HOST="$(env_val PROD_HOST "$ENV_FILE")"
PROD_HOST="${PROD_HOST:-$(python3 -c "import json; print(json.load(open('$ROOT/infra/digitalocean/production.json')).get('public_ipv4',''))" 2>/dev/null || true)}"

echo "=== Post-deploy verification ==="
echo "Host: ${PROD_HOST:-unknown} | Site: $SITE_URL | E2E: $RUN_E2E"

fail=0

# ── 1. Container status ──
echo ""
echo ">>> [1/6] Docker container status"
if ! docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps | tee /tmp/fixitlab-ps.txt; then
  echo "ERROR: docker compose ps failed"
  fail=1
fi

# ── 2. Internal API health (bypass nginx IP restrictions) ──
echo ""
echo ">>> [2/6] Internal API health"
if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend python -c \
  "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/api/health/'); assert r.status==200"; then
  echo "  ✓ Backend /api/health/ OK"
else
  echo "ERROR: Backend health check failed"
  fail=1
fi

# ── 3. Public nginx health (what GitHub runners can reach) ──
echo ""
echo ">>> [3/6] Public gateway health"
if [ -n "$PROD_HOST" ]; then
  if curl -sf --max-time 15 "http://${PROD_HOST}/health" | grep -q ok; then
    echo "  ✓ http://${PROD_HOST}/health OK"
  else
    echo "ERROR: Public /health failed on $PROD_HOST"
    fail=1
  fi
else
  echo "WARN: PROD_HOST not set — skipping public health"
fi

if curl -sf --max-time 20 "${SITE_URL}/api/config/" >/dev/null 2>&1; then
  echo "  ✓ ${SITE_URL}/api/config/ OK"
else
  echo "WARN: HTTPS site check failed (DNS/SSL may still be propagating)"
fi

# ── 4. Scenario Docker images ──
echo ""
echo ">>> [4/6] Scenario lab images"
chmod +x "$ROOT/scripts/validate-scenario-images.sh"
if bash "$ROOT/scripts/validate-scenario-images.sh"; then
  echo "  ✓ All scenario images present"
else
  echo "ERROR: Missing scenario images — labs will fail to start"
  echo "  Fix: re-run deploy with build_scenarios=true"
  fail=1
fi

# ── 5. Sample lab provisioning (multi-user) ──
echo ""
echo ">>> [5/6] Lab provisioning sample"
if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend \
  env E2E_SKIP_LAB=0 LAB_SAMPLE=5 python /scripts/validate-scenario-labs.py; then
  echo "  ✓ Sample lab provisioning OK"
else
  echo "ERROR: Lab provisioning validation failed"
  fail=1
fi

# ── 6. Full E2E API suite ──
echo ""
echo ">>> [6/6] Full E2E API tests"
if [ "$RUN_E2E" = "true" ] || [ "$RUN_E2E" = "1" ]; then
  chmod +x "$ROOT/scripts/run-full-e2e.sh"
  export E2E_SKIP_LAB=0
  export RUN_FULL_E2E=1
  export BASE_URL="$SITE_URL"
  if bash "$ROOT/scripts/run-full-e2e.sh"; then
    echo "  ✓ Full E2E passed"
  else
    echo "ERROR: E2E tests failed"
    fail=1
  fi
else
  echo "  Skipped (RUN_E2E=$RUN_E2E)"
fi

echo ""
if [ "$fail" -ne 0 ]; then
  echo "=== VERIFICATION FAILED ==="
  exit 1
fi
echo "=== ALL POST-DEPLOY CHECKS PASSED ==="
