#!/bin/bash
! grep -q '^appuser$' /etc/cron.deny 2>/dev/null && echo PASS && exit 0
echo FAIL: remove appuser from /etc/cron.deny or add to /etc/cron.allow
exit 1
