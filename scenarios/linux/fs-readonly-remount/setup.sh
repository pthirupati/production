#!/bin/bash
# Simulate read-only data directory at container start.
mkdir -p /data
echo test > /data/file.txt
chmod 555 /data
touch /data/.ro
mount -o remount,ro /data 2>/dev/null || true
