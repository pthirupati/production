#!/bin/bash
AVAIL=$(df -i /var/cache 2>/dev/null | tail -1 | awk '{print $4}')
[ "${AVAIL:-0}" -gt 50 ] && echo PASS && exit 0
echo FAIL: free inodes on /var/cache (need >50). Delete unused files under /var/cache/app
exit 1
