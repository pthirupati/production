#!/usr/bin/env bash
# DR restore drill (audit O8 / Z5-8).
#
# Proves the shipped backup → restore path works on a disposable Postgres
# container — not on production D3. Measures wall-clock restore throughput so
# docs/runbooks/README.md can quote a measured figure instead of "correct on
# inspection".
#
# Steps:
#   1. Start (or reuse) a postgres:16 container named fixitlab_db
#   2. Seed a known table + checksum row
#   3. pg_dump | gzip (same shape as nightly backups)
#   4. Truncate the table, then restore via scripts/restore-pg-backup.sh --file --yes
#   5. Assert row count + content checksum
#
# Usage:
#   ./scripts/dr-restore-drill.sh
#   KEEP_CONTAINER=1 ./scripts/dr-restore-drill.sh   # leave fixitlab_db running
#   SKIP_DOCKER_PULL=1 ./scripts/dr-restore-drill.sh
#
# Requires: docker, python3, gzip. Does NOT need Django or app secrets.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="${PG_IMAGE:-postgres:16}"
CONTAINER="${DB_CONTAINER:-fixitlab_db}"
PGUSER="${POSTGRES_USER:-fixitlab}"
PGDB="${POSTGRES_DB:-fixitlab}"
PGPASS="${POSTGRES_PASSWORD:-fixitlab_drill}"
KEEP_CONTAINER="${KEEP_CONTAINER:-0}"
WORKDIR="$(mktemp -d)"
ENV_FILE="$WORKDIR/.env.production"
DUMP="$WORKDIR/fixitlab-${PGDB}-drill.sql.gz"
SEED_MARK="fixitlab-dr-drill-$(date +%s)"

cleanup() {
  rm -rf "$WORKDIR"
  if [ "$KEEP_CONTAINER" != "1" ] && [ "${STARTED_CONTAINER:-0}" = "1" ]; then
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "[drill] workdir=$WORKDIR container=$CONTAINER"

if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  if [ "${SKIP_DOCKER_PULL:-0}" != "1" ]; then
    docker pull "$IMAGE" >/dev/null
  fi
  docker run -d --name "$CONTAINER" \
    -e POSTGRES_USER="$PGUSER" \
    -e POSTGRES_PASSWORD="$PGPASS" \
    -e POSTGRES_DB="$PGDB" \
    "$IMAGE" >/dev/null
  STARTED_CONTAINER=1
  echo "[drill] started $CONTAINER from $IMAGE"
else
  echo "[drill] reusing existing container $CONTAINER"
fi

# Wait until ready
for _ in $(seq 1 60); do
  if docker exec "$CONTAINER" pg_isready -U "$PGUSER" -d "$PGDB" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker exec "$CONTAINER" pg_isready -U "$PGUSER" -d "$PGDB" >/dev/null

# Seed known data (idempotent recreate)
docker exec -i "$CONTAINER" psql -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$PGDB" <<SQL
DROP TABLE IF EXISTS drill_probe;
CREATE TABLE drill_probe (
  id serial PRIMARY KEY,
  marker text NOT NULL,
  payload text NOT NULL
);
INSERT INTO drill_probe (marker, payload)
SELECT '${SEED_MARK}', md5(i::text || '${SEED_MARK}')
FROM generate_series(1, 500) AS i;
SQL

BEFORE_COUNT="$(docker exec "$CONTAINER" psql -U "$PGUSER" -d "$PGDB" -Atc "SELECT count(*) FROM drill_probe;")"
BEFORE_SUM="$(docker exec "$CONTAINER" psql -U "$PGUSER" -d "$PGDB" -Atc "SELECT coalesce(sum(ascii(substr(payload,1,1))),0) FROM drill_probe;")"
echo "[drill] seeded rows=$BEFORE_COUNT checksum=$BEFORE_SUM marker=$SEED_MARK"

# Dump (same shape as nightly: gzipped plain SQL)
docker exec "$CONTAINER" pg_dump -U "$PGUSER" "$PGDB" | gzip > "$DUMP"
DUMP_BYTES="$(wc -c < "$DUMP" | tr -d ' ')"
echo "[drill] wrote dump $DUMP (${DUMP_BYTES} bytes compressed)"

# Destroy live data so restore must bring it back
docker exec -i "$CONTAINER" psql -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$PGDB" \
  -c "TRUNCATE drill_probe;"
GONE="$(docker exec "$CONTAINER" psql -U "$PGUSER" -d "$PGDB" -Atc "SELECT count(*) FROM drill_probe;")"
[ "$GONE" = "0" ] || { echo "[drill] truncate failed (count=$GONE)" >&2; exit 1; }

# Env file for restore-pg-backup.sh defaults
cat > "$ENV_FILE" <<EOF
POSTGRES_USER=$PGUSER
POSTGRES_DB=$PGDB
EOF

START_S="$(python3 -c 'import time; print(time.time())')"
DB_CONTAINER="$CONTAINER" ENV_FILE="$ENV_FILE" \
  "$ROOT/scripts/restore-pg-backup.sh" --file "$DUMP" --yes
END_S="$(python3 -c 'import time; print(time.time())')"
ELAPSED="$(python3 - <<PY
print(f"{float('${END_S}') - float('${START_S}'):.3f}")
PY
)"

AFTER_COUNT="$(docker exec "$CONTAINER" psql -U "$PGUSER" -d "$PGDB" -Atc "SELECT count(*) FROM drill_probe;")"
AFTER_SUM="$(docker exec "$CONTAINER" psql -U "$PGUSER" -d "$PGDB" -Atc "SELECT coalesce(sum(ascii(substr(payload,1,1))),0) FROM drill_probe;")"
MARKER_OK="$(docker exec "$CONTAINER" psql -U "$PGUSER" -d "$PGDB" -Atc "SELECT count(*) FROM drill_probe WHERE marker='${SEED_MARK}';")"

echo "[drill] restored rows=$AFTER_COUNT checksum=$AFTER_SUM marker_rows=$MARKER_OK elapsed_s=$ELAPSED"

if [ "$AFTER_COUNT" != "$BEFORE_COUNT" ] || [ "$AFTER_SUM" != "$BEFORE_SUM" ] || [ "$MARKER_OK" != "$BEFORE_COUNT" ]; then
  echo "[drill] FAIL: restored data does not match seed" >&2
  exit 1
fi

# Uncompressed size estimate for throughput note
UNCOMP_BYTES="$(DUMP_PATH="$DUMP" python3 - <<'PY'
import gzip, os
with gzip.open(os.environ["DUMP_PATH"], "rb") as fh:
    n = 0
    while True:
        chunk = fh.read(1024 * 1024)
        if not chunk:
            break
        n += len(chunk)
print(n)
PY
)"
THROUGHPUT="$(python3 - <<PY
elapsed=float("${ELAPSED}")
nbytes=int("${UNCOMP_BYTES}")
print(f"{(nbytes/1e6)/elapsed:.2f}" if elapsed > 0 else "n/a")
PY
)"
echo "[drill] PASS uncompressed_bytes=$UNCOMP_BYTES throughput_MBps=$THROUGHPUT"
