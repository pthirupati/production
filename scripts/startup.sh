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
python manage.py migrate --noinput

echo "[startup] Collecting static files..."
python manage.py collectstatic --noinput

if [ "${CREATE_SUPERUSER:-0}" = "1" ] && [ -n "${SUPERUSER_EMAIL:-}" ]; then
  python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
u, created = User.objects.get_or_create(
    email='${SUPERUSER_EMAIL}',
    defaults={'username': '${SUPERUSER_USERNAME:-admin}', 'is_staff': True, 'is_superuser': True}
)
if created and '${SUPERUSER_PASSWORD:-}':
    u.set_password('${SUPERUSER_PASSWORD}')
    u.save()
    print('[startup] Superuser created')
else:
    print('[startup] Superuser already exists')
" 2>/dev/null || true
fi

echo "[startup] Starting Daphne on :8000"
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
