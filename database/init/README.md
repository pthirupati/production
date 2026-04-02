# Database Initialization

Files in this directory are executed **only once**
when the PostgreSQL container is created for the first time.

## What happens here?
- PostgreSQL extensions are enabled
- No tables are created here (Django migrations handle that)

## Important
- If you delete the Docker volume, this script will run again
- Normal container restarts do NOT re-run this

