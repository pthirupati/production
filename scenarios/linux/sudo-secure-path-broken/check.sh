#!/bin/bash
! grep -q 'secure_path="/usr/bin"' /etc/sudoers.d/99-bad-path 2>/dev/null && echo PASS && exit 0
grep -q '/usr/sbin' /etc/sudoers.d/99-bad-path 2>/dev/null && echo PASS && exit 0
echo FAIL: fix secure_path to include /usr/sbin and /sbin in /etc/sudoers.d/99-bad-path
exit 1
