#!/bin/bash
set -e
mount -o remount,rw /data
chmod u+w /data /data/file.txt 2>/dev/null || true
