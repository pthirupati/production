#!/bin/bash
set -e
iptables -D INPUT -p tcp --dport 80 -j DROP 2>/dev/null || true
service nginx restart 2>/dev/null || systemctl restart nginx 2>/dev/null || true
