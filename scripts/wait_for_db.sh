#!/bin/sh
set -e

echo "⏳ Waiting for PostgreSQL..."

until pg_isready -h database -p 5432 -U fixitlab; do
  sleep 2
done

echo "✅ PostgreSQL is ready"

