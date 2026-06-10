#!/bin/bash
set -e
sed -i '/^sshd:[[:space:]]*ALL/d' /etc/hosts.deny 2>/dev/null || true
grep -q '^sshd:[[:space:]]*ALL' /etc/hosts.allow 2>/dev/null || echo 'sshd: ALL' >> /etc/hosts.allow
