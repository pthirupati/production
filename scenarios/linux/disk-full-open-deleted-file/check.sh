#!/bin/bash
USE=$(df /var/log | tail -1 | awk '{print $5}' | tr -d '%')
[ "$USE" -lt 85 ] && echo PASS && exit 0
echo FAIL: /var/log still full — find deleted-but-open files: lsof +L1 /var/log
exit 1
