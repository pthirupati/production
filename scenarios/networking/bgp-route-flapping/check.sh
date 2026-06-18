#!/bin/bash
# Verify BGP session is Established and timer config is correct
BGP_STATE=$(vtysh -c 'show bgp summary' 2>/dev/null | grep -E 'Estab|Established' | wc -l)
if [ "$BGP_STATE" -gt 0 ]; then
  # Also check timers are not too aggressive (keepalive should be >= 10)
  TIMER=$(vtysh -c 'show bgp neighbors' 2>/dev/null | grep 'Hold time is' | awk '{print $4}' | head -1)
  if [ -n "$TIMER" ] && [ "$TIMER" -lt 30 ]; then
    echo "FAIL: BGP session established but holdtime ($TIMER) is still too low — set to at least 30s"
    exit 1
  fi
  echo "OK: BGP session is Established with appropriate timers"
  exit 0
fi
echo "FAIL: No BGP sessions in Established state — check peer config and timer settings"
exit 1
