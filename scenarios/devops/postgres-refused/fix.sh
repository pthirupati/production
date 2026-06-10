#!/bin/bash
set -e
for f in /etc/postgresql/*/main/postgresql.conf; do
  [ -f "$f" ] || continue
  sed -i "s/listen_addresses = 'none'/listen_addresses = '127.0.0.1'/" "$f"
  grep -q "^listen_addresses" "$f" || echo "listen_addresses = '127.0.0.1'" >> "$f"
done
service postgresql restart 2>/dev/null || systemctl restart postgresql 2>/dev/null || true
