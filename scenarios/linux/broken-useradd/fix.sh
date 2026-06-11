#!/bin/bash
set -e
sed -i '/CORRUPTED:::ENTRY/d' /etc/passwd 2>/dev/null || true
sed -i '/fakegroup/d' /etc/group 2>/dev/null || true
chmod 644 /etc/passwd /etc/group
chmod 640 /etc/shadow 2>/dev/null || chmod 600 /etc/shadow
chown root:root /etc/passwd /etc/group
chown root:shadow /etc/shadow 2>/dev/null || chown root:root /etc/shadow
rm -f /etc/.pwd.lock
userdel -r fixitlab_testuser 2>/dev/null || true
userdel -r devops 2>/dev/null || true
id devops >/dev/null 2>&1 || useradd -m -s /bin/bash devops
usermod -s /bin/bash devops 2>/dev/null || true
mkdir -p "$(getent passwd devops | cut -d: -f6)"
chown devops:devops "$(getent passwd devops | cut -d: -f6)" 2>/dev/null || true
