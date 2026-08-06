# Redis down or unreachable

## What you will see

Simulation labs losing their state between commands — a learner creates a file, runs
`ls`, and it is gone. It reads as a lab bug, not an infrastructure one, which is
exactly why this was hard to spot before readiness reported Redis (audit Z5-10).

Cached pages get slower but keep working.

## Confirm it

```bash
curl -s https://fixitlab.in/api/health/ready/ | jq '.checks.redis'
```

`status: unavailable`. Note the check is a **set/get round trip**, not a `try/except`
— django-redis with `IGNORE_EXCEPTIONS` swallows the connection error and returns
`None`, so a silent miss is the normal signature of a dead Redis.

## What still works

Most of the site. The cache is configured with `IGNORE_EXCEPTIONS: True`, so reads
fall through to the database instead of 500ing. What degrades:

- simulation lab state (the visible symptom)
- rate limiting **fails open** — throttles stop counting
- per-user WebSocket connection caps fail open

## Fix

Redis runs on **D1 (edge)**, not the app node — verified against
`docker-compose.edge.yml`.

```bash
# On D1
docker compose -f docker-compose.edge.yml restart redis
docker compose -f docker-compose.edge.yml logs --tail=100 redis
```

If Redis is up but D2 cannot reach it, this is a VPC/firewall problem rather than a
Redis one — check that before restarting anything.

## Why it behaves this way

Degrading rather than failing is deliberate: 500ing every cached endpoint because a
cache is unavailable turns a slowdown into an outage. The trade is that security
controls keyed on the cache fail open — acceptable for minutes, not for hours, so
treat a prolonged Redis outage as a security event as well as an availability one.
