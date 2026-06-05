#!/bin/bash
! grep -q 'umask 000' /etc/profile.d/99-bad-umask.sh 2>/dev/null && echo PASS && exit 0
echo FAIL: set umask 022 in /etc/profile.d/99-bad-umask.sh
exit 1
