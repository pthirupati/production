#!/usr/bin/env bash
# Check: RDS instance has BackupRetentionPeriod > 0.
set -euo pipefail

DB_ID="${RDS_INSTANCE_ID:-lab-db}"

RETENTION=$(aws rds describe-db-instances \
  --db-instance-identifier "$DB_ID" \
  --query 'DBInstances[0].BackupRetentionPeriod' \
  --output text 2>/dev/null || echo "0")

if [[ "$RETENTION" -lt 1 ]]; then
  echo "FAIL: RDS instance '$DB_ID' has BackupRetentionPeriod=0. Backups are disabled."
  exit 1
fi

echo "PASS: RDS instance '$DB_ID' has automated backups enabled (retention: ${RETENTION} days)."
exit 0
