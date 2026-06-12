#!/bin/bash
set -e
chattr -iae /etc/passwd /etc/shadow /etc/group 2>/dev/null || true
sed -i '/CORRUPTED:::ENTRY/d' /etc/passwd 2>/dev/null || true
sed -i '/fakegroup/d' /etc/group 2>/dev/null || true
rm -f /etc/.pwd.lock
chmod 644 /etc/passwd /etc/group
chmod 640 /etc/shadow
chown root:root /etc/passwd /etc/group
chown root:shadow /etc/shadow 2>/dev/null || chown root:root /etc/shadow
userdel -r fixitlab_testuser 2>/dev/null || true
userdel -r devops 2>/dev/null || true
useradd -m -s /bin/bash devops
DEVOPS_HOME="$(getent passwd devops | cut -d: -f6)"
mkdir -p "$DEVOPS_HOME"
chown devops:devops "$DEVOPS_HOME"
chmod 755 "$DEVOPS_HOME"
# useradd can relax modes on some images — enforce final permissions
chmod 644 /etc/passwd /etc/group
chmod 640 /etc/shadow
chown root:root /etc/passwd /etc/group
chown root:shadow /etc/shadow 2>/dev/null || chown root:root /etc/shadow
