#!/bin/bash
# Check that the stale ARP entry for 192.168.1.1 is gone or updated
OLD_MAC="aa:bb:cc:dd:ee:ff"
TARGET_IP="192.168.1.1"
CURRENT_ARP=$(ip neigh show "$TARGET_IP" 2>/dev/null)
if echo "$CURRENT_ARP" | grep -qi "$OLD_MAC"; then
  echo "FAIL: ARP cache still shows old MAC ($OLD_MAC) for $TARGET_IP — flush with: ip neigh del $TARGET_IP dev eth0"
  exit 1
fi
# Check if entry is now correct or missing (missing = will be re-learned on next access)
if [ -z "$CURRENT_ARP" ] || echo "$CURRENT_ARP" | grep -qiE 'REACHABLE|STALE|DELAY|PROBE'; then
  CURRENT_MAC=$(echo "$CURRENT_ARP" | awk '{for(i=1;i<=NF;i++) if($i~/^([0-9a-f]{2}:){5}[0-9a-f]{2}$/){print $i}}' | head -1)
  if [ -z "$CURRENT_MAC" ] || [ "$CURRENT_MAC" != "$OLD_MAC" ]; then
    echo "OK: stale ARP entry cleared for $TARGET_IP"
    exit 0
  fi
fi
echo "OK: ARP cache for $TARGET_IP no longer shows the stale MAC address"
exit 0
