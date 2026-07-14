"""Live Incident Director — procedurally seeds & escalates incidents.

FOUNDATION feature (see also ``postmortem.py``). The Director is a *thin
orchestration layer over the existing* :class:`UnifiedSimulationEngine`; it does
NOT re-implement the simulation engine. Given a difficulty and an optional
template key it:

1. selects a parameterized incident from a catalogue that reuses the ~10
   on-call templates in ``apps/interviews/services/incident_scenarios.py`` and
   maps each to a concrete *root-cause break* on the sim engine's OS state, and
2. applies that break to a live engine / session, and
3. exposes ``tick()`` / ``next_escalation()`` hooks that can cascade a second
   fault into the sim state based on elapsed time or a learner-progress signal.

Everything is DETERMINISTIC for a given ``(seed, template_key)`` pair: template
selection and escalation ordering come from a stable SHA-256 hash of those
inputs, never from ``random``/``time`` at import. That means a replay/postmortem
generated from the same seed is byte-stable, which matters for the public
portfolio artifact.

The whole surface is additive and flag-guarded (``INCIDENT_DIRECTOR_ENABLED``)
so ordinary lab flows are untouched unless a caller explicitly opts in.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:  # avoid a hard import cycle at module load
    from .provisioner.simulation.unified_sim import UnifiedSimulationEngine


# ---------------------------------------------------------------------------
# Incident catalogue
# ---------------------------------------------------------------------------
# Each entry maps an on-call incident (mirroring incident_scenarios._INCIDENTS,
# which we read but do not edit) onto a concrete break we can apply to the sim
# engine's RHELOSState. ``root_cause`` is the *known* cause the Director owns —
# the postmortem uses it verbatim so the artifact never has to guess. ``break``
# and ``escalation`` are pure functions of the engine (idempotent, no randomness)
# so re-applying on a restored snapshot is safe.
#
# We keep this in-module (rather than importing the interview templates as data)
# because the interview templates are Q&A prompts, whereas the Director needs an
# executable state mutation. The ``title``/``summary`` deliberately echo the
# interview catalogue so the two stay recognizably the same incidents.


def _svc_break(state, name: str, description: str = "") -> None:
    """Force a systemd unit into the failed state (a common root-cause break)."""
    from .provisioner.simulation.rhel_os import SimService

    svc = state.services.get(name)
    if svc is None:
        state.services[name] = SimService(
            name, active="failed", enabled="enabled",
            description=description or name, sub_state="failed",
        )
    else:
        svc.active = "failed"
        svc.sub_state = "failed"


def _svc_recover(state, name: str) -> bool:
    svc = state.services.get(name)
    if svc is None:
        return False
    return svc.active == "active" and svc.sub_state == "running"


@dataclass(frozen=True)
class IncidentTemplate:
    key: str
    title: str
    summary: str
    difficulty: str  # easy | medium | hard
    root_cause: str
    detection_signal: str
    # apply the root-cause break to the engine's OS state
    apply_break: Callable[[Any], None]
    # the cascade fault applied on escalation
    apply_escalation: Callable[[Any], None]
    escalation_note: str
    # heuristic "is this resolved?" read over engine state (best-effort; the real
    # completion path still owns scoring). Used by the postmortem to note whether
    # the run self-reported resolution.
    is_resolved: Callable[[Any], bool]
    what_worked: str
    action_items: list[str] = field(default_factory=list)


def _mk_catalogue() -> dict[str, IncidentTemplate]:
    cat: list[IncidentTemplate] = [
        IncidentTemplate(
            key="oom_payment_pods",
            title="OOMKilled payment pods",
            summary=(
                "40% of payment-service pods are OOMKilled after a deploy added a "
                "cache layer; memory limit 512Mi."
            ),
            difficulty="medium",
            root_cause="Unbounded cache growth from a TTL change (60s -> 3600s) exceeded the 512Mi limit.",
            detection_signal="Alertmanager: payment-service OOMKilled, last exit 137.",
            apply_break=lambda st: _svc_break(st, "payment-svc", "Payment service (OOM)"),
            apply_escalation=lambda st: _svc_break(st, "checkout-svc", "Checkout (cascade from payment OOM)"),
            escalation_note="Cascade: checkout-svc starts erroring as payment retries pile up.",
            is_resolved=lambda st: _svc_recover(st, "payment-svc"),
            what_worked="Rolled back the cache TTL and restored the memory ceiling before the error budget burned.",
            action_items=[
                "Add a bounded-cache size guard with an alert at 80% of the memory limit.",
                "Require a staged canary for cache-layer changes.",
            ],
        ),
        IncidentTemplate(
            key="crashloop_configmap",
            title="CrashLoopBackOff after ConfigMap change",
            summary="api-gateway pods CrashLoopBackOff after a ConfigMap DB_HOST edit.",
            difficulty="medium",
            root_cause="ConfigMap changed DB_HOST to an FQDN missing the namespace segment; DNS resolution fails on startup.",
            detection_signal="P1: api-gateway pods CrashLoopBackOff, panic: nil pointer on startup.",
            apply_break=lambda st: _svc_break(st, "api-gateway", "API gateway (bad ConfigMap)"),
            apply_escalation=lambda st: _svc_break(st, "postgresql", "PostgreSQL (connection storm)"),
            escalation_note="Cascade: retry storm from restarting pods overwhelms postgresql connections.",
            is_resolved=lambda st: _svc_recover(st, "api-gateway"),
            what_worked="Rolled back the ConfigMap to restore the resolvable DB host, ending the crash loop.",
            action_items=[
                "Add a config-validation gate in CI that resolves DB_HOST before merge.",
                "Alert on CrashLoopBackOff rate, not just pod-down.",
            ],
        ),
        IncidentTemplate(
            key="nginx_502_spike",
            title="502 spike on nginx ingress",
            summary="Intermittent 502s under load, correlated with rolling deploys.",
            difficulty="easy",
            root_cause="Missing preStop hook + keepalive_timeout mismatch drops in-flight connections during rollout.",
            detection_signal="nginx error log: upstream prematurely closed connection.",
            apply_break=lambda st: _svc_break(st, "nginx", "nginx ingress (upstream resets)"),
            apply_escalation=lambda st: _svc_break(st, "app", "App tier (readiness flaps)"),
            escalation_note="Cascade: app pods flap readiness, widening the 502 blast radius.",
            is_resolved=lambda st: _svc_recover(st, "nginx"),
            what_worked="Added a preStop drain and aligned keepalive timeouts; 502s cleared without a second outage.",
            action_items=[
                "Add a preStop sleep + connection-drain to the deployment template.",
                "Synthetic-check ingress during every rollout.",
            ],
        ),
        IncidentTemplate(
            key="db_replication_lag",
            title="Database replication lag",
            summary="Read replicas 45 minutes behind primary after a write spike.",
            difficulty="hard",
            root_cause="An unthrottled batch job flooded writes while autovacuum was blocked on a hot table.",
            detection_signal="pg_stat_replication shows replay lag climbing; stale reads served.",
            apply_break=lambda st: _svc_break(st, "postgresql", "PostgreSQL replica (lag)"),
            apply_escalation=lambda st: _svc_break(st, "app", "App tier (stale-read errors)"),
            escalation_note="Cascade: app serves stale data, tripping data-integrity checks.",
            is_resolved=lambda st: _svc_recover(st, "postgresql"),
            what_worked="Paused the batch job and scaled the read pool; replication caught up within SLO.",
            action_items=[
                "Throttle bulk writers and alert on replication lag > SLO.",
                "Fix the blocked autovacuum on the hot table.",
            ],
        ),
        IncidentTemplate(
            key="cert_expiry",
            title="Certificate expiry on API gateway",
            summary="TLS handshakes fail at 3am; the gateway cert expired with no alert.",
            difficulty="easy",
            root_cause="Auto-renew (ACME) failed silently; no monitoring on the expiry date.",
            detection_signal="openssl shows the cert expired 2 hours ago; traffic failing closed.",
            apply_break=lambda st: _svc_break(st, "nginx", "TLS terminator (expired cert)"),
            apply_escalation=lambda st: _svc_break(st, "api-gateway", "API gateway (all TLS clients failing)"),
            escalation_note="Cascade: every TLS client fails closed, taking the API gateway down.",
            is_resolved=lambda st: _svc_recover(st, "nginx"),
            what_worked="Rolled back to the n-1 cert secret and re-ran ACME; handshakes recovered.",
            action_items=[
                "Alert on cert expiry at 30/14/7 days.",
                "Monitor the ACME renewal job for silent failures.",
            ],
        ),
        IncidentTemplate(
            key="inode_exhaustion",
            title="Disk full — inodes exhausted",
            summary="A worker node stops accepting writes; df shows free space but writes fail.",
            difficulty="medium",
            root_cause="A debug flag produced millions of tiny log fragments; /var hit 100% inode usage.",
            detection_signal="df -i shows /var at 100% inode usage; 'no space left on device'.",
            apply_break=lambda st: _svc_break(st, "rsyslog", "Log shipper (inode-full)"),
            apply_escalation=lambda st: _svc_break(st, "crond", "cron (cannot write spool)"),
            escalation_note="Cascade: cron and other writers fail as the inode table stays full.",
            is_resolved=lambda st: _svc_recover(st, "rsyslog"),
            what_worked="Truncated open logs, restarted the shipper, and fixed logrotate; writes resumed.",
            action_items=[
                "Alert on inode usage, not just block usage.",
                "Remove the stray debug logging flag.",
            ],
        ),
        IncidentTemplate(
            key="redis_eviction_storm",
            title="Redis memory eviction storm",
            summary="Cache hit rate dropped 95% -> 40%; p99 latency tripled.",
            difficulty="medium",
            root_cause="A new feature stored 2MB session blobs with no TTL, hitting maxmemory allkeys-lru eviction.",
            detection_signal="INFO memory shows evicted_keys climbing; clients spiking.",
            apply_break=lambda st: _svc_break(st, "redis", "Redis (eviction storm)"),
            apply_escalation=lambda st: _svc_break(st, "postgresql", "PostgreSQL (cold-cache DB overload)"),
            escalation_note="Cascade: cold cache pushes read load onto the DB, which saturates.",
            is_resolved=lambda st: _svc_recover(st, "redis"),
            what_worked="Added TTLs and compressed payloads; hit rate recovered without hammering the DB.",
            action_items=[
                "Enforce a max value size and mandatory TTL on session keys.",
                "Add an eviction-rate alert.",
            ],
        ),
        IncidentTemplate(
            key="feature_flag_checkout",
            title="Bad deploy — feature flag kills checkout",
            summary="Checkout success dropped 80% after a flag rolled to 100%.",
            difficulty="hard",
            root_cause="new_checkout_flow flag hit 100% without a canary; a new provider's API key was missing in prod.",
            detection_signal="Checkout success -80%; NullPointerException in payment routing.",
            apply_break=lambda st: _svc_break(st, "checkout-svc", "Checkout (flag + missing secret)"),
            apply_escalation=lambda st: _svc_break(st, "payment-svc", "Payment (routing NPE)"),
            escalation_note="Cascade: payment routing NPEs propagate to the payment service.",
            is_resolved=lambda st: _svc_recover(st, "checkout-svc"),
            what_worked="Disabled the flag and added the missing prod secret; checkout recovered.",
            action_items=[
                "Never roll a flag to 100% without a staged canary.",
                "Add a CI check for staging/prod config parity.",
            ],
        ),
        IncidentTemplate(
            key="dns_migration",
            title="DNS propagation failure after migration",
            summary="30% of EU users can't reach the API after an LB migration.",
            difficulty="hard",
            root_cause="Old A record TTL was 86400s; EU resolvers cached the decommissioned LB's IP.",
            detection_signal="dig from EU resolvers still returns the old IP.",
            apply_break=lambda st: _svc_break(st, "nginx", "Edge LB (stale DNS in EU)"),
            apply_escalation=lambda st: _svc_break(st, "api-gateway", "API gateway (EU region down)"),
            escalation_note="Cascade: the EU region's gateway sees zero healthy upstreams.",
            is_resolved=lambda st: _svc_recover(st, "nginx"),
            what_worked="Ran dual-stack until caches expired and lowered TTL; EU traffic recovered.",
            action_items=[
                "Lower record TTLs ahead of any migration.",
                "Keep the old LB dual-stacked until TTL fully expires.",
            ],
        ),
        IncidentTemplate(
            key="thread_pool_exhaustion",
            title="Thread pool exhaustion under load",
            summary="Latency spikes at peak while CPU stays at 30%.",
            difficulty="hard",
            root_cause="No circuit breaker: a slow inventory dependency blocked every worker thread; retries amplified load.",
            detection_signal="Thread dump: all workers blocked on inventory HTTP calls.",
            apply_break=lambda st: _svc_break(st, "app", "App tier (thread pool blocked)"),
            apply_escalation=lambda st: _svc_break(st, "inventory-svc", "Inventory (retry storm)"),
            escalation_note="Cascade: the retry storm drives inventory-svc into failure too.",
            is_resolved=lambda st: _svc_recover(st, "app"),
            what_worked="Tightened timeouts and added a bulkhead + cached fallback; the core API held.",
            action_items=[
                "Add circuit breakers and bounded timeouts to downstream calls.",
                "Bulkhead the inventory call path.",
            ],
        ),
    ]
    return {t.key: t for t in cat}


CATALOGUE: dict[str, IncidentTemplate] = _mk_catalogue()

# Feature flag: keep the whole Director path additive/off unless a caller opts in.
FLAG_NAME = "INCIDENT_DIRECTOR_ENABLED"


def director_enabled() -> bool:
    from django.conf import settings

    return bool(getattr(settings, FLAG_NAME, False))


def _stable_hash(*parts: Any) -> int:
    """Deterministic non-negative int from the inputs (never random/time)."""
    raw = "\x1f".join(str(p) for p in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def select_template(seed: Any, template_key: str = "", difficulty: str = "") -> IncidentTemplate:
    """Deterministically pick a template.

    If ``template_key`` is given and valid, it wins. Otherwise we pick from the
    catalogue (optionally filtered by ``difficulty``) using a stable hash of the
    seed, so the same seed always yields the same incident.
    """
    if template_key and template_key in CATALOGUE:
        return CATALOGUE[template_key]

    pool = list(CATALOGUE.values())
    if difficulty:
        filtered = [t for t in pool if t.difficulty == difficulty]
        if filtered:
            pool = filtered
    pool.sort(key=lambda t: t.key)  # stable order regardless of dict insertion
    idx = _stable_hash(seed, difficulty) % len(pool)
    return pool[idx]


class IncidentDirector:
    """Thin orchestration layer that drives incidents on a sim engine.

    Usage (deterministic per seed):

        director = IncidentDirector(seed="abc", difficulty="medium")
        director.seed_incident(engine)      # apply root-cause break
        director.next_escalation(engine)    # cascade a second fault
        director.tick(engine, elapsed_seconds=..., progress=...)

    The Director never owns the engine's lifecycle — the caller passes the engine
    (or a session id we resolve to a live engine) each call, so a Redis-restored
    engine on another worker works identically.
    """

    def __init__(self, seed: Any = 0, template_key: str = "", difficulty: str = ""):
        self.seed = seed
        self.template = select_template(seed, template_key, difficulty)
        self.template_key = self.template.key
        self.escalations: list[dict] = []
        self._seeded = False
        self._escalation_fired = False

    # -- engine resolution -------------------------------------------------
    @staticmethod
    def _engine_for(engine_or_session_id) -> "UnifiedSimulationEngine | None":
        from .provisioner.simulation.unified_sim import UnifiedSimulationEngine

        if isinstance(engine_or_session_id, UnifiedSimulationEngine):
            return engine_or_session_id
        # Treat as a session id and resolve a live engine from the in-memory
        # registry. The provisioner registers the engine under
        # ``entry["state"]["engine"]`` (see simulation_provisioner), so read that;
        # fall back to a top-level ``engine`` key for any other producer.
        from .provisioner.simulation.shell import get_sim_session

        entry = get_sim_session(str(engine_or_session_id))
        if not entry:
            return None
        eng = entry.get("state", {}).get("engine") or entry.get("engine")
        return eng if isinstance(eng, UnifiedSimulationEngine) else None

    # -- root-cause break --------------------------------------------------
    def seed_incident(self, engine_or_session_id) -> dict:
        """Apply the incident's root-cause break to the engine state.

        Idempotent: re-seeding just re-applies the (idempotent) break.
        Returns a structured summary the caller/model can persist.
        """
        engine = self._engine_for(engine_or_session_id)
        if engine is None:
            return {"applied": False, "reason": "no live engine"}
        self.template.apply_break(engine.shell.state)
        self._seeded = True
        return {
            "applied": True,
            "template_key": self.template_key,
            "title": self.template.title,
            "root_cause": self.template.root_cause,
            "detection_signal": self.template.detection_signal,
            "difficulty": self.template.difficulty,
        }

    # -- escalation --------------------------------------------------------
    def next_escalation(self, engine_or_session_id) -> dict | None:
        """Cascade a second fault into the sim state.

        Foundation: a single deterministic escalation step (cascade fault). A
        future richer escalation timeline (multiple ordered steps, per-learner
        pacing) can extend ``escalations`` — the persistence shape already stores
        a list.
        """
        if self._escalation_fired:
            return None
        engine = self._engine_for(engine_or_session_id)
        if engine is None:
            return None
        self.template.apply_escalation(engine.shell.state)
        self._escalation_fired = True
        record = {
            "step": len(self.escalations) + 1,
            "kind": "cascade_fault",
            "note": self.template.escalation_note,
        }
        self.escalations.append(record)
        return record

    def tick(self, engine_or_session_id, elapsed_seconds: float = 0.0,
             progress: float = 0.0, escalate_after_seconds: float = 300.0) -> dict | None:
        """Time/progress-driven hook.

        Fires the escalation once the learner has spent ``escalate_after_seconds``
        without resolving (progress < 1.0). Deterministic: identical inputs give
        an identical decision. Returns the escalation record if one fired, else
        ``None``.
        """
        if self._escalation_fired or progress >= 1.0:
            return None
        if elapsed_seconds >= escalate_after_seconds:
            return self.next_escalation(engine_or_session_id)
        return None

    def is_resolved(self, engine_or_session_id) -> bool:
        engine = self._engine_for(engine_or_session_id)
        if engine is None:
            return False
        try:
            return bool(self.template.is_resolved(engine.shell.state))
        except Exception:  # noqa: BLE001 — heuristic read must never raise
            return False

    def summary(self) -> dict:
        """A JSON-safe snapshot of the Director's plan (for the model/postmortem)."""
        return {
            "seed": str(self.seed),
            "template_key": self.template_key,
            "title": self.template.title,
            "summary": self.template.summary,
            "difficulty": self.template.difficulty,
            "root_cause": self.template.root_cause,
            "detection_signal": self.template.detection_signal,
            "escalations": list(self.escalations),
            "what_worked": self.template.what_worked,
            "action_items": list(self.template.action_items),
        }
