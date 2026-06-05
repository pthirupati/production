#!/bin/bash
[ -f /var/run/cron-ok ] && echo PASS && exit 0
crontab -l 2>/dev/null | grep -qE 'PATH=.*usr/local' && echo PASS && exit 0
crontab -l 2>/dev/null | grep -q '/usr/local/bin/backup.sh' && echo PASS && exit 0
echo FAIL: add PATH=/usr/local/bin:/bin:/usr/bin to crontab or use full path to backup.sh
exit 1
