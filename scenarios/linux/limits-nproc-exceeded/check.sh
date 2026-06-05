#!/bin/bash
! grep -q 'nproc 5' /etc/security/limits.d/99-nproc.conf 2>/dev/null && echo PASS && exit 0
grep -q 'nproc 1024' /etc/security/limits.d/99-nproc.conf 2>/dev/null && echo PASS && exit 0
echo FAIL: raise nproc limits in /etc/security/limits.d/99-nproc.conf
exit 1
