#!/bin/bash
# Expect route to 10.50.0.0/24 via 172.16.0.1
if ip route | grep -q '10.50.0.0/24.*172.16.0.1'; then
  echo "OK: static route present"
  exit 0
fi
echo "FAIL: add route: ip route add 10.50.0.0/24 via 172.16.0.1"
exit 1
