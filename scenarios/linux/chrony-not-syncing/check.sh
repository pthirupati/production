#!/bin/bash
! grep -q 'invalid.ntp.example' /etc/chrony/chrony.conf && echo PASS && exit 0
echo FAIL: remove invalid pool from /etc/chrony/chrony.conf and restart chrony
exit 1
