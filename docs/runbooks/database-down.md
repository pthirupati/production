# PostgreSQL (D3) down or unreachable

## What you will see

Everything failing. This is the one dependency with no graceful degradation, and
that is intentional — serving a page from a stale cache while the database is gone
would show users wrong data rather than an honest error.

## Confirm it

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://fixitlab.in/api/health/ready/
```

**503** with `checks.database.status == "error"`. This is the only condition that
returns 503; everything else degrades to 200.

## What still works

Static assets and the marketing shell, briefly. Nothing that reads data.

## Fix

```bash
# On D3
docker compose -f docker-compose.data.yml ps
docker compose -f docker-compose.data.yml logs --tail=200 database
docker compose -f docker-compose.data.yml restart database pgbouncer
```

If Postgres is up but D2 cannot reach it, check the DigitalOcean cloud firewall —
5432/6432 are restricted to D2's private IP, so a changed IP after a droplet
recreate breaks this silently.

## After a restart

Confirm `shared_buffers` took effect — it is not reloadable and needs a full
container restart, not a `pg_ctl reload`:

```bash
docker compose -f docker-compose.data.yml exec database \
  psql -U postgres -c "SHOW shared_buffers; SHOW effective_cache_size;"
```

Expect `2GB` and `6GB` (audit Z5-12). If they read `256MB`/`768MB` the container is
running the old config and query plans will be poor.

## Known risk

D3 has **no read replica** (ADR 0001, accepted deliberately on cost). The exposure
is restore time, which grows with database size and has **not been drill-tested** —
see audit Z5-8.
