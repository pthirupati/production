#!/bin/bash
set -e
for f in /etc/postgresql/*/main/postgresql.conf; do
  [ -f "$f" ] || continue
  sed -i "/^listen_addresses/d" "$f"
  sed -i "/^#listen_addresses/d" "$f"
  echo "listen_addresses = '127.0.0.1'" >> "$f"
done
for f in /etc/postgresql/*/main/pg_hba.conf; do
  [ -f "$f" ] || continue
  grep -q '127.0.0.1/32' "$f" || echo "host all all 127.0.0.1/32 trust" >> "$f"
  grep -q '^local.*all.*all.*trust' "$f" || echo "local all all trust" >> "$f"
done
CLUSTER=$(pg_lsclusters -h 2>/dev/null | awk 'NR==1 {print $1}')
VERSION="${CLUSTER:-14}"
service postgresql restart 2>/dev/null || \
  pg_ctlcluster "$VERSION" main restart 2>/dev/null || \
  pg_ctlcluster "$VERSION" main start 2>/dev/null || true
sleep 3
