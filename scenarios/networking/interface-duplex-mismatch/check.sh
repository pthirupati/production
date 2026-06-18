#!/bin/bash
# Check that eth0 is no longer in half-duplex mode
DUPLEX=$(ethtool eth0 2>/dev/null | grep 'Duplex:' | awk '{print $2}')
if [ "$DUPLEX" = "Half" ]; then
  echo "FAIL: eth0 is still in Half duplex mode — causing collisions and low throughput. Set to Full duplex."
  exit 1
fi
if [ "$DUPLEX" = "Full" ]; then
  echo "OK: eth0 is in Full duplex mode"
  exit 0
fi
# Check autoneg is on as alternative
AUTONEG=$(ethtool eth0 2>/dev/null | grep 'Advertised auto-negotiation\|Auto-negotiation:' | grep -c 'on\|Yes')
if [ "$AUTONEG" -gt 0 ]; then
  echo "OK: eth0 has auto-negotiation enabled (current duplex: ${DUPLEX:-unknown})"
  exit 0
fi
echo "FAIL: unable to verify duplex setting on eth0 — run: ethtool eth0"
exit 1
