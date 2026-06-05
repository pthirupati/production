#!/bin/bash
grep -q 'AllowUsers.*deploy' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/* 2>/dev/null && echo PASS && exit 0
! grep -q 'AllowUsers adminonly' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/* 2>/dev/null && echo PASS && exit 0
echo FAIL: add deploy to AllowUsers or remove restrictive AllowUsers line
exit 1
