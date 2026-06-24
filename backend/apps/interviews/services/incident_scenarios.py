"""Free incident / on-call scenario engine — no LLM/API.

Progressive incident interviews: open with alert context, reveal clues as the
candidate asks diagnostic questions or names commands, probe comms/rollback.
Used for scenario, troubleshooting, sla, and itil category slots.
"""

from __future__ import annotations

import random
import re

from apps.interviews.services.interview_ai import _normalize, _pick_unused

# Each scenario: setup, clue triggers → reveal text, root cause, fix signals.
_INCIDENTS: list[dict] = [
    {
        "title": "OOMKilled payment pods",
        "setup": (
            "You're on call. Alertmanager: 40% of payment-service pods are OOMKilled. "
            "CPU looks normal. Memory limit is 512Mi. A deploy landed 20 minutes ago that added a cache layer."
        ),
        "clues": [
            (("describe", "pod", "oom", "kill", "137"), "kubectl describe shows OOMKilled, last exit 137."),
            (("top", "memory", "metric"), "kubectl top pod shows memory pegged near 490Mi before kill."),
            (("log", "git", "commit", "deploy"), "Recent commit changed cache TTL from 60s to 3600s."),
            (("rollback", "limit", "ttl", "cache"), "Root cause: unbounded cache growth from TTL change."),
        ],
        "probes": [
            "What's your first move — stabilize traffic or dig into the deploy?",
            "Who do you notify in the first five minutes?",
            "What's your rollback trigger before you touch prod config?",
        ],
    },
    {
        "title": "CrashLoopBackOff after ConfigMap change",
        "setup": (
            "P1: api-gateway pods are CrashLoopBackOff after a ConfigMap update ten minutes ago. "
            "The previous version was healthy. Error budget is burning."
        ),
        "clues": [
            (("log", "kubectl logs", "panic", "error"), "Logs show panic: nil pointer dereference on startup."),
            (("configmap", "config", "env"), "ConfigMap changed DB_HOST from 'postgres' to 'postgres.svc.cluster.local'."),
            (("dns", "nslookup", "connect", "psql"), "DNS resolution fails — FQDN missing namespace segment."),
            (("fix", "fqdn", "default.svc", "rollback"), "Fix: postgres.default.svc.cluster.local or rollback ConfigMap."),
        ],
        "probes": [
            "How do you confirm blast radius before restarting anything?",
            "What do you post in the incident channel right now?",
            "When would you page a second engineer?",
        ],
    },
    {
        "title": "502 spike on nginx ingress",
        "setup": (
            "Users report intermittent 502s. It correlates with deploys but only under load. "
            "Upstream health checks look green on half the pods."
        ),
        "clues": [
            (("nginx", "error log", "upstream"), "nginx error log: upstream prematurely closed connection."),
            (("readiness", "probe", "health"), "Half the pods fail readiness briefly during rolling update."),
            (("timeout", "keepalive", "worker"), "keepalive_timeout mismatch between nginx and upstream."),
            (("grace", "prestop", "drain", "sleep"), "Missing preStop hook — connections dropped mid-request."),
        ],
        "probes": [
            "Walk me through your triage order — ingress, app, or platform first?",
            "How do you validate a fix without a second outage?",
        ],
    },
    {
        "title": "Database replication lag",
        "setup": (
            "Read replicas are 45 minutes behind primary. Write traffic spiked after a marketing push. "
            "Some reads are serving stale data to users."
        ),
        "clues": [
            (("replication", "lag", "postgres", "show"), "pg_stat_replication shows replay lag climbing."),
            (("write", "bulk", "batch", "job"), "A batch job started writing large rows without throttling."),
            (("index", "vacuum", "bloat"), "Autovacuum blocked on a hot table — bloat on the primary."),
            (("throttle", "pause", "job", "scale"), "Mitigation: pause batch job, scale read pool, throttle writes."),
        ],
        "probes": [
            "How do you communicate stale reads to product while you fix lag?",
            "What's acceptable lag for this service's SLO?",
        ],
    },
    {
        "title": "Certificate expiry on API gateway",
        "setup": (
            "Mobile clients fail TLS handshake at 3am. The API gateway cert expired with no auto-renew alert. "
            "Traffic is failing closed."
        ),
        "clues": [
            (("openssl", "cert", "expir", "tls"), "Cert expired 2 hours ago; no monitoring on expiry date."),
            (("renew", "letsencrypt", "acme"), "Auto-renew job failed silently — ACME challenge blocked."),
            (("rollback", "previous cert", "secret"), "Previous cert still in secret version n-1."),
            (("alert", "monitor", "30 day"), "Add cert expiry alert at 30/14/7 days."),
        ],
        "probes": [
            "What's your immediate restore path — rollback secret or emergency renew?",
            "How do you prevent this class of failure next quarter?",
        ],
    },
    {
        "title": "Disk full — inodes exhausted",
        "setup": (
            "A batch worker node stops accepting writes. df shows 40% free on /var but apps report 'no space left on device'. "
            "Log shipping stopped 30 minutes ago."
        ),
        "clues": [
            (("df", "inode", "iuse"), "df -i shows /var at 100% inode usage."),
            (("log", "rotate", "journal"), "Millions of tiny rotated log fragments from a debug flag left on."),
            (("lsof", "delete", "open"), "Deleted log files still held open — space not reclaimed."),
            (("truncate", "restart", "logrotate"), "Fix: truncate open logs, restart shipper, fix logrotate config."),
        ],
        "probes": [
            "How do you confirm whether this is blocks or inodes before you delete anything?",
            "What monitoring would have caught this before writes failed?",
        ],
    },
    {
        "title": "Redis memory eviction storm",
        "setup": (
            "Cache hit rate dropped from 95% to 40% in ten minutes. API latency p99 tripled. "
            "Redis cluster shows elevated evictions and connected clients spiking."
        ),
        "clues": [
            (("redis", "info", "memory", "evict"), "INFO memory shows evicted_keys climbing — maxmemory-policy allkeys-lru."),
            (("key", "scan", "ttl", "large"), "A new feature stores 2MB session blobs without TTL."),
            (("hot", "key", "single"), "One key pattern accounts for 60% of memory — unbounded fan-out."),
            (("ttl", "compress", "shard", "limit"), "Mitigation: add TTL, compress payloads, shard hot keys."),
        ],
        "probes": [
            "Do you fail open to the database or fail closed when cache is cold?",
            "How do you validate recovery without hammering the DB?",
        ],
    },
    {
        "title": "Bad deploy — feature flag kills checkout",
        "setup": (
            "Checkout success rate dropped 80% after a deploy. Error logs show NullPointerException in payment routing. "
            "Feature flag 'new_checkout_flow' was enabled for 100% of traffic."
        ),
        "clues": [
            (("log", "stack", "null", "exception"), "Stack trace points to missing config for a new payment provider."),
            (("flag", "feature", "launchdarkly", "toggle"), "Flag rolled to 100% without a staged canary."),
            (("config", "env", "missing", "secret"), "New provider API key not in prod secrets — works in staging."),
            (("rollback", "disable", "flag", "canary"), "Fix: disable flag or rollback; add canary + config check in CI."),
        ],
        "probes": [
            "What's your comms update to product and support in the first 15 minutes?",
            "How do you prevent config drift between staging and prod next time?",
        ],
    },
    {
        "title": "DNS propagation failure after migration",
        "setup": (
            "After migrating to a new load balancer, 30% of users in EU can't reach the API. "
            "US traffic is healthy. TTL on the old record was 86400 seconds."
        ),
        "clues": [
            (("dig", "nslookup", "dns"), "dig from EU resolvers still returns the old IP address."),
            (("ttl", "record", "route53", "cloudflare"), "Old A record TTL was 24h — resolvers caching stale answers."),
            (("geo", "health", "region"), "EU edge still routing to decommissioned LB in eu-west-1."),
            (("lower ttl", "cname", "rollback", "dual"), "Fix: lower TTL pre-migration; run dual-stack until cache expires."),
        ],
        "probes": [
            "How do you measure blast radius when only one region is affected?",
            "When is it worth an emergency DNS TTL change versus waiting it out?",
        ],
    },
    {
        "title": "Thread pool exhaustion under load",
        "setup": (
            "During peak traffic, API latency spikes but CPU stays at 30%. Thread dump shows all worker threads blocked "
            "waiting on a downstream inventory service that started timing out."
        ),
        "clues": [
            (("thread", "dump", "blocked", "jstack"), "All Tomcat threads blocked on inventory HTTP calls."),
            (("timeout", "circuit", "breaker", "retry"), "No circuit breaker — retry storm amplifies load on inventory."),
            (("inventory", "deploy", "slow", "query"), "Inventory team deployed a slow query — p95 at 8 seconds."),
            (("bulkhead", "timeout", "fallback", "cache"), "Mitigation: tighten timeouts, bulkhead, cached fallback stock."),
        ],
        "probes": [
            "How do you protect the core API when a dependency degrades?",
            "What SLO breach do you declare — yours or the dependency's?",
        ],
    },
]

