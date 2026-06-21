#!/usr/bin/env bash
# Install a daily pg_dump backup cron on the D3 Data droplet.
#
# Creates /usr/local/bin/fixitlab-pg-backup.sh (runs pg_dump inside the
# fixitlab_db container, gzip, 7-day retention under /var/backups/fixitlab) and a
# /etc/cron.d/fixitlab-pg-backup entry that runs daily at 02:30 server time.
#
# Idempotent (rewrites the script + cron each run). DRY_RUN=1 prints the ssh
# commands and the rendered backup script without executing.
#
# Required env: EDGE_PUBLIC_IP DATA_PRIVATE_IP PROD_SSH_KEY
# Optional    : BACKUP_HOUR (default 2) BACKUP_MIN (default 30) BACKUP_RETENTION_DAYS (default 7)
set -euo pipefail

DRY_RUN="${DRY_RUN:-0}"
EDGE_PUBLIC_IP="${EDGE_PUBLIC_IP:?EDGE_PUBLIC_IP required}"
DATA_PRIVATE_IP="${DATA_PRIVATE_IP:?DATA_PRIVATE_IP required}"
BACKUP_HOUR="${BACKUP_HOUR:-2}"
BACKUP_MIN="${BACKUP_MIN:-30}"
RETENTION="${BACKUP_RETENTION_DAYS:-7}"

_is_true() { case "${1:-}" in 1|true|TRUE|yes|on) return 0;; *) return 1;; esac; }

KEY_FILE=""
if [ -n "${PROD_SSH_KEY:-}" ] && ! _is_true "$DRY_RUN"; then
  KEY_FILE="$(mktemp)"; printf '%s\n' "$PROD_SSH_KEY" | tr -d '\r' > "$KEY_FILE"; chmod 600 "$KEY_FILE"
  trap 'rm -f "$KEY_FILE"' EXIT
fi

# The backup script that will live on D3. Uses the .env.production on the node
# for POSTGRES_USER/DB; pg_dump runs inside the db container (no creds on cmdline).
read -r -d '' BACKUP_SCRIPT <<'SCRIPT' || true
#!/usr/bin/env bash
set -euo pipefail
BACKUP_DIR=/var/backups/fixitlab
RETENTION_DAYS=__RETENTION__
mkdir -p "$BACKUP_DIR"
cd /opt/fixitlab
PGUSER="$(grep '^POSTGRES_USER=' .env.production | cut -d= -f2- | tr -d '\r')"
PGDB="$(grep '^POSTGRES_DB=' .env.production | cut -d= -f2- | tr -d '\r')"
PGUSER="${PGUSER:-fixitlab}"; PGDB="${PGDB:-fixitlab}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/fixitlab-${PGDB}-${STAMP}.sql.gz"
docker exec fixitlab_db pg_dump -U "$PGUSER" "$PGDB" | gzip > "$OUT"
echo "[pg-backup] wrote $OUT"
# Retention
find "$BACKUP_DIR" -name 'fixitlab-*.sql.gz' -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true
SCRIPT
BACKUP_SCRIPT="${BACKUP_SCRIPT//__RETENTION__/$RETENTION}"

CRON_LINE="${BACKUP_MIN} ${BACKUP_HOUR} * * * root /usr/local/bin/fixitlab-pg-backup.sh >> /var/log/fixitlab-pg-backup.log 2>&1"

install_remote() {
  local opts=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes)
  local jopts="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -o ConnectTimeout=10"
  [ -n "$KEY_FILE" ] && { opts+=(-i "$KEY_FILE" -o IdentitiesOnly=yes); jopts="$jopts -i $KEY_FILE -o IdentitiesOnly=yes"; }
  opts+=(-o "ProxyCommand=ssh $jopts -W %h:%p root@${EDGE_PUBLIC_IP}")
  if _is_true "$DRY_RUN"; then
    echo "DRY_RUN ssh -J root@${EDGE_PUBLIC_IP} root@${DATA_PRIVATE_IP} 'install /usr/local/bin/fixitlab-pg-backup.sh + /etc/cron.d/fixitlab-pg-backup'"
    echo "----- rendered /usr/local/bin/fixitlab-pg-backup.sh -----"
    printf '%s\n' "$BACKUP_SCRIPT"
    echo "----- rendered /etc/cron.d/fixitlab-pg-backup -----"
    printf '%s\n' "$CRON_LINE"
    return 0
  fi
  ssh "${opts[@]}" "root@${DATA_PRIVATE_IP}" "bash -s" <<EOF
set -e
cat > /usr/local/bin/fixitlab-pg-backup.sh <<'BSCRIPT'
${BACKUP_SCRIPT}
BSCRIPT
chmod +x /usr/local/bin/fixitlab-pg-backup.sh
cat > /etc/cron.d/fixitlab-pg-backup <<'BCRON'
${CRON_LINE}
BCRON
chmod 644 /etc/cron.d/fixitlab-pg-backup
echo "[pg-backup] installed daily backup at ${BACKUP_HOUR}:${BACKUP_MIN} (retention ${RETENTION}d)"
EOF
}

echo "=== FixitLab pg backup cron on D3 (dry_run=$DRY_RUN) ==="
install_remote
echo "=== pg backup cron done ==="
