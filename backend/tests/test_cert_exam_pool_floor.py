"""Certification exam-pool integrity: dead refs and the >=2-scenario floor.

Two independent guards for the same failure mode. Grading in
``apps/certifications/views.py`` divides the weighted sum by the FULL track
weight, so an objective whose exam pool is empty silently subtracts its whole
weight from every achievable score — a candidate can answer every served
scenario correctly and still fail, with no error anywhere.

  1. A static check over the seed YAMLs: every objective must reference at
     least ``EXAM_SCENARIOS_PER_OBJECTIVE`` scenarios that actually exist on
     disk. Below that floor the sampler stops randomizing and repeat attempts
     serve identical labs; at zero it makes the objective unpassable.
  2. A live check on ExamStartView: when the reachable ceiling falls under the
     track's passing_score, starting the exam must fail loudly instead of
     selling an unwinnable attempt.

Note on slug resolution: ``seed_scenarios`` writes ``Scenario.slug`` from the
``slug:`` key inside each scenario.yaml, falling back to the directory name.
250 scenarios declare a slug that differs from their directory, so resolving
exam-pool refs against directory names alone reports ~70 false "dead" refs.
Resolve the same way the seeder does.
"""

import glob
import os

import yaml
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient, APITestCase

from apps.certifications.models import CertificationTrack, TrackScenario
from apps.certifications.views import EXAM_SCENARIOS_PER_OBJECTIVE
from apps.question_bank.models import Scenario, Technology

User = get_user_model()

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCENARIOS_DIR = os.path.join(REPO_ROOT, "scenarios")
CERT_DATA_DIR = os.path.join(
    REPO_ROOT, "backend", "apps", "certifications", "management", "commands", "data"
)


def _live_scenario_slugs():
    """Slugs the seeder would create, resolved exactly as seed_scenarios does."""
    slugs = set()
    for path in glob.glob(os.path.join(SCENARIOS_DIR, "*", "*", "scenario.yaml")):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
        except Exception:
            continue
        slugs.add(data.get("slug") or os.path.basename(os.path.dirname(path)))
    return slugs


class CertExamPoolFloorTests(APITestCase):
    """Static integrity of the shipped cert YAMLs — no DB needed."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.live = _live_scenario_slugs()

    def test_scenarios_dir_is_discoverable(self):
        # Guards the whole file: an empty `live` set would make every other
        # assertion below vacuously pass in one direction and noisily fail in
        # the other, so fail fast and unambiguously if the path is wrong.
        self.assertTrue(os.path.isdir(SCENARIOS_DIR), SCENARIOS_DIR)
        self.assertGreater(len(self.live), 1000)

    def test_every_objective_meets_the_exam_pool_floor(self):
        below = []
        for fname in sorted(os.listdir(CERT_DATA_DIR)):
            if not fname.endswith(".yaml"):
                continue
            with open(os.path.join(CERT_DATA_DIR, fname), "r", encoding="utf-8") as fh:
                spec = yaml.safe_load(fh) or {}
            for objective in spec.get("objectives", []):
                refs = objective.get("scenarios") or []
                live = [s for s in refs if s in self.live]
                if len(live) < EXAM_SCENARIOS_PER_OBJECTIVE:
                    below.append(
                        f"{fname}:{objective['code']} has {len(live)} live "
                        f"scenario(s), need {EXAM_SCENARIOS_PER_OBJECTIVE} "
                        f"(dead refs: {[s for s in refs if s not in self.live]})"
                    )
        self.assertEqual(below, [], "objectives below the exam-pool floor:\n" + "\n".join(below))


class ExamStartUnwinnableGuardTests(APITestCase):
    """ExamStartView must refuse a track whose ceiling is under passing_score."""

    def setUp(self):
        self.tech = Technology.objects.create(name="Linux Administration", slug="linux")
        # One real RHCSA slug so exactly one objective gets a non-empty pool.
        self.scenario = Scenario.objects.create(
            technology=self.tech,
            slug="broken-useradd",
            title="Broken Useradd",
            category="rhcsa",
            difficulty="medium",
            description="Test scenario.",
        )
        call_command("seed_certifications")
        self.track = CertificationTrack.objects.get(slug="rhcsa")
        # is_staff bypasses the cert paywall (services/access.py), keeping this
        # test about pool coverage rather than subscription plumbing.
        self.user = User.objects.create_user(
            username="pool-learner",
            email="pool-learner@example.com",
            password="pw-Str0ng!23",
            is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_start_refuses_when_ceiling_is_below_passing_score(self):
        # Only rhcsa.users has a live scenario here, so the reachable ceiling is
        # that objective's weight share — far under the 70% passing score.
        linked = TrackScenario.objects.filter(objective__track=self.track)
        self.assertEqual(linked.count(), 1)

        resp = self.client.post(f"/api/certifications/{self.track.slug}/exam/start/")
        self.assertEqual(resp.status_code, 503, resp.data)
        self.assertEqual(resp.data["code"], "CERT_EXAM_POOL_INCOMPLETE")
        self.assertLess(resp.data["max_achievable_score"], self.track.passing_score)

    def test_start_succeeds_once_every_objective_has_a_pool(self):
        # Give every objective one live scenario: ceiling returns to 100%.
        for objective in self.track.objectives.all():
            if objective.track_scenarios.exists():
                continue
            scenario = Scenario.objects.create(
                technology=self.tech,
                slug=f"filler-{objective.code}",
                title=f"Filler {objective.code}",
                category="rhcsa",
                difficulty="medium",
                description="Test scenario.",
            )
            TrackScenario.objects.create(
                objective=objective, scenario=scenario, order=0, in_exam_pool=True
            )

        resp = self.client.post(f"/api/certifications/{self.track.slug}/exam/start/")
        self.assertEqual(resp.status_code, 201, resp.data)
        served = {s["objective_code"] for s in resp.data["scenarios"]}
        self.assertEqual(served, {o.code for o in self.track.objectives.all()})
