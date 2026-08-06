# Runbooks

Audit Z5-18: grepping `docs/` and `scripts/` for "runbook" returned only
architecture and audit documents. During an incident, the reasoning that lives in
one person's head is not available — including to that person at 3am.

Each runbook covers **one dependency failing**, and follows the same shape:

1. **What you will see** — the symptom as it actually presents, not the cause.
   You do not start an incident knowing which dependency broke.
2. **Confirm it** — a command that distinguishes this from the things it looks like.
3. **What still works** — so you can tell users something true.
4. **Fix**.
5. **Why it behaves this way** — the design decision, linked to its ADR where one
   exists, so the next person does not "fix" the deliberate part.

Everything here was verified against the code in August 2026. Where a behaviour is
believed but unverified it says so — a runbook that is confidently wrong is worse
than no runbook, because it is followed under pressure.

| Runbook | Symptom you would notice first |
|---|---|
| [Vault sealed](vault-sealed.md) | Auth and interview endpoints 500 |
| [Redis down](redis-down.md) | Simulation labs reset between commands |
| [Broker down](broker-down.md) | Lab starts 500; scheduled cleanup stops |
| [celery_beat wedged](beat-wedged.md) | Nothing cleaned up; disk and capacity creep |
| [Database down](database-down.md) | Everything 503 |
| [D4 / Docker daemon down](d4-docker-down.md) | Only container-mode labs fail |

## First 60 seconds, whatever the symptom

```bash
curl -s https://fixitlab.in/api/health/ready/ | jq .
```

That endpoint names the failing dependency directly (audit Z5-10): `database`,
`vault`, `redis`, `broker`, `docker`. It returns **200 with `status: degraded`** for
anything the platform is designed to survive, and **503** only when the database is
gone — so a 200 does not mean "fine", it means "still serving". Read `checks`.

## Disaster recovery targets (RTO / RPO)

These numbers are **derived from the backup cadence that is actually configured**,
not from what we would like them to be. Publishing an RPO shorter than the real
backup interval is worse than publishing none, because it is believed during an
incident. Where a target is unverified it says so.

The only stateful tier is **D3 (Postgres)**. Everything else is rebuildable from
the repo: D1/D2/D4 hold no durable customer data, so their recovery time is a
redeploy, not a restore.

| Scenario | RPO (data loss) | RTO (time to serving) | Verified? |
|---|---|---|---|
| App/edge/labs droplet lost (D1/D2/D4) | **0** — no durable state | ~30 min (`rollback.yml` `timeout-minutes: 30`) + Vault unseal if D1 | Deploy path runs continuously; full-droplet rebuild not drilled |
| Postgres container/data corrupted, D3 alive | **up to 24 h** | **~17 s** for a 344 MB dump — 13.7 s restore + ~3 s container start — scaling at **~25 MB/s of uncompressed dump** | ✅ drilled monthly ([`dr-restore-drill.yml`](../../.github/workflows/dr-restore-drill.yml)) — read the caveats below before quoting it |
| D3 droplet lost entirely | **total loss unless off-site is on** — see below | Unbounded | ❌ never drilled |

### Why RPO is 24 hours, not less

`scripts/ci-pg-backup-cron.sh` installs **one** `pg_dump` per day at **02:30**
server time (`BACKUP_HOUR=2`, `BACKUP_MIN=30`), 7-day local retention. There is no
WAL archiving and no PITR. A failure at 02:29 therefore loses **~24 hours** of
writes — payments, subscriptions, and lab progress included. That is the RPO. It
cannot be improved by documentation, only by raising the cron frequency or adding
WAL shipping.

`ALERT_BACKUP_MAX_AGE_HOURS` defaults to `26.0` (`backend/config/settings.py`) —
deliberately one cycle plus headroom, so a single missed run pages rather than
silently extending the RPO to 48 h.

### The off-site gap that changes the D3 number

Off-site upload to Spaces is **gated and off by default**: `env.production.example`
ships `BACKUP_OFFSITE_ENABLED=0`, and the generated backup script skips the upload
entirely when it is unset. Until an owner sets that flag and the `SPACES_*` secrets,
**every backup lives on the same droplet as the database it protects**.

That means: container-level corruption is recoverable; **losing D3 loses the data
and the backups together**. The stated 24 h RPO only holds for the first case. Treat
enabling off-site as the single highest-value DR action outstanding.

### Where the restore RTO comes from, and what it is not

