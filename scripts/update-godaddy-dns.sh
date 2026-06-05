#!/usr/bin/env bash
# Update GoDaddy DNS A record (@) and www CNAME after production IP change.
#
# Requires in env or deploy/production.env:
#   GODADDY_API_KEY, GODADDY_API_SECRET
# Optional:
#   GODADDY_DOMAIN=fixitlab.in
#   DNS_TTL=600
#
# Usage:
#   ./scripts/update-godaddy-dns.sh 64.227.175.89
#   PRODUCTION_ENV_B64=... ./scripts/update-godaddy-dns.sh 64.227.175.89
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PUBLIC_IP="${1:-${PUBLIC_IP:-}}"
ENV_FILE="${ENV_FILE:-$ROOT/deploy/production.env}"

if [ -z "$PUBLIC_IP" ]; then
  echo "Usage: $0 <public_ipv4>"
  exit 1
fi

read_env() {
  local key="$1"
  if [ -f "$ENV_FILE" ] && grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    grep "^${key}=" "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '\r'
    return 0
  fi
  return 1
}

load_from_b64() {
  if [ -n "${PRODUCTION_ENV_B64:-}" ]; then
    local tmp
    tmp="$(mktemp)"
    echo "$PRODUCTION_ENV_B64" | base64 -d > "$tmp"
    ENV_FILE="$tmp"
    trap 'rm -f "$tmp"' EXIT
  fi
}

load_from_b64

GODADDY_API_KEY="${GODADDY_API_KEY:-$(read_env GODADDY_API_KEY 2>/dev/null || true)}"
GODADDY_API_SECRET="${GODADDY_API_SECRET:-$(read_env GODADDY_API_SECRET 2>/dev/null || true)}"
GODADDY_DOMAIN="${GODADDY_DOMAIN:-$(read_env GODADDY_DOMAIN 2>/dev/null || echo fixitlab.in)}"
DNS_TTL="${DNS_TTL:-$(read_env DNS_TTL 2>/dev/null || echo 600)}"

if [ -z "$GODADDY_API_KEY" ] || [ -z "$GODADDY_API_SECRET" ]; then
  echo "SKIP: GoDaddy DNS not configured (set GODADDY_API_KEY + GODADDY_API_SECRET in production env)"
  exit 0
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl required"
  exit 1
fi

API="https://api.godaddy.com/v1/domains/${GODADDY_DOMAIN}/records"
AUTH="sso-key ${GODADDY_API_KEY}:${GODADDY_API_SECRET}"

echo "=== GoDaddy DNS update ==="
echo "  domain: $GODADDY_DOMAIN"
echo "  A @    → $PUBLIC_IP"
echo "  CNAME www → $GODADDY_DOMAIN"

# Root A record
HTTP_CODE=$(curl -sS -o /tmp/godaddy-a.json -w "%{http_code}" -X PATCH \
  -H "Authorization: $AUTH" \
  -H "Content-Type: application/json" \
  -d "[{\"data\":\"${PUBLIC_IP}\",\"ttl\":${DNS_TTL}}]" \
  "${API}/A/@")

if [ "$HTTP_CODE" -lt 200 ] || [ "$HTTP_CODE" -ge 300 ]; then
  echo "ERROR: GoDaddy A record update failed (HTTP $HTTP_CODE)"
  cat /tmp/godaddy-a.json 2>/dev/null || true
  exit 1
fi
echo "  ✓ A @ updated"

# www → root (CNAME)
HTTP_CODE=$(curl -sS -o /tmp/godaddy-www.json -w "%{http_code}" -X PUT \
  -H "Authorization: $AUTH" \
  -H "Content-Type: application/json" \
  -d "[{\"data\":\"${GODADDY_DOMAIN}.\",\"ttl\":${DNS_TTL}}]" \
  "${API}/CNAME/www")

if [ "$HTTP_CODE" -lt 200 ] || [ "$HTTP_CODE" -ge 300 ]; then
  echo "WARN: www CNAME update failed (HTTP $HTTP_CODE) — A record may still be enough"
  cat /tmp/godaddy-www.json 2>/dev/null || true
else
  echo "  ✓ CNAME www updated"
fi

echo ""
echo "Verify (may take 1–10 min to propagate):"
echo "  dig +short ${GODADDY_DOMAIN}"
echo "  dig +short www.${GODADDY_DOMAIN}"
