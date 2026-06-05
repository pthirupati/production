#!/bin/bash
mkdir -p /var/log
fallocate -l 80M /var/log/app.log 2>/dev/null || dd if=/dev/zero of=/var/log/app.log bs=1M count=80
tail -f /var/log/app.log >/dev/null 2>&1 &
echo $! >/var/run/logholder.pid
rm -f /var/log/app.log

