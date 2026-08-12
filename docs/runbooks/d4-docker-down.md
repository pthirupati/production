# D4 lab host / Docker daemon down

## What you will see

Container-mode labs failing to start. **Simulation labs are unaffected** — measured,
only 92 of 6,973 active scenarios (1.3%) route to D4, so most of the catalog keeps
working and this can go unnoticed.

## Confirm it

```bash
curl -s https://fixitlab.in/api/health/ready/ | jq '.checks.docker'
```

Note: on D2 this legitimately reports `not_applicable` — the backend runs on the app
node and the daemon lives on the lab host. Check from D4, or check the daemon
directly:

```bash
# On D4
systemctl status docker
docker ps --filter label=fixitlab.session_id
```

## What still works

Everything except the 92 container-mode scenarios — the flagship "real machine"
lab for each technology. Losing those is a credibility problem more than a capacity
one.

## Fix

```bash
# On D4
systemctl restart docker
```

Then reclaim anything orphaned by the outage. The cleanup is session-aware: a
container whose `fixitlab.session_id` has no live `LabSession` row is removed
regardless of age (audit Z5-11), so it recovers on the next hourly sweep — or force
it:

```bash
docker compose -f docker-compose.app.yml exec backend python manage.py shell -c "
from celery_app.tasks import cleanup_orphaned_containers
print(cleanup_orphaned_containers())
"
```

## Do not

Lower the 7200-second age floor in `cleanup_expired` to reclaim faster. A lab can
legitimately reach 120 minutes via two 30-minute extensions on a 60-minute maximum,
so a lower floor kills **live** labs. This was measured (audit Z5-11); the
session-aware rule is the correct way to reclaim quickly.
