#!/bin/bash
# Check that analysis was written and the fix was applied
if [ ! -f /tmp/analysis.txt ]; then
  echo "FAIL: /tmp/analysis.txt not found — write your analysis findings to this file"
  exit 1
fi
ANALYSIS_SIZE=$(wc -c < /tmp/analysis.txt)
if [ "$ANALYSIS_SIZE" -lt 20 ]; then
  echo "FAIL: /tmp/analysis.txt is too short — provide a meaningful analysis of the packet loss root cause"
  exit 1
fi
# Check that the txqueuelen was increased
TXQLEN=$(ip link show eth0 2>/dev/null | grep -oE 'qlen [0-9]+' | awk '{print $2}')
if [ -n "$TXQLEN" ] && [ "$TXQLEN" -lt 100 ]; then
  echo "FAIL: eth0 txqueuelen is still $TXQLEN — increase with: ip link set eth0 txqueuelen 1000"
  exit 1
fi
echo "OK: analysis written to /tmp/analysis.txt and txqueuelen fixed (current: ${TXQLEN:-default})"
exit 0
