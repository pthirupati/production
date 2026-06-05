#!/bin/bash
! [ -f /var/lib/dpkg/lock-frontend ] && dpkg --audit 2>/dev/null | grep -qv . && echo PASS && exit 0
! [ -f /var/lib/dpkg/lock-frontend ] && echo PASS && exit 0
echo FAIL: rm /var/lib/dpkg/lock* && dpkg --configure -a
exit 1
