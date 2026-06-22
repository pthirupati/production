#!/usr/bin/env bash
# Restore a FixitLab Postgres backup (PRODUCTION_AUDIT REL-01).
#
# Run this ON the data droplet (D3), in /opt/fixitlab, where the fixitlab_db
# container runs and .env.production lives. It restores a gzipped pg_dump into
# the live database via psql inside the container.
#
# SOURCE (one of):
#   --file PATH        Restore a specific local .sql.gz dump.
#   --latest-local     Restore the newest dump under /var/backups/fixitlab.
#   --latest-spaces    Download the newest dump from DigitalOcean Spaces and
#                      restore it (requires SPACES_* in .env.production + s3cmd
#                      or aws-cli or python boto3). DEFAULT if no source given.
#
# SAFETY: restoring OVERWRITES the current database. This is destructive, so the
# script REQUIRES an explicit confirmation: either run interactively and type
# the database name when prompted, or pass --yes (CONFIRM=<dbname> also works)
# for non-interactive use. Nothing is changed before the confirmation passes.
#
# Usage:
#   ./scripts/restore-pg-backup.sh --latest-spaces
#   ./scripts/restore-pg-backup.sh --file /var/backups/fixitlab/fixitlab-...sql.gz
#   ./scripts/restore-pg-backup.sh --latest-local --yes
#
# Env (read from .env.production, overridable): POSTGRES_USER POSTGRES_DB
#   SPACES_KEY SPACES_SECRET SPACES_BUCKET SPACES_REGION [SPACES_ENDPOINT] [SPACES_PREFIX]
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/fixitlab}"
DB_CONTAINER="${DB_CONTAINER:-fixitlab_db}"
ENV_FILE="${ENV_FILE:-.env.production}"
SOURCE="latest-spaces"
SRC_FILE=""
ASSUME_YES="${ASSUME_YES:-0}"

while [ $# -gt 0 ]; do
  case "$1" in
    --file) SOURCE="file"; SRC_FILE="${2:?--file needs a path}"; shift 2;;
    --latest-local) SOURCE="latest-local"; shift;;
    --latest-spaces) SOURCE="latest-spaces"; shift;;
    --yes|-y) ASSUME_YES=1; shift;;
    -h|--help) sed -n '2,30p' "$0"; exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

_envval() { grep "^$1=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '\r'; }

PGUSER="$(_envval POSTGRES_USER)"; PGDB="$(_envval POSTGRES_DB)"
PGUSER="${PGUSER:-fixitlab}"; PGDB="${PGDB:-fixitlab}"

WORKDIR="$(mktemp -d)"
cleanup() { rm -rf "$WORKDIR"; }
trap cleanup EXIT

resolve_local_latest() {
  ls -1t "$BACKUP_DIR"/fixitlab-*.sql.gz 2>/dev/null | head -1
}

download_latest_spaces() {
  local key secret bucket region endpoint prefix hostpart
  key="$(_envval SPACES_KEY)"; secret="$(_envval SPACES_SECRET)"
  bucket="$(_envval SPACES_BUCKET)"; region="$(_envval SPACES_REGION)"
  endpoint="$(_envval SPACES_ENDPOINT)"; prefix="$(_envval SPACES_PREFIX)"; prefix="${prefix:-fixitlab}"
  if [ -z "$key" ] || [ -z "$secret" ] || [ -z "$bucket" ] || [ -z "$region" ]; then
    echo "[restore] SPACES_* not configured in $ENV_FILE — cannot use --latest-spaces" >&2
    return 3
  fi
  endpoint="${endpoint:-https://${region}.digitaloceanspaces.com}"
  hostpart="${endpoint#https://}"; hostpart="${hostpart#http://}"

  local latest_key="" dest="$WORKDIR/restore.sql.gz"
  if command -v s3cmd >/dev/null 2>&1; then
    latest_key="$(s3cmd --access_key="$key" --secret_key="$secret" --host="$hostpart" \
      --host-bucket="%(bucket)s.${hostpart}" ls -r "s3://${bucket}/${prefix}/" 2>/dev/null \
      | awk '/\.sql\.gz$/ {print $4}' | sort | tail -1)"
    [ -n "$latest_key" ] || { echo "[restore] no .sql.gz found under s3://${bucket}/${prefix}/" >&2; return 4; }
    echo "[restore] downloading $latest_key"
    s3cmd --access_key="$key" --secret_key="$secret" --host="$hostpart" \
      --host-bucket="%(bucket)s.${hostpart}" get "$latest_key" "$dest" >&2
  elif command -v aws >/dev/null 2>&1; then
    latest_key="$(AWS_ACCESS_KEY_ID="$key" AWS_SECRET_ACCESS_KEY="$secret" \
      aws --endpoint-url "$endpoint" --region "$region" s3 ls "s3://${bucket}/${prefix}/" --recursive 2>/dev/null \
      | awk '/\.sql\.gz$/ {print $4}' | sort | tail -1)"
    [ -n "$latest_key" ] || { echo "[restore] no .sql.gz found under s3://${bucket}/${prefix}/" >&2; return 4; }
    echo "[restore] downloading $latest_key"
    AWS_ACCESS_KEY_ID="$key" AWS_SECRET_ACCESS_KEY="$secret" \
      aws --endpoint-url "$endpoint" --region "$region" s3 cp "s3://${bucket}/${latest_key}" "$dest" >&2
  else
    local pybin; pybin="$(command -v python3 || command -v python || true)"
    [ -n "$pybin" ] || { echo "[restore] need s3cmd, aws-cli, or python boto3 to pull from Spaces" >&2; return 3; }
    SPACES_KEY="$key" SPACES_SECRET="$secret" SP_ENDPOINT="$endpoint" SP_REGION="$region" \
    SP_BUCKET="$bucket" SP_PREFIX="$prefix" SP_DEST="$dest" "$pybin" - <<'PY' >&2
