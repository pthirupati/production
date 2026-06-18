#!/bin/bash
# Check that trunk port is configured with correct VLANs
TRUNKS=$(ovs-vsctl list port eth2 2>/dev/null | grep 'trunks' | grep -o '[0-9]*' | sort -n | tr '\n' ',')
if echo "$TRUNKS" | grep -q '20' && echo "$TRUNKS" | grep -q '30'; then
  echo "OK: trunk port eth2 allows VLAN 20 and VLAN 30"
  exit 0
fi
# Alternative check via ip link for VLAN sub-interfaces
if ip link show | grep -qE 'eth2\.20|vlan20' && ip link show | grep -qE 'eth2\.30|vlan30'; then
  echo "OK: VLAN sub-interfaces for 20 and 30 are present"
  exit 0
fi
echo "FAIL: trunk port is not passing VLAN 20 and VLAN 30 — check ovs-vsctl set port eth2 trunks=20,30"
exit 1
