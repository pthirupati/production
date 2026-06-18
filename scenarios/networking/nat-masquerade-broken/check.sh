#!/bin/bash
# Check IP forwarding is enabled
FWD=$(cat /proc/sys/net/ipv4/ip_forward)
if [ "$FWD" != "1" ]; then
  echo "FAIL: IP forwarding is disabled — run: sysctl -w net.ipv4.ip_forward=1"
  exit 1
fi
# Check MASQUERADE rule exists in nat POSTROUTING
if iptables -t nat -L POSTROUTING -n 2>/dev/null | grep -qiE 'MASQUERADE|masq'; then
  echo "OK: IP forwarding enabled and MASQUERADE rule present in POSTROUTING"
  exit 0
fi
echo "FAIL: MASQUERADE rule missing from iptables nat POSTROUTING — add it with: iptables -t nat -A POSTROUTING -s 192.168.100.0/24 -o eth0 -j MASQUERADE"
exit 1
