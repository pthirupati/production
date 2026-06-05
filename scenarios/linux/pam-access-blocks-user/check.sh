#!/bin/bash
! grep -qE '^- : opsuser :' /etc/security/access.conf 2>/dev/null && echo PASS && exit 0
grep -qE '^\+ : opsuser :' /etc/security/access.conf 2>/dev/null && echo PASS && exit 0
echo FAIL: remove deny rule for opsuser in /etc/security/access.conf or add explicit allow
exit 1
