#!/bin/sh
set -e

echo "🚀 FixitLab startup initiated"

# -------------------------
# Wait for DB
# -------------------------
echo "⏳ Waiting for PostgreSQL..."
until pg_isready -h database -p 5432 -U fixitlab 2>/dev/null; do
  sleep 2
done
echo "✅ PostgreSQL is ready"

# -------------------------
# Django setup
# -------------------------
cd /app

echo "📦 Checking for pending migrations"
python manage.py showmigrations --plan 2>/dev/null | grep "\\[ \\]" | head -5 || echo "  All migrations applied"

echo "📦 Running migrations"
python manage.py migrate --noinput 2>&1 || {
  echo "⚠️  Migration failed, faking conflicting app migrations..."
  # Tables may exist from --run-syncdb before migrations were generated
  for app in labs question_bank notifications; do
    python manage.py migrate "$app" --fake --noinput 2>&1 || true
  done
  echo "🔄  Re-running remaining migrations..."
  python manage.py migrate --noinput 2>&1 || {
    echo "⚠️  Still failing, running --fake-initial..."
    python manage.py migrate --fake-initial --noinput
  }
}

echo "🔄 Syncing DB schema (catch any missing columns)"
python manage.py migrate --run-syncdb --noinput 2>/dev/null || true

# Ensure phone_number column exists (handles edge case where migration ran before field was added)
python -c "
from django.db import connection
cursor = connection.cursor()
cursor.execute(\"SELECT column_name FROM information_schema.columns WHERE table_name = 'accounts_profile'\")
cols = [r[0] for r in cursor.fetchall()]
if 'phone_number' not in cols:
    cursor.execute('ALTER TABLE accounts_profile ADD COLUMN phone_number varchar(17) NULL')
    print('  Added missing phone_number column')
" 2>/dev/null || true

echo "🎨 Collecting static files"
python manage.py collectstatic --noinput

echo "👤 Ensuring superuser exists"
PYTHONPATH=/app python /scripts/create_superuser.py

echo "🌱 Seeding initial data"
PYTHONPATH=/app python /scripts/seed_data.py

# -------------------------
# Create Docker network for labs
# -------------------------
echo "🐳 Ensuring lab Docker network exists"
docker network create fixitlab_labs 2>/dev/null || true

# -------------------------
# Start Daphne (ASGI — supports HTTP + WebSocket)
# -------------------------
echo "🔥 Starting Daphne ASGI server"
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application

