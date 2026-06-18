#!/bin/bash
# Check that integrity investigation and restoration was completed
# Verify integrity report was written
if [ ! -f /tmp/integrity-report.txt ]; then
  echo "FAIL: /tmp/integrity-report.txt not found — document your investigation findings"
  exit 1
fi
REPORT_SIZE=$(wc -c < /tmp/integrity-report.txt)
if [ "$REPORT_SIZE" -lt 50 ]; then
  echo "FAIL: integrity report is too short ($REPORT_SIZE bytes) — provide detailed findings"
  exit 1
fi
# Check that /usr/bin/find checksum matches the backup (if backup exists)
if [ -f /var/backup/find.backup ]; then
  FIND_CKSUM=$(md5sum /usr/bin/find 2>/dev/null | awk '{print $1}')
  BACKUP_CKSUM=$(md5sum /var/backup/find.backup 2>/dev/null | awk '{print $1}')
  if [ "$FIND_CKSUM" != "$BACKUP_CKSUM" ]; then
    echo "FAIL: /usr/bin/find still differs from backup — restore with: cp /var/backup/find.backup /usr/bin/find"
    exit 1
  fi
fi
# Check that AIDE database was re-initialized (db newer than 1 hour)
if [ -f /var/lib/aide/aide.db ]; then
  DB_AGE=$(( ($(date +%s) - $(stat -c %Y /var/lib/aide/aide.db 2>/dev/null || echo 0)) / 60 ))
  if [ "$DB_AGE" -gt 60 ]; then
    echo "FAIL: AIDE database is $DB_AGE minutes old — re-initialize with: aide --init && mv /var/lib/aide/aide.db.new /var/lib/aide/aide.db"
    exit 1
  fi
fi
echo "OK: integrity investigation complete, files restored, and report written"
exit 0
