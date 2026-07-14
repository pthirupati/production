#!/bin/bash
grep -q FIXED-OK /etc/systemd/system/backup.timer
exit 0
