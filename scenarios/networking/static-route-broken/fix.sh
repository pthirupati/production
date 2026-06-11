#!/bin/bash
set -e
[ -x /opt/fixitlab/setup.sh ] && bash /opt/fixitlab/setup.sh 2>/dev/null || true
ip route replace 10.50.0.0/24 via 172.16.0.1 dev lo 2>/dev/null || \
  ip route replace 10.50.0.0/24 via 172.16.0.1 dev fb-dummy0 2>/dev/null || \
  ip route add 10.50.0.0/24 via 172.16.0.1
