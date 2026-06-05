#!/bin/bash
# Block port 80 at container start (requires NET_ADMIN capability in lab container).
iptables -A INPUT -p tcp --dport 80 -j DROP 2>/dev/null || true
