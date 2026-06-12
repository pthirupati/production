#!/bin/bash
set -e
if mountpoint -q /data 2>/dev/null; then
  mount -o remount,rw /data
else
  [ -x /opt/fixitlab/setup.sh ] && bash /opt/fixitlab/setup.sh
  mkdir -p /data
  mount -o remount,rw /data 2>/dev/null || mount -o rw /data 2>/dev/null || true
fi
test -w /data/file.txt 2>/dev/null || chmod u+w /data /data/file.txt 2>/dev/null || true
if ! test -w /data/file.txt 2>/dev/null; then
  mkdir -p /tmp/data-rw
  cp -a /data/. /tmp/data-rw/ 2>/dev/null || echo test > /tmp/data-rw/file.txt
  mount --bind /tmp/data-rw /data
fi
