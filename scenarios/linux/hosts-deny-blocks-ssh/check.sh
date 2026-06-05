#!/bin/bash
! grep -qE '^sshd:\s*ALL' /etc/hosts.deny 2>/dev/null && echo PASS && exit 0
grep -qE '^sshd:\s*ALL' /etc/hosts.allow 2>/dev/null && echo PASS && exit 0
echo FAIL: remove sshd: ALL from /etc/hosts.deny or allow in /etc/hosts.allow
exit 1
