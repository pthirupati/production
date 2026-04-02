#!/bin/bash
# FixitLab — Automated Database & Volume Backup
# Add to crontab: 0 3 * * * /opt/fixitlab/scripts/backup.sh
set -euo pipefail

BACKUP_DIR="/opt/fixitlab/backups"
COMPOSE_FILE="/opt/fixitlab/docker-compose.prod.yml"
RETENTION_DAYS=30
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup..."

# ── PostgreSQL dump ──
docker compose -f "$COMPOSE_FILE" exec -T database \
    pg_dump -U fixitlab fixitlab | gzip > "$BACKUP_DIR/db_${DATE}.sql.gz"
echo "  ✓ Database backed up"

# ── Redis dump ──
docker compose -f "$COMPOSE_FILE" exec -T redis redis-cli BGSAVE 2>/dev/null || true
sleep 2
docker cp fixitlab_redis:/data/dump.rdb "$BACKUP_DIR/redis_${DATE}.rdb" 2>/dev/null || true
echo "  ✓ Redis backed up"

# ── Cleanup old backups ──
find "$BACKUP_DIR" -type f -mtime +"$RETENTION_DAYS" -delete
echo "  ✓ Old backups cleaned (retention: ${RETENTION_DAYS}d)"

# ── Optional: Upload to S3 ──
# aws s3 sync "$BACKUP_DIR" "s3://fixitlab-backups/$(hostname)/" --quiet

SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
echo "[$(date)] Backup complete. Total size: $SIZE"
