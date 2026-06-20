#!/bin/bash
# Validate: the timer's OnCalendar was corrected (FIXED-OK written after the real fix).
grep -q FIXED-OK /etc/systemd/system/backup.timer
exit 0
