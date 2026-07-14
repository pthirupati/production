"""Tests for the Live Incident Director + auto postmortem + public replay.

Covers the three required cases:
  (a) the Director seeds an incident + escalation deterministically and the
      engine state reflects the break;
  (b) postmortem generation produces a timeline + root cause + MTTR from a
      resolved run;
  (c) the public postmortem endpoint returns 200 for a valid token and 404 for a
      bad one, and requires no auth.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.labs.incident_director import (
    CATALOGUE,
    IncidentDirector,
    director_enabled,
    select_template,
)
from apps.labs.models import CommandHistory, IncidentRun, LabSession, Postmortem, SessionRecording
from apps.labs.postmortem import build_postmortem_data, generate_postmortem
from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine
from apps.question_bank.models import Scenario, Technology

User = get_user_model()


def _make_scenario(slug="incident-lab"):
    tech = Technology.objects.create(name=f"Tech {slug}")
    return Scenario.objects.create(
        technology=tech,
        slug=slug,
        title="Incident Lab",
        category="troubleshooting",
        difficulty="medium",
        description="An incident lab",
        lab_mode="simulation",
        simulation_type="generic",
        solution_explanation="Restart the service.",
    )


def _make_session(user, scenario):
    return LabSession.objects.create(
        user=user, scenario=scenario, status="RUNNING", provider="docker",
    )


# ---------------------------------------------------------------------------
# (a) Director determinism + engine break
# ---------------------------------------------------------------------------
class IncidentDirectorTests(TestCase):
    def test_template_selection_is_deterministic(self):
        a = select_template(seed="abc-123")
        b = select_template(seed="abc-123")
        self.assertEqual(a.key, b.key)
        # A different seed can pick a different template (but is itself stable).
        c = select_template(seed="zzz-999")
        self.assertEqual(c.key, select_template(seed="zzz-999").key)

    def test_explicit_template_key_wins(self):
        d = IncidentDirector(seed="whatever", template_key="oom_payment_pods")
        self.assertEqual(d.template_key, "oom_payment_pods")

    def test_difficulty_filter(self):
        t = select_template(seed="x", difficulty="hard")
        self.assertEqual(t.difficulty, "hard")

    def test_seed_incident_breaks_engine_state(self):
        engine = UnifiedSimulationEngine(scenario_slug="incident-lab", simulation_type="generic")
        director = IncidentDirector(seed="s1", template_key="nginx_502_spike")
        result = director.seed_incident(engine)
        self.assertTrue(result["applied"])
        self.assertEqual(result["template_key"], "nginx_502_spike")
        # The nginx unit must now be failed (root-cause break reflected in state).
        nginx = engine.shell.state.services.get("nginx")
        self.assertIsNotNone(nginx)
        self.assertEqual(nginx.active, "failed")

    def test_next_escalation_cascades_second_fault(self):
        engine = UnifiedSimulationEngine(scenario_slug="incident-lab")
        director = IncidentDirector(seed="s2", template_key="nginx_502_spike")
        director.seed_incident(engine)
        record = director.next_escalation(engine)
        self.assertIsNotNone(record)
        self.assertEqual(record["step"], 1)
        self.assertEqual(record["kind"], "cascade_fault")
        # Cascade fault is the 'app' service for this template.
        app = engine.shell.state.services.get("app")
        self.assertIsNotNone(app)
        self.assertEqual(app.active, "failed")
        # Escalation is one-shot for the foundation.
        self.assertIsNone(director.next_escalation(engine))

    def test_tick_escalates_after_threshold(self):
        engine = UnifiedSimulationEngine(scenario_slug="incident-lab")
        director = IncidentDirector(seed="s3", template_key="db_replication_lag")
        director.seed_incident(engine)
        # Before threshold: no escalation.
        self.assertIsNone(director.tick(engine, elapsed_seconds=10, escalate_after_seconds=300))
        # After threshold with unresolved progress: escalate.
        rec = director.tick(engine, elapsed_seconds=301, progress=0.5, escalate_after_seconds=300)
        self.assertIsNotNone(rec)

    def test_tick_does_not_escalate_when_resolved(self):
        engine = UnifiedSimulationEngine(scenario_slug="incident-lab")
        director = IncidentDirector(seed="s4", template_key="cert_expiry")
        director.seed_incident(engine)
        self.assertIsNone(
            director.tick(engine, elapsed_seconds=999, progress=1.0, escalate_after_seconds=1)
        )

    def test_is_resolved_reads_engine_state(self):
        engine = UnifiedSimulationEngine(scenario_slug="incident-lab")
        director = IncidentDirector(seed="s5", template_key="nginx_502_spike")
        director.seed_incident(engine)
        self.assertFalse(director.is_resolved(engine))
        # Repair the broken unit -> resolved.
        nginx = engine.shell.state.services["nginx"]
        nginx.active = "active"
        nginx.sub_state = "running"
        self.assertTrue(director.is_resolved(engine))

    def test_flag_off_by_default(self):
        # No override -> flag absent -> disabled (surface invisible).
        self.assertFalse(director_enabled())

    def test_catalogue_covers_interview_incidents(self):
        # We reuse the ~10 on-call templates; keep at least that many.
        self.assertGreaterEqual(len(CATALOGUE), 10)


# ---------------------------------------------------------------------------
# (b) Postmortem generation
# ---------------------------------------------------------------------------
class PostmortemGenerationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="learner", password="pw12345", email="l@x.io")
        self.scenario = _make_scenario()
        self.session = _make_session(self.user, self.scenario)

    def _resolved_run(self):
        director = IncidentDirector(seed=str(self.session.id), template_key="inode_exhaustion")
        engine = UnifiedSimulationEngine(scenario_slug="incident-lab")
        director.seed_incident(engine)
        director.next_escalation(engine)
        started = timezone.now() - timedelta(minutes=12)
        run = IncidentRun.objects.create(
            lab_session=self.session,
            template_key=director.template_key,
            seed=str(self.session.id),
            root_cause=director.template.root_cause,
            detection_signal=director.template.detection_signal,
            difficulty=director.template.difficulty,
            escalations=director.escalations,
            director_plan=director.summary(),
        )
        # Backdate timing so MTTR is computable.
        run.started_at = started
        run.detected_at = started + timedelta(minutes=1)
        run.mitigated_at = started + timedelta(minutes=6)
        run.resolved_at = started + timedelta(minutes=10)
        run.save()
        # A couple of commands for the timeline.
        CommandHistory.objects.create(session=self.session, command="journalctl -u rsyslog", exit_code=0)
        CommandHistory.objects.create(session=self.session, command="truncate -s 0 /var/log/big.log", exit_code=0)
        CommandHistory.objects.create(session=self.session, command="systemctl restart rsyslog", exit_code=0)
        return run

    def test_build_postmortem_data_has_timeline_root_cause_mttr(self):
        run = self._resolved_run()
        data = build_postmortem_data(run)
        # Timeline built from command history.
        self.assertGreaterEqual(len(data["timeline"]), 3)
        # Key actions detect state-changing commands.
        self.assertTrue(any(a["kind"] == "action" for a in data["key_actions"]))
        # Root cause carried from the Director.
        self.assertIn("inode", data["root_cause"].lower())
        # MTTR computed (detect -> resolve = 9 minutes = 540s).
        self.assertEqual(data["mttr"]["mttr_seconds"], 540)
        self.assertEqual(data["mttr"]["time_to_detect_seconds"], 60)
        # Escalations carried through.
        self.assertGreaterEqual(len(data["escalations"]), 1)
        # Action items present.
        self.assertTrue(data["action_items"])

    def test_markdown_render_is_deterministic(self):
        run = self._resolved_run()
        pm1 = generate_postmortem(run)
        md1 = pm1.markdown
        # Regenerate -> same token, same markdown (deterministic).
        pm2 = generate_postmortem(run)
        self.assertEqual(pm1.public_token, pm2.public_token)
        self.assertEqual(md1, pm2.markdown)
        self.assertIn("Blameless postmortem", md1)
        self.assertIn("## Root cause", md1)
        self.assertIn("## Timeline", md1)
        self.assertIn("MTTR", md1)

    def test_replay_reference_reuses_session_recording(self):
        run = self._resolved_run()
        SessionRecording.objects.create(
            session=self.session,
            events=[[0.0, "o", "hello"], [1.0, "o", "world"]],
            total_duration=1.0,
        )
        data = build_postmortem_data(run)
        self.assertIsNotNone(data["replay"])
        self.assertTrue(data["replay"]["available"])
        self.assertEqual(data["replay"]["event_count"], 2)


# ---------------------------------------------------------------------------
# (c) Public postmortem endpoint
# ---------------------------------------------------------------------------
class PublicPostmortemEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="owner", password="pw12345", email="o@x.io")
        self.scenario = _make_scenario("incident-lab-2")
        self.session = _make_session(self.user, self.scenario)
        self.run = IncidentRun.objects.create(
            lab_session=self.session,
            template_key="cert_expiry",
            seed="fixed-seed",
            root_cause=CATALOGUE["cert_expiry"].root_cause,
            director_plan=IncidentDirector(seed="fixed-seed", template_key="cert_expiry").summary(),
            detected_at=timezone.now(),
            resolved_at=timezone.now() + timedelta(minutes=5),
        )
        self.pm = generate_postmortem(self.run)

    def test_valid_token_returns_200_no_auth(self):
        url = reverse("public-postmortem", args=[self.pm.public_token])
        # No credentials set on the client — must still work.
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["public_token"], str(self.pm.public_token))
        self.assertIn("postmortem", body)
        self.assertIn("markdown", body)
        self.assertIn("root_cause", body["postmortem"])

    def test_bad_token_returns_404(self):
        url = reverse("public-postmortem", args=[uuid.uuid4()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_unshared_postmortem_returns_404(self):
        self.pm.is_public = False
        self.pm.save(update_fields=["is_public"])
        url = reverse("public-postmortem", args=[self.pm.public_token])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_only_returns_the_tokened_postmortem(self):
        # A second postmortem for a different session must not leak via the first token.
        other_scenario = _make_scenario("incident-lab-3")
        other_session = _make_session(self.user, other_scenario)
        other_run = IncidentRun.objects.create(
            lab_session=other_session, template_key="oom_payment_pods",
            root_cause=CATALOGUE["oom_payment_pods"].root_cause,
            director_plan=IncidentDirector(seed="s", template_key="oom_payment_pods").summary(),
        )
        other_pm = generate_postmortem(other_run)
        url = reverse("public-postmortem", args=[self.pm.public_token])
        resp = self.client.get(url)
        self.assertEqual(resp.json()["public_token"], str(self.pm.public_token))
        self.assertNotEqual(str(other_pm.public_token), resp.json()["public_token"])


# ---------------------------------------------------------------------------
# Flag-guarded Director entrypoint
# ---------------------------------------------------------------------------
class IncidentDirectorViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="u", password="pw12345", email="u@x.io")
        self.scenario = _make_scenario("incident-lab-4")
        self.session = _make_session(self.user, self.scenario)
        self.client.force_authenticate(self.user)

    def test_flag_off_returns_404(self):
        url = reverse("incident-director")
        resp = self.client.post(url, {"session_id": str(self.session.id)}, format="json")
        self.assertEqual(resp.status_code, 404)

    @override_settings(INCIDENT_DIRECTOR_ENABLED=True)
    def test_flag_on_starts_incident_run(self):
        url = reverse("incident-director")
        resp = self.client.post(
            url,
            {"session_id": str(self.session.id), "action": "start", "template_key": "redis_eviction_storm"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("incident_run_id", body)
        self.assertEqual(body["plan"]["template_key"], "redis_eviction_storm")
        self.assertTrue(IncidentRun.objects.filter(lab_session=self.session).exists())
