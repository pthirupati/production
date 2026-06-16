#!/bin/sh
# FixitLab backend container entrypoint — migrate, collectstatic, run ASGI server
set -e

cd /app

echo "[startup] Waiting for PostgreSQL..."
until pg_isready -h "${POSTGRES_HOST:-database}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER:-fixitlab}" >/dev/null 2>&1; do
  sleep 2
done
echo "[startup] Database is ready"

echo "[startup] Running migrations..."
python - <<'PY'
import fcntl
import subprocess
import sys

lock_path = "/tmp/fixitlab-migrate.lock"
with open(lock_path, "w") as lock_file:
    fcntl.flock(lock_file, fcntl.LOCK_EX)
    subprocess.check_call([sys.executable, "manage.py", "migrate", "--noinput"])
PY

echo "[startup] Collecting static files..."
python manage.py collectstatic --noinput

if [ "${CREATE_SUPERUSER:-0}" = "1" ] && [ -n "${SUPERUSER_EMAIL:-}" ] && [ -n "${SUPERUSER_PASSWORD:-}" ]; then
  echo "[startup] Ensuring superuser..."
  python /scripts/create_superuser.py 2>/dev/null || true
fi

# Ensure argon2 password hasher is available (required for registration)
python -c "import argon2" 2>/dev/null || pip install -q argon2-cffi

WORKERS=${UVICORN_WORKERS:-4}
echo "[startup] Starting uvicorn with ${WORKERS} workers on :8000"
exec uvicorn config.asgi:application \
  --host 0.0.0.0 \
  --port 8000 \
  --workers "${WORKERS}" \
  --loop uvloop \
  --http h11 \
  --timeout-keep-alive 75 \
  --log-level warning
