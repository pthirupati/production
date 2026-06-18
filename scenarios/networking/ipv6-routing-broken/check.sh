#!/bin/bash
# Check that radvd is running and configured correctly
if ! systemctl is-active --quiet radvd 2>/dev/null; then
  echo "FAIL: radvd is not running — start it with: systemctl start radvd"
  exit 1
fi
# Check that AdvSendAdvert is enabled
if grep -qi 'AdvSendAdvert on' /etc/radvd.conf 2>/dev/null; then
  # Check AdvAutonomous is enabled
  if grep -qi 'AdvAutonomous on' /etc/radvd.conf 2>/dev/null; then
    echo "OK: radvd is running with AdvSendAdvert and AdvAutonomous enabled"
    exit 0
  else
    echo "FAIL: radvd running but AdvAutonomous is not set to on — hosts cannot autoconfigure IPv6 addresses"
    exit 1
  fi
fi
echo "FAIL: AdvSendAdvert is not set to on in /etc/radvd.conf — Router Advertisements are not being sent"
exit 1
