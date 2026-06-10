#!/bin/bash
set -e
for f in /etc/postgresql/*/main/postgresql.conf; do
  [ -f "$f" ] || continue
  sed -i "/^listen_addresses/d" "$f"
  echo "listen_addresses = '127.0.0.1'" >> "$f"
done
service postgresql start 2>/dev/null || pg_ctlcluster 14 main start 2>/dev/null || true
sleep 2