D3 has no read replica — accepted deliberately on cost in
[ADR 0001](../adr/0001-four-droplet-topology.md), which names restore time as the
known exposure. The restore number above is now **measured**, by
`scripts/dr-restore-drill.sh` (audit Z5-8): it builds the production database
image, applies the real Django migrations, writes known rows, dumps with the
shipped backup logic, restores with `scripts/restore-pg-backup.sh`, and asserts
every table's row count and a content checksum come back. A 441 MB database →
344 MB uncompressed dump restored in **13.7 s**. Two runs at different scales
agree closely — 27.1 MB/s at 114 MB, 25.1 MB/s at 344 MB — so **~25 MB/s** is the
figure to extrapolate from, and it is roughly flat with size.

Three caveats, all load-bearing:

1. **It is synthetic data, and not on D3.** The figure comes from the drill host
   (CI runner / dev laptop), not from an s-2vcpu-8gb droplet with network block
   storage. Treat **~25 MB/s as an upper bound** and scale from the *uncompressed*
   dump size, which is ~3× the `.sql.gz` on disk: a 5 GB uncompressed dump is
   ~3.5 minutes, not seconds. Quote the throughput and the measurement
   conditions, never the bare 13.7 s.
2. **Restore time is not time-to-serving.** The number covers `psql` consuming the
   dump. Add container start, the app reconnecting, and — if D1 is involved — the
   Vault unseal below.
3. **"Correct on inspection" was wrong.** Before the drill existed, this page said
   these scripts were correct on inspection and merely untested. The first run
   found three defects that made the documented restore path fail on any real
   dump — see [Verifying the nightly backup actually ran](#verifying-the-nightly-backup-actually-ran).
   That is the argument for keeping the drill scheduled rather than running it
   once and deleting it.

### Verifying the nightly backup actually ran

The drill found that the generated backup script could not complete on a healthy
dump. Two independent bugs, both fixed, both invisible without running the thing:

- `zcat "$OUT" | head -c 4096 | grep -q ...` under `set -o pipefail` — `head` and
  `grep` exit early, `zcat` dies of SIGPIPE (141), and pipefail turns that into a
  failure. It passed on a toy dump and **rejected every dump larger than the 64 KB
  pipe buffer**, so the backup wrote its dump and then exited 1 on good data.
- `VAR="$(_envval KEY)"` under `set -e` — a *missing* optional key made `grep`
  exit 1 and killed the script silently, before the heartbeat and the retention
  sweep. The script's own "BACKUP_OFFSITE_ENABLED not set — skipping" branch was
  unreachable code.

Either path exits **after** writing the dump and **before** the heartbeat, which is
the nasty part: `/var/backups/fixitlab` fills with real, restorable dumps while the
dead-man's-switch never updates and retention never prunes. **On D3, confirm:**

```bash
# Should be less than ~26 h old (ALERT_BACKUP_MAX_AGE_HOURS). If it is stale or
# absent while dumps exist, the script was dying before the heartbeat.
date -d "@$(cat /var/backups/fixitlab/last_success_epoch)"
ls -lt /var/backups/fixitlab/*.sql.gz | head

# The smoking gun: dumps present, non-zero exits in the log.
tail -50 /var/log/fixitlab-pg-backup.log

# More than 7 dumps means the retention sweep never ran either.
ls -1 /var/backups/fixitlab/*.sql.gz | wc -l
```

Re-run `scripts/ci-pg-backup-cron.sh` against D3 to install the fixed script.

If D1 is lost, add the Vault unseal to any RTO: it needs **three unseal keys entered
by a human** ([vault-sealed](vault-sealed.md)), so recovery cannot complete unattended
regardless of how fast the droplet rebuilds.

## On-call

There is **no rotation**. One maintainer, stated plainly in
[ADR 0001](../adr/0001-four-droplet-topology.md) ("one maintainer, no on-call
rotation"). This is a documented business constraint, not an oversight to be papered
over — so the honest coverage model is:

- **Detection is automated, response is not.** `health-check.yml` and the business-
  signal monitor (`ALERT_MONITOR_INTERVAL_MINUTES`, default 5) open a GitHub issue;
  nobody is guaranteed to be awake to read it.
- **Effective response window: waking hours, best effort.** An overnight D3 failure
  can plausibly run until morning. Size customer commitments to that reality.
- **Escalation path is one person.** There is no secondary. Before any change that
  raises overnight risk (schema migration, data-tier work), do it early in the day.

Anything that needs a second responder needs a second person hired first. Until then,
prefer designs that **degrade** over designs that need a human at 3am — which is why
Redis, the broker, and Docker all fail soft and only the database returns 503.
