#!/bin/bash
# Prepare dummy gateway for static route lab
set -e
ip link add fb-dummy0 type dummy 2>/dev/null || true
ip addr add 172.16.0.1/32 dev fb-dummy0 2>/dev/null || ip addr add 172.16.0.1/32 dev lo
ip link set fb-dummy0 up 2>/dev/null || true
