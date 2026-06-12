#!/bin/bash
set -e
. /opt/fixitlab/lab-loop.sh
SPARE=$(cat /etc/fixitlab-raid-spare 2>/dev/null || true)
if [ -z "$SPARE" ] || [ ! -b "$SPARE" ]; then
  SPARE=$(fixitlab_loop_attach /opt/fixitlab/backing/raid2.img 120M)
  echo "$SPARE" > /etc/fixitlab-raid-spare
fi
[ -b "$SPARE" ] || { echo "spare loop device missing" >&2; exit 1; }
grep -q 'md0' /proc/mdstat 2>/dev/null || { echo "/dev/md0 not active" >&2; exit 1; }
mdadm --manage /dev/md0 --add "$SPARE" 2>/dev/null || mdadm /dev/md0 --add "$SPARE"
for _ in $(seq 1 60); do
  grep -q '\[UU\]' /proc/mdstat 2>/dev/null && break
  sleep 1
done
mkdir -p /data
mountpoint -q /data || mount /dev/md0 /data 2>/dev/null || true
