#!/usr/bin/env bash
# Install a daily pg_dump backup cron on the D3 Data droplet.
#
# Creates /usr/local/bin/fixitlab-pg-backup.sh (runs pg_dump inside the
# fixitlab_db container, gzip, 7-day LOCAL retention under /var/backups/fixitlab)
# and a /etc/cron.d/fixitlab-pg-backup entry that runs daily at 02:30 server time.
#
# PRODUCTION_AUDIT REL-01: the generated backup script ALSO integrity-checks each
# dump, uploads it OFF-SITE to DigitalOcean Spaces (S3-compatible), and writes a
# backup heartbeat (local file + Redis key) on success. The off-site upload and
# Redis heartbeat are GATED on config read from .env.production on D3
# (SPACES_KEY / SPACES_SECRET / SPACES_BUCKET / SPACES_REGION for Spaces;
# REDIS_HOST for the heartbeat) and skip cleanly with a log line when absent —
# so this installer needs NO new env and the green deploy is unchanged. The
# owner sets the SPACES_* secrets in Vault → .env.production later.
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
#
# PRODUCTION_AUDIT REL-01: after writing the local dump it (a) integrity-checks
# the gzip + the pg_dump SQL header, (b) uploads OFF-SITE to DigitalOcean Spaces
# (S3-compatible) when SPACES_* are present in .env.production — s3cmd → aws-cli
# → python boto3, whichever is available — and (c) records a backup heartbeat
# (local file + a Redis key the app/monitoring can read) on success. Every
# off-site/heartbeat step is GATED on its config being present and skips cleanly
# with a log line when absent, so a node without Spaces/Redis configured keeps
# producing local backups exactly as before.
read -r -d '' BACKUP_SCRIPT <<'SCRIPT' || true
#!/usr/bin/env bash
set -euo pipefail
BACKUP_DIR=/var/backups/fixitlab
RETENTION_DAYS=__RETENTION__
HEARTBEAT_FILE="$BACKUP_DIR/last_success_epoch"
HEARTBEAT_REDIS_KEY="fixitlab:backup:last_success_epoch"
mkdir -p "$BACKUP_DIR"
cd /opt/fixitlab

_envval() { grep "^$1=" .env.production 2>/dev/null | head -1 | cut -d= -f2- | tr -d '\r'; }

PGUSER="$(_envval POSTGRES_USER)"; PGDB="$(_envval POSTGRES_DB)"
PGUSER="${PGUSER:-fixitlab}"; PGDB="${PGDB:-fixitlab}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/fixitlab-${PGDB}-${STAMP}.sql.gz"

docker exec fixitlab_db pg_dump -U "$PGUSER" "$PGDB" | gzip > "$OUT"
echo "[pg-backup] wrote $OUT"

# ── Integrity check: a corrupt/empty dump must NOT count as a success ──
if ! gzip -t "$OUT" 2>/dev/null; then
  echo "[pg-backup] ERROR: gzip integrity check failed for $OUT" >&2
  exit 1
fi
if ! zcat "$OUT" | head -c 4096 | grep -q "PostgreSQL database dump"; then
  echo "[pg-backup] ERROR: $OUT does not look like a pg_dump (missing header)" >&2
  exit 1
fi