_OPENERS = [
    "You're the on-call engineer. Here's the situation:",
    "Incident bridge is starting — I'll set the scene:",
    "P1 just landed. Context:",
    "Alert fired — walk me through how you'd handle this:",
]

_METHODOLOGY_PROBES = [
    "Before you change anything — what signal confirms your hypothesis?",
    "What's in the incident channel update you'd send in the next 10 minutes?",
    "How do you know when it's safe to close this incident?",
    "What's the rollback if your fix makes it worse?",
]


def pick_scenario(used_titles: set[str], rng: random.Random, round_type: str = "") -> dict:
    def _unused(s: dict) -> bool:
        t = _normalize(s["title"])
        return t not in used_titles and not any(t in u for u in used_titles)

    pool = [s for s in _INCIDENTS if _unused(s)]
    if round_type == "sre_oncall":
        # Prefer scenarios with comms/SLO probes for on-call rounds.
        comms = [s for s in pool if any("channel" in p.lower() or "SLO" in p for p in (s.get("probes") or []))]
        if comms:
            pool = comms
    if not pool:
        pool = _INCIDENTS
    rng.shuffle(pool)
    return pool[0]


def _clue_index_from_answer(answer: str, scenario: dict, revealed: int) -> int:
    """Return how many clues should be revealed based on answer content."""
    low = (answer or "").lower()
    clues = scenario.get("clues") or []
    new_revealed = revealed
    for i, (triggers, _text) in enumerate(clues):
        if i < revealed:
            continue
        if any(t in low for t in triggers):
            new_revealed = i + 1
            break
    return new_revealed


