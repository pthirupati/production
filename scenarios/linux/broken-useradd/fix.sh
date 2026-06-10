#!/bin/bash
set -e
sed -i '/CORRUPTED:::ENTRY/d' /etc/passwd 2>/dev/null || true
sed -i '/fakegroup/d' /etc/group 2>/dev/null || true
chmod 644 /etc/passwd /etc/group
chmod 640 /etc/shadow 2>/dev/null || chmod 600 /etc/shadow
rm -f /etc/.pwd.lock
id devops >/dev/null 2>&1 || useradd -m -s /bin/bash devops
usermod -s /bin/bash devops 2>/dev/null || true
