#!/bin/bash
set -e
chmod 755 /opt/backup.sh
CUR=$(crontab -l 2>/dev/null || true)
{
  echo "$CUR"
  echo '*/5 * * * * /opt/backup.sh >/dev/null 2>&1'
} | awk 'NF && !seen[$0]++' | crontab -
