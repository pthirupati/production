#!/bin/bash
set -e
mount -o remount,exec /tmp 2>/dev/null || true
sed -i 's#\(/tmp[^#
]*\)noexec,\?##g; s#\(/tmp[^#
]*\),noexec##g' /etc/fstab 2>/dev/null || true
