#!/bin/bash
set -e
mountpoint -q /data || true
mount -o remount,rw /data 2>/dev/null || true
chmod u+w /data /data/file.txt 2>/dev/null || true
# Fallback if remount fails: bind-mount a writable layer
if ! test -w /data/file.txt 2>/dev/null; then
  mkdir -p /tmp/data-rw
  cp -a /data/. /tmp/data-rw/ 2>/dev/null || echo test > /tmp/data-rw/file.txt
  mount --bind /tmp/data-rw /data
fi
