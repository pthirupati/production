FROM postgres:15-alpine

# Default Postgres port
EXPOSE 5432

# Init scripts (run only on first startup)
COPY init/ /docker-entrypoint-initdb.d/

