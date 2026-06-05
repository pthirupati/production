#!/bin/bash
# Validation: PostgreSQL must accept connections on localhost
FAILED=0

if ! command -v psql >/dev/null 2>&1; then
    echo "FAIL: psql not found"
    exit 1
fi

# Try to start postgres if not running
if ! pgrep -x postgres >/dev/null 2>&1; then
    service postgresql start 2>/dev/null || systemctl start postgresql 2>/dev/null
    sleep 2
fi

if PGPASSWORD=postgres psql -h 127.0.0.1 -U postgres -c "SELECT 1" >/dev/null 2>&1; then
    echo "OK: PostgreSQL accepts connections on 127.0.0.1"
else
    echo "FAIL: Cannot connect to PostgreSQL on 127.0.0.1 — check listen_addresses in postgresql.conf"
    FAILED=1
fi

if grep -q "listen_addresses = 'none'" /etc/postgresql/*/main/postgresql.conf 2>/dev/null; then
    echo "FAIL: Invalid listen_addresses = 'none' still present in postgresql.conf"
    FAILED=1
else
    echo "OK: postgresql.conf listen_addresses looks valid"
fi

[ $FAILED -eq 0 ] && echo "PASS: PostgreSQL is configured correctly" && exit 0
echo "RESULT: Fix postgresql.conf and restart PostgreSQL"
exit 1
