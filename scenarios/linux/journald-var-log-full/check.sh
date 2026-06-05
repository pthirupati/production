#!/bin/bash
USE=$(df /var/log 2>/dev/null | tail -1 | awk '{print $5}' | tr -d '%')
[ "${USE:-100}" -lt 90 ] && echo PASS && exit 0
journalctl --disk-usage 2>/dev/null | grep -q journal
echo FAIL: free /var/log space — journalctl --vacuum-size=50M or delete /var/log/big/*.log
exit 1
