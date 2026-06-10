#!/bin/bash
set -e
mount -o remount,rw /data 2>/dev/null || true
chmod u+w /data /data/file.txt 2>/dev/null || true
