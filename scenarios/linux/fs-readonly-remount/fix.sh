#!/bin/bash
set -e
[ -x /opt/fixitlab/setup.sh ] && bash /opt/fixitlab/setup.sh 2>/dev/null || true
mount -o remount,rw /data
chmod u+w /data /data/file.txt 2>/dev/null || true
