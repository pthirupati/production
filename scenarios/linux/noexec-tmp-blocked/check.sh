#!/bin/bash
findmnt -n /tmp -o OPTIONS 2>/dev/null | grep -q noexec && echo "FAIL: /tmp still noexec — remount with exec" && exit 1
cp /opt/install/run.sh /tmp/run.sh && chmod +x /tmp/run.sh && /tmp/run.sh | grep -q installed && echo PASS && exit 0
echo FAIL: mount -o remount,exec /tmp (or remove noexec from fstab)
exit 1
