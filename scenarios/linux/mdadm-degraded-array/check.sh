#!/bin/bash
# [UU] appears on the blocks line below the md0 header in modern kernels.
if grep -A2 '^md0 ' /proc/mdstat 2>/dev/null | grep -qE '\[2/2\] \[UU\]|\[UU\]'; then
  echo PASS
  exit 0
fi
if grep -A2 '^md0 ' /proc/mdstat 2>/dev/null | grep -qE '\[U_|\[_U|/2\] \[_'; then
  echo "FAIL: RAID still degraded — add missing device to md0"
  exit 1
fi
echo FAIL: rebuild RAID1 — mdadm --manage /dev/md0 --add /dev/loopXp2 then wait for [UU]
exit 1
