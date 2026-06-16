FROM postgres:15-alpine

# Default Postgres port
EXPOSE 5432

# Init scripts (run only on first startup)
COPY init/ /docker-entrypoint-initdb.d/

# Production tuning configuration
COPY postgresql.conf /etc/postgresql/postgresql.conf

CMD ["postgres", "-c", "config_file=/etc/postgresql/postgresql.conf"]

