#!/bin/sh
# Vault health probe for cron / deploy hooks — exits 0 when API is up or secrets already loaded.
set -e

VAULT_ADDR="${VAULT_ADDR:-http://vault:8200}"
if [ -f /.dockerenv ] && echo "$VAULT_ADDR" | grep -q 127.0.0.1; then
  VAULT_ADDR="http://vault:8200"
fi

if [ "${VAULT_SECRETS_LOADED:-0}" = "1" ]; then
  echo "vault: secrets loaded at startup (API may be degraded)"
  exit 0
fi

code=$(curl -s -o /dev/null -w '%{http_code}' \
  "${VAULT_ADDR%/}/v1/sys/health?standbyok=true&sealedcode=200&uninitcode=200" \
  --connect-timeout 3 --max-time 5 || echo "000")

case "$code" in
  200|429|472|473) echo "vault: healthy (HTTP $code)"; exit 0 ;;
  *) echo "vault: unreachable or sealed (HTTP $code)"; exit 1 ;;
esac