import os, sys
try:
    import boto3
except Exception as e:
    print(f"[restore] boto3 unavailable: {e}", file=sys.stderr); sys.exit(3)
s3 = boto3.session.Session().client(
    "s3", region_name=os.environ["SP_REGION"], endpoint_url=os.environ["SP_ENDPOINT"],
    aws_access_key_id=os.environ["SPACES_KEY"], aws_secret_access_key=os.environ["SPACES_SECRET"],
)
bucket, prefix = os.environ["SP_BUCKET"], os.environ["SP_PREFIX"].rstrip("/") + "/"
keys = []
paginator = s3.get_paginator("list_objects_v2")
for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
    for obj in page.get("Contents", []):
        if obj["Key"].endswith(".sql.gz"):
            keys.append(obj["Key"])
if not keys:
    print(f"[restore] no .sql.gz under s3://{bucket}/{prefix}", file=sys.stderr); sys.exit(4)
latest = sorted(keys)[-1]
print(f"[restore] downloading {latest}", file=sys.stderr)
s3.download_file(bucket, latest, os.environ["SP_DEST"])
PY
  fi
  [ -s "$dest" ] || { echo "[restore] download produced no file" >&2; return 4; }
  printf '%s' "$dest"
}

# ── Resolve the dump to restore ──
case "$SOURCE" in
  file)          DUMP="$SRC_FILE";;
  latest-local)  DUMP="$(resolve_local_latest)";;
  latest-spaces) DUMP="$(download_latest_spaces)";;
esac
[ -n "${DUMP:-}" ] && [ -f "$DUMP" ] || { echo "[restore] no dump file resolved (source=$SOURCE)" >&2; exit 1; }

# ── Integrity check before we touch the DB ──
if ! gzip -t "$DUMP" 2>/dev/null; then
  echo "[restore] ERROR: $DUMP failed gzip integrity check" >&2; exit 1
fi
if ! zcat "$DUMP" | head -c 4096 | grep -q "PostgreSQL database dump"; then
  echo "[restore] ERROR: $DUMP does not look like a pg_dump (missing header)" >&2; exit 1
fi

echo "==============================================================="
echo " FixitLab DB RESTORE"
echo "   dump      : $DUMP"
echo "   container : $DB_CONTAINER"
echo "   database  : $PGDB (user $PGUSER)"
echo "   WARNING   : this OVERWRITES the current contents of '$PGDB'."
echo "==============================================================="

# ── Confirmation guard — nothing destructive runs before this passes ──
if [ "$ASSUME_YES" != "1" ]; then
  CONFIRM_INPUT="${CONFIRM:-}"
  if [ -z "$CONFIRM_INPUT" ]; then
    printf "Type the database name (%s) to proceed: " "$PGDB"
    read -r CONFIRM_INPUT
  fi
  if [ "$CONFIRM_INPUT" != "$PGDB" ]; then
    echo "[restore] confirmation did not match '$PGDB' — aborting (no changes made)." >&2
    exit 1
  fi
fi

echo "[restore] restoring into '$PGDB' ..."
# psql restore; ON_ERROR_STOP makes a failed restore non-silent. The dump is a
# plain SQL pg_dump, so pipe it straight into psql inside the container.
zcat "$DUMP" | docker exec -i "$DB_CONTAINER" \
  psql -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$PGDB"

echo "[restore] done. Verify row counts on users / payments / subscriptions before resuming traffic."