# ── Off-site upload to DigitalOcean Spaces (S3-compatible), GATED on SPACES_* ──
SPACES_KEY="$(_envval SPACES_KEY)"
SPACES_SECRET="$(_envval SPACES_SECRET)"
SPACES_BUCKET="$(_envval SPACES_BUCKET)"
SPACES_REGION="$(_envval SPACES_REGION)"
SPACES_ENDPOINT="$(_envval SPACES_ENDPOINT)"
SPACES_PREFIX="$(_envval SPACES_PREFIX)"; SPACES_PREFIX="${SPACES_PREFIX:-fixitlab}"
if [ -n "$SPACES_KEY" ] && [ -n "$SPACES_SECRET" ] && [ -n "$SPACES_BUCKET" ] && [ -n "$SPACES_REGION" ]; then
  ENDPOINT="${SPACES_ENDPOINT:-https://${SPACES_REGION}.digitaloceanspaces.com}"
  HOSTPART="${ENDPOINT#https://}"; HOSTPART="${HOSTPART#http://}"
  KEYPATH="${SPACES_PREFIX}/$(date +%Y/%m/%d)/$(basename "$OUT")"
  UPLOADED=0
  if command -v s3cmd >/dev/null 2>&1; then
    if s3cmd --access_key="$SPACES_KEY" --secret_key="$SPACES_SECRET" \
        --host="$HOSTPART" --host-bucket="%(bucket)s.${HOSTPART}" \
        put "$OUT" "s3://${SPACES_BUCKET}/${KEYPATH}"; then
      UPLOADED=1
    fi
  fi
  if [ "$UPLOADED" -eq 0 ] && command -v aws >/dev/null 2>&1; then
    if AWS_ACCESS_KEY_ID="$SPACES_KEY" AWS_SECRET_ACCESS_KEY="$SPACES_SECRET" \
        aws --endpoint-url "$ENDPOINT" --region "$SPACES_REGION" \
        s3 cp "$OUT" "s3://${SPACES_BUCKET}/${KEYPATH}"; then
      UPLOADED=1
    fi
  fi
  if [ "$UPLOADED" -eq 0 ]; then
    # Last resort: small inline boto3 uploader (boto3 ships in the backend image).
    PYBIN="$(command -v python3 || command -v python || true)"
    if [ -n "$PYBIN" ]; then
      if SPACES_KEY="$SPACES_KEY" SPACES_SECRET="$SPACES_SECRET" \
         SP_ENDPOINT="$ENDPOINT" SP_REGION="$SPACES_REGION" \
         SP_BUCKET="$SPACES_BUCKET" SP_KEY="$KEYPATH" SP_FILE="$OUT" \
         "$PYBIN" - <<'PY'
import os, sys
try:
    import boto3
except Exception as e:
    print(f"[pg-backup] boto3 unavailable for upload: {e}", file=sys.stderr); sys.exit(3)
s3 = boto3.session.Session().client(
    "s3", region_name=os.environ["SP_REGION"], endpoint_url=os.environ["SP_ENDPOINT"],
    aws_access_key_id=os.environ["SPACES_KEY"], aws_secret_access_key=os.environ["SPACES_SECRET"],
)
s3.upload_file(os.environ["SP_FILE"], os.environ["SP_BUCKET"], os.environ["SP_KEY"])
print(f"[pg-backup] uploaded via boto3 to s3://{os.environ['SP_BUCKET']}/{os.environ['SP_KEY']}")
PY
      then UPLOADED=1; fi
    fi
  fi
  if [ "$UPLOADED" -eq 1 ]; then
    echo "[pg-backup] off-site copy ok: s3://${SPACES_BUCKET}/${KEYPATH}"
  else
    echo "[pg-backup] WARNING: off-site upload FAILED (no s3cmd/aws/boto3 succeeded) — local backup kept" >&2
  fi
else
  echo "[pg-backup] SPACES_* not set — skipping off-site upload (local backup only)"
fi

# ── Backup heartbeat (dead-man's-switch). Always write the local file; also push
#    to Redis when REDIS_HOST is configured so the app (on another droplet) can
#    read it. Redis push is best-effort and never fails the backup. ──
NOW_EPOCH="$(date +%s)"
printf '%s\n' "$NOW_EPOCH" > "$HEARTBEAT_FILE" || true
REDIS_HOST="$(_envval REDIS_HOST)"
REDIS_PORT="$(_envval REDIS_PORT)"; REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASSWORD="$(_envval REDIS_PASSWORD)"
if [ -n "$REDIS_HOST" ] && command -v redis-cli >/dev/null 2>&1; then
  if [ -n "$REDIS_PASSWORD" ]; then
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" -n 1 \
      SET "$HEARTBEAT_REDIS_KEY" "$NOW_EPOCH" >/dev/null 2>&1 \
      && echo "[pg-backup] heartbeat -> redis ($REDIS_HOST db1)" \
      || echo "[pg-backup] WARNING: heartbeat redis SET failed (non-fatal)" >&2
  else
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n 1 \
      SET "$HEARTBEAT_REDIS_KEY" "$NOW_EPOCH" >/dev/null 2>&1 \
      && echo "[pg-backup] heartbeat -> redis ($REDIS_HOST db1)" \
      || echo "[pg-backup] WARNING: heartbeat redis SET failed (non-fatal)" >&2
  fi
else
  echo "[pg-backup] heartbeat written to $HEARTBEAT_FILE (redis-cli/REDIS_HOST unavailable)"
fi

# Retention (local only — off-site retention is managed by a Spaces lifecycle rule)
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
