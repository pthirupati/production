#!/bin/bash
# Check that password complexity is configured
PWQUAL_CONF="/etc/security/pwquality.conf"
if [ ! -f "$PWQUAL_CONF" ]; then
  echo "FAIL: $PWQUAL_CONF not found — install libpam-pwquality"
  exit 1
fi
# Check minlen is set to at least 12
MINLEN=$(grep -E '^\s*minlen\s*=' "$PWQUAL_CONF" 2>/dev/null | grep -oE '[0-9]+' | head -1)
if [ -z "$MINLEN" ] || [ "$MINLEN" -lt 12 ]; then
  echo "FAIL: minlen is ${MINLEN:-not set} — set to at least 12 in $PWQUAL_CONF"
  exit 1
fi
# Check that complexity credits are configured (at least one negative credit value)
COMPLEXITY=$(grep -E '^\s*[duolm]credit\s*=\s*-[1-9]' "$PWQUAL_CONF" 2>/dev/null | wc -l)
if [ "$COMPLEXITY" -lt 2 ]; then
  echo "FAIL: password complexity credits not configured — set dcredit=-1, ucredit=-1, ocredit=-1, lcredit=-1 in $PWQUAL_CONF"
  exit 1
fi
echo "OK: password policy configured (minlen=$MINLEN, complexity rules: $COMPLEXITY credits set)"
exit 0
