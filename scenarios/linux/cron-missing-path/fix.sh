#!/bin/bash
set -e
CUR=$(crontab -l 2>/dev/null || true)
{
  echo 'PATH=/usr/local/bin:/bin:/usr/bin'
  echo "$CUR"
  echo '* * * * * /usr/local/bin/backup.sh >/dev/null 2>&1'
} | awk 'NF && !seen[$0]++' | crontab -
