# celery_beat running but not scheduling

## What you will see

Nothing, at first — which is the problem. Then, over hours: expired labs not
cleaned up, orphaned containers holding capacity, retention sweeps not running,
disk creeping up on D4.

## Confirm it

The container healthcheck now catches this (audit Z5-15):

```bash
docker compose -f docker-compose.app.yml ps celery_beat     # look for (unhealthy)
docker compose -f docker-compose.app.yml exec celery_beat \
  sh -c 'echo $(( $(date +%s) - $(stat -c %Y /tmp/celerybeat-heartbeat) ))'
```

Anything over 200 seconds means beat has stopped scheduling. The healthcheck writes
that file every minute via the `beat_heartbeat` task.

## What still works

Everything user-facing. Workers keep processing whatever is queued; only *scheduling*
has stopped, so the damage is cumulative rather than immediate.

## Fix

```bash
docker compose -f docker-compose.app.yml restart celery_beat
```

Then confirm the heartbeat is advancing again, and check what was missed while it
was wedged — particularly orphaned containers on D4.

## Why the healthcheck is shaped this way

The pidfile check alone proved the process existed, not that it was working. The
obvious alternative — watching the mtime of beat's schedule file — was measured and
**does not work**: with the next task an hour away the mtime does not advance, so it
would report a healthy beat as dead and restart-loop it. The heartbeat proves
liveness by beat doing its actual job.
