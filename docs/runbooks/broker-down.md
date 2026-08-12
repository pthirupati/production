# Broker (RabbitMQ) down

## What you will see

Lab starts returning 500. Nothing scheduled running — no expiry cleanup, no orphan
reclaim, no retention sweep. Outbound email stops for non-critical messages.

## Confirm it

```bash
curl -s https://fixitlab.in/api/health/ready/ | jq '.checks.broker'
```

## What still works

Browsing, auth, payments, and **OTP / password-reset email** — those are sent from
the web process in a daemon thread precisely so signing in does not depend on the
broker (ADR 0005).

## The cascade to watch for

This is the failure with a tail. `provision_docker_lab.delay()` is **unguarded**
(`public_api/views.py:954`), so when the broker is down:

1. the `LabSession` row is created,
2. `.delay()` raises and the user gets a 500,
3. the row stays in `PROVISIONING` and **counts against the global capacity cap**,
4. the beat task that clears stuck sessions **also cannot run**.

So capacity fills with rows nobody can start and nothing can clear. After restoring
the broker, check for and clear them:

```bash
docker compose -f docker-compose.app.yml exec backend python manage.py shell -c "
from apps.labs.models import LabSession
from django.utils import timezone
from datetime import timedelta
stuck = LabSession.objects.filter(status='PROVISIONING', started_at__lt=timezone.now()-timedelta(minutes=15))
print('stuck:', stuck.count())
stuck.update(status='FAILED')
"
```

## Fix

RabbitMQ runs on **D1 (edge)**; the workers run on **D2 (app)** — verified
against `docker-compose.edge.yml` and `docker-compose.app.yml`.

```bash
# On D1 — the broker itself
docker compose -f docker-compose.edge.yml restart rabbitmq

# On D2 — the consumers
docker compose -f docker-compose.app.yml restart celery_worker celery_beat
```

Restart the workers too — they do not always recover a dropped connection cleanly.

## Known gap

The unguarded `.delay()` is recorded in audit Z5-18 and is **not yet fixed**. Until
it is, a broker outage costs capacity as well as availability.