def generate_incident_turn(
    *,
    scenario: dict,
    last_answer: str = "",
    revealed_clues: int = 0,
    phase: str = "open",
    used: set[str],
    rng: random.Random,
    time_stitch: str = "",
    round_type: str = "",
) -> tuple[str, int, str]:
    """Return (question_text, new_revealed_count, phase)."""
    title = scenario.get("title", "Incident")
    setup = scenario.get("setup", "")
    clues = scenario.get("clues") or []

    if phase == "open" or revealed_clues == 0:
        opener = _pick_unused(_OPENERS, used, rng) or _OPENERS[0]
        if round_type == "sre_oncall":
            opener = "You're the on-call SRE — pager just fired. Here's the situation:"
        text = f"{opener} {setup} What's your first step?"
        if time_stitch:
            text = f"{time_stitch} {text}"
        return text, 0, "investigate"

    new_revealed = _clue_index_from_answer(last_answer, scenario, revealed_clues)
    if new_revealed > revealed_clues and new_revealed <= len(clues):
        _, clue_text = clues[new_revealed - 1]
        text = f"Okay — you investigate and find: {clue_text} What do you do next?"
        if time_stitch:
            text = f"{time_stitch} {text}"
        return text, new_revealed, "investigate"

    if revealed_clues >= len(clues):
        probe = _pick_unused(_METHODOLOGY_PROBES, used, rng) or _METHODOLOGY_PROBES[0]
        text = f"Given what we know on {title} — {probe}"
        if time_stitch:
            text = f"{time_stitch} {text}"
        return text, revealed_clues, "wrap"

    probes = scenario.get("probes") or _METHODOLOGY_PROBES
    probe = _pick_unused(probes, used, rng) or probes[0]
    hint = ""
    if revealed_clues < len(clues):
        # Nudge toward next diagnostic without giving answer away.
        triggers = clues[revealed_clues][0]
        hint = f" (Hint: you'd learn something from checking {triggers[0]}.)"
    text = f"Still on {title}. {probe}{hint}"
    if time_stitch:
        text = f"{time_stitch} {text}"
    return text, revealed_clues, "investigate"
