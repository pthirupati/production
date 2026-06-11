#!/bin/bash
set -e
faillock --user lockeduser --reset 2>/dev/null || true
rm -f /var/run/faillock/lockeduser /var/run/faillock/* 2>/dev/null || true
passwd -u lockeduser 2>/dev/null || true
usermod -U lockeduser 2>/dev/null || true
echo 'lockeduser:lockedpass' | chpasswd 2>/dev/null || true
passwd -S lockeduser 2>/dev/null | grep -qE ' P | L ' || passwd -u lockeduser 2>/dev/null || true
