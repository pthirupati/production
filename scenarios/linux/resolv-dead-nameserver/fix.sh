#!/bin/bash
set -e
echo 'nameserver 127.0.0.1' > /etc/resolv.conf
pkill -HUP dnsmasq 2>/dev/null || dnsmasq 2>/dev/null || true
sleep 1
