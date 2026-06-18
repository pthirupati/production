#!/bin/bash
# Check that bonding miimon is enabled
BOND_INFO=$(cat /proc/net/bonding/bond0 2>/dev/null)
if [ -z "$BOND_INFO" ]; then
  echo "FAIL: bond0 interface not found — ensure bonding module is loaded and bond0 is configured"
  exit 1
fi
MII_INTERVAL=$(echo "$BOND_INFO" | grep 'MII Polling Interval' | awk '{print $NF}')
if [ -z "$MII_INTERVAL" ] || [ "$MII_INTERVAL" = "0" ]; then
  echo "FAIL: MII Polling Interval is 0 — link failures will not be detected. Set miimon=100 in bond configuration"
  exit 1
fi
# Check that the bond mode is active-backup
if echo "$BOND_INFO" | grep -q 'Mode: active-backup\|mode: active-backup'; then
  echo "OK: bond0 in active-backup mode with miimon=${MII_INTERVAL}ms — failover detection enabled"
  exit 0
fi
echo "OK: bond0 miimon=${MII_INTERVAL}ms (link monitoring enabled)"
exit 0
