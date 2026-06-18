#!/bin/bash
# Check that PMTUD is enabled
PMTU_DISC=$(sysctl -n net.ipv4.ip_no_pmtu_disc 2>/dev/null)
if [ "$PMTU_DISC" != "0" ]; then
  echo "FAIL: net.ipv4.ip_no_pmtu_disc=$PMTU_DISC — PMTUD is disabled. Set to 0: sysctl -w net.ipv4.ip_no_pmtu_disc=0"
  exit 1
fi
# Check that ICMP type 3 is not being blocked
if iptables -L INPUT -n 2>/dev/null | grep -q 'icmp.*type 3\|icmp.*destination-unreachable'; then
  # It's explicitly allowed
  echo "OK: PMTUD enabled and ICMP destination-unreachable allowed"
  exit 0
fi
# Check if there's a blanket DROP on ICMP without an allow for type 3
ICMP_DROP=$(iptables -L INPUT -n 2>/dev/null | grep -c 'DROP.*icmp\|icmp.*DROP')
if [ "$ICMP_DROP" -gt 0 ]; then
  echo "FAIL: PMTUD enabled but ICMP DROP rule may be blocking type 3 messages — add explicit ACCEPT for icmp type 3"
  exit 1
fi
echo "OK: PMTUD is enabled (ip_no_pmtu_disc=0)"
exit 0
