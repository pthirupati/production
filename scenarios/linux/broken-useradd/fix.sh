#!/bin/bash
set -e
chattr -i /etc/passwd /etc/shadow /etc/group 2>/dev/null || true
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
mkdir -p "$(getent passwd devops | cut -d: -f6)"
chown devops:devops "$(getent passwd devops | cut -d: -f6)"
