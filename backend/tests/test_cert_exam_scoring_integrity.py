"""Locks the three grading invariants in certifications.ExamSubmitView.

Every one of these fails OPEN: break it and scores only go UP, certificates
only get easier to earn, and nothing else in the suite notices. That is exactly
the shape of regression that ships silently, so each invariant gets a test that
fails when the corresponding line is relaxed.

  1. Window-scoped completions — only ``UserScenarioProgress`` rows completed
     DURING the attempt window count. Without ``since=attempt.started_at`` a
     candidate who solved the labs last month starts the exam pre-passed.
  2. DB-read objective weights — weights come from ``track.objectives`` at
     submit time, not from the snapshot stored in ``attempt.results``. The
     snapshot is user-adjacent JSON; trusting it makes the score forgeable.
  3. Full-weight denominator — the weighted sum divides by the FULL track
     weight, so an objective with no passed scenarios drags the total down.
     Dividing by only tested weight would let a cert be earned on partial
     objective coverage.
"""

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.certifications.models import (
    CertEarnedCertificate,
    CertObjective,
    CertificationTrack,
    ExamAttempt,
    TrackScenario,
)
from apps.progress.models import UserScenarioProgress
from apps.question_bank.models import Scenario, Technology

User = get_user_model()


class ExamScoringIntegrityTests(APITestCase):
    """Two equally-weighted objectives, one scenario each — 50 points apiece."""

    def setUp(self):
        self.tech = Technology.objects.create(name="Linux Administration", slug="linux")
        # passing_score 70 sits above a single objective's 50-point share, so
        # partial coverage can never pass while the denominator is correct.
        self.track = CertificationTrack.objects.create(
            slug="integrity-track",
            code="INTEG",
            name="Integrity Track",
            passing_score=70,
            exam_duration_minutes=60,
        )
        self.scenarios = {}
        for idx, code in enumerate(("integ.alpha", "integ.beta")):
            objective = CertObjective.objects.create(
                track=self.track, code=code, title=code, weight=1, order=idx
            )
            scenario = Scenario.objects.create(
                technology=self.tech,
                slug=f"scenario-{code.split('.')[-1]}",
                title=code,
                category="integrity",
                difficulty="medium",
                description="Test scenario.",
            )
            TrackScenario.objects.create(objective=objective, scenario=scenario, order=0)
            self.scenarios[code] = scenario

        # is_staff bypasses the cert paywall so these stay about grading.
        self.user = User.objects.create_user(
            username="integrity-learner",
            email="integrity-learner@example.com",
            password="pw-Str0ng!23",
            is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _start(self):
        resp = self.client.post(f"/api/certifications/{self.track.slug}/exam/start/")
        self.assertEqual(resp.status_code, 201, resp.data)
        return resp.data["id"]

    def _submit(self, attempt_id):
        resp = self.client.post(f"/api/certifications/exam/{attempt_id}/submit/")
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data

    def _complete(self, code, when):
        """Mark the objective's scenario complete at an explicit timestamp."""
        UserScenarioProgress.objects.update_or_create(
            user=self.user,
            scenario=self.scenarios[code],
            defaults={"completed": True, "best_score": 100, "completed_at": when},
        )

    def test_completions_before_the_attempt_do_not_count(self):
        """Invariant 1: pre-attempt solves must not pre-pass the exam."""
        # Both objectives solved a month before the attempt even starts.
        stale = timezone.now() - timezone.timedelta(days=30)
        self._complete("integ.alpha", stale)
        self._complete("integ.beta", stale)

        attempt_id = self._start()
        result = self._submit(attempt_id)

        self.assertEqual(result["score"], 0)
        self.assertEqual(result["status"], "failed")
        self.assertFalse(
            CertEarnedCertificate.objects.filter(user=self.user, track=self.track).exists(),
            "a certificate was issued for work done before the attempt began",
        )

    def test_completions_during_the_attempt_do_count(self):
        """Guards invariant 1 from the other side: in-window solves must score.

        Without this, deleting the completion lookup entirely would still pass
        the test above, and the window check would look correct while grading
        everyone at zero.
        """
        attempt_id = self._start()
        attempt = ExamAttempt.objects.get(id=attempt_id)
        during = attempt.started_at + timezone.timedelta(minutes=1)
        self._complete("integ.alpha", during)
        self._complete("integ.beta", during)

        result = self._submit(attempt_id)

        self.assertEqual(result["score"], 100)
        self.assertEqual(result["status"], "passed")

    def test_failed_objective_drags_the_score_down(self):
        """A served-but-failed objective still counts against the total."""
        attempt_id = self._start()
        attempt = ExamAttempt.objects.get(id=attempt_id)
        during = attempt.started_at + timezone.timedelta(minutes=1)
        # Only one of the two objectives is satisfied.
        self._complete("integ.alpha", during)

        result = self._submit(attempt_id)

        self.assertEqual(result["score"], 50)
        self.assertEqual(result["status"], "failed")
        self.assertFalse(
            CertEarnedCertificate.objects.filter(user=self.user, track=self.track).exists(),
            "a certificate was earned on partial objective coverage",
        )

    def test_unserved_objective_still_counts_against_the_score(self):
        """Invariant 3: the denominator is the FULL track weight.

        This is the only case where the full-weight denominator and a
        "tested weight only" denominator actually diverge. ``by_obj`` is keyed
        off SERVED scenarios, so a failed objective is still present and both
        denominators agree; they part ways only when an objective contributes
        no scenario to the exam at all. A third objective with an empty exam
        pool is exactly that, and it is the live shape of the bug the
        exam-pool-floor test guards statically.
        """
        # Start the attempt while the track is still fully covered:
        # ExamStartView refuses to sell an attempt whose ceiling is under the
        # passing score, which is the FIRST line of defence against this bug.
        # The objective is added afterwards to isolate the grading math -- the
        # same state an already-running attempt lands in when a scenario is
        # unpublished mid-exam.
        attempt_id = self._start()
        attempt = ExamAttempt.objects.get(id=attempt_id)
        CertObjective.objects.create(
            track=self.track, code="integ.gamma", title="integ.gamma", weight=1, order=2
        )
        during = attempt.started_at + timezone.timedelta(minutes=1)
        self._complete("integ.alpha", during)
        self._complete("integ.beta", during)

        served = {s["objective_code"] for s in attempt.results["scenarios"]}
        self.assertNotIn("integ.gamma", served)

        result = self._submit(attempt_id)

        # Full-weight denominator: 2 of 3 objective weights -> 67, no cert.
        # Tested-weight-only would score a perfect 100 and issue one.
        self.assertEqual(result["score"], 67)
        self.assertEqual(result["status"], "failed")
        self.assertFalse(
            CertEarnedCertificate.objects.filter(user=self.user, track=self.track).exists(),
            "a certificate was earned without covering every objective",
        )

    def test_weights_come_from_the_db_not_the_attempt_snapshot(self):
        """Invariant 2: a tampered snapshot weight must not move the score."""
        attempt_id = self._start()
        attempt = ExamAttempt.objects.get(id=attempt_id)
        during = attempt.started_at + timezone.timedelta(minutes=1)
        self._complete("integ.alpha", during)

        # Forge the stored snapshot so the solved objective claims to be worth
        # far more than the DB says. Reading weights from here would score 99+.
        scenarios = attempt.results["scenarios"]
        for entry in scenarios:
            if entry["objective_code"] == "integ.alpha":
                entry["weight"] = 999
        attempt.results["scenarios"] = scenarios
        attempt.save(update_fields=["results"])

        result = self._submit(attempt_id)

        self.assertEqual(result["score"], 50)
        self.assertEqual(result["status"], "failed")
