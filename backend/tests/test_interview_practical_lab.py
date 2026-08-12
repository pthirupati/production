"""Tests for lab infrastructure type resolution and interview practical labs."""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.labs.infra import lab_infra_type


def _scenario(**kwargs):
    s = MagicMock()
    for k, v in kwargs.items():
        setattr(s, k, v)
    return s


class TestLabInfraType(TestCase):
    def test_simulation_lab_mode(self):
        s = _scenario(lab_mode="simulation", infrastructure_type="docker")
        self.assertEqual(lab_infra_type(s), "simulation")

    def test_sim_slug_fallback(self):
        s = _scenario(lab_mode="docker", slug="sim-rhel-ssh-stop", infrastructure_type="docker")
        self.assertEqual(lab_infra_type(s), "simulation")

    def test_terraform_simulation_type(self):
        s = _scenario(lab_mode="docker", simulation_type="terraform", infrastructure_type="docker")
        self.assertEqual(lab_infra_type(s), "simulation")

    def test_plain_scenario_defaults_to_simulation(self):
        # Prod never bakes per-scenario docker images, so an unresolved scenario
        # must route to the image-free simulation engine (not "docker", which
        # dead-ends in PROVISION_FAILED "Lab image not built on server").
        s = _scenario(lab_mode="docker", slug="nginx-down", infrastructure_type="docker")
        self.assertEqual(lab_infra_type(s), "simulation")

    def test_explicit_cloud_infra_preserved(self):
        for infra in ("aws_ec2", "digitalocean"):
            s = _scenario(lab_mode="docker", slug="cloud-lab", infrastructure_type=infra)
            self.assertEqual(lab_infra_type(s), infra)


class TestInterviewPracticalLab(TestCase):
    def test_start_uses_simulation_not_docker(self):
        from apps.interviews.models import InterviewCampaign, InterviewRound
        from apps.interviews.services import practical_lab as pl
        from apps.labs.models import LabSession
        from apps.question_bank.models import Scenario, Technology

        user = self._create_user()
        tech, _ = Technology.objects.get_or_create(slug="simulation", defaults={"name": "Simulation", "is_active": True})
        scenario, _ = Scenario.objects.get_or_create(
            slug="sim-rhel-ssh-stop",
            defaults={
                "title": "RHEL SSH Stop",
                "technology": tech,
                "category": "Fix",
                "difficulty": "easy",
                "description": "test",
                "lab_mode": "simulation",
                "simulation_type": "rhel",
                "infrastructure_type": "simulation",
                "is_active": True,
            },
        )
        scenario.lab_mode = "simulation"
        scenario.infrastructure_type = "simulation"
        scenario.save(update_fields=["lab_mode", "infrastructure_type"])

        campaign = InterviewCampaign.objects.create(user=user, title="Test", profile_snapshot={})
        round_obj = InterviewRound.objects.create(
            campaign=campaign,
            round_number=1,
            round_type="practical",
            title="Practical",
            status="in_progress",
        )
        from apps.interviews.models import InterviewMessage

        InterviewMessage.objects.create(
            round=round_obj,
            role="interviewer",
            message_type="practical",
            content="Start the lab",
            metadata={"practical_config": {"scenario_slug": "sim-rhel-ssh-stop"}},
        )

        # The session row is now created by start_practical_lab itself, inside the
        # atomic capacity block; only the provisioning half is stubbed out.
        with patch(
            "apps.interviews.services.practical_lab.provision_reserved_session",
            side_effect=lambda s: s,
        ) as mock_provision, patch(
            "apps.labs.start_gates.lab_start_block_reason",
            return_value=None,
        ):
            result = pl.start_practical_lab(user, round_obj)

        self.assertNotIn("error", result, result)
        session = LabSession.objects.get(id=result["session_id"])
        self.assertEqual(session.provider, "simulation")
        mock_provision.assert_called_once()

    def test_start_respects_global_capacity_cap(self):
        """Interview practical labs must honour MAX_CONCURRENT_LABS.

        Audit L1506/L1511: this path called start_lab_session() directly, which
        never consults at_global_capacity(), so interview labs could be started
        without limit even with the platform already at its ceiling. Regression
        guard: at cap, no new LabSession row may be created.
        """
        from apps.interviews.services import practical_lab as pl
        from apps.labs.models import LabSession

        user, round_obj, _scenario = self._practical_round(username="capuser")

        # Fill the platform to the ceiling with someone else's live lab.
        other = self._create_user(username="hog")
        filler_scenario = self._sim_scenario()
        LabSession.objects.create(
            user=other, scenario=filler_scenario, status="RUNNING", provider="simulation",
        )
        before = LabSession.objects.count()

        with self.settings(MAX_CONCURRENT_LABS=1), patch(
            "apps.interviews.services.practical_lab.provision_reserved_session",
            side_effect=AssertionError("must not provision when at capacity"),
        ), patch("apps.labs.start_gates.lab_start_block_reason", return_value=None):
            result = pl.start_practical_lab(user, round_obj)

        self.assertEqual(result.get("code"), "CAPACITY_FULL", result)
        # The gate must reject BEFORE the INSERT — no orphan row holding a slot.
        self.assertEqual(LabSession.objects.count(), before)
        round_obj.refresh_from_db()
        self.assertIsNone(round_obj.practical_lab_session_id)

    def test_failed_provision_releases_capacity_slot(self):
        """A provision failure must leave the row terminal, not PROVISIONING.

        Otherwise the dead row counts against count_active_engine_labs() forever
        and permanently shrinks the platform ceiling.
        """
        from apps.interviews.services import practical_lab as pl
        from apps.labs.models import LabSession

        user, round_obj, _scenario = self._practical_round(username="failuser")

        with patch(
            "apps.interviews.services.practical_lab.provision_reserved_session",
            side_effect=RuntimeError("engine down"),
        ), patch("apps.labs.start_gates.lab_start_block_reason", return_value=None):
            result = pl.start_practical_lab(user, round_obj)

        self.assertEqual(result.get("code"), "PROVISION_FAILED", result)
        session = LabSession.objects.filter(user=user).first()
        self.assertIsNotNone(session)
        # provision_reserved_session is mocked out here, so the caller is what we
        # assert on: it must not leave the round pointing at a dead session.
        round_obj.refresh_from_db()
        self.assertIsNone(round_obj.practical_lab_session_id)

    def test_provision_reserved_session_marks_failed_on_error(self):
        """The real provisioning helper flips the row to FAILED, freeing its slot."""
        from apps.interviews.services import practical_lab as pl
        from apps.labs.capacity import count_active_engine_labs
        from apps.labs.models import LabSession

        user = self._create_user(username="provuser")
        scenario = self._sim_scenario()
        session = LabSession.objects.create(
            user=user, scenario=scenario, status="PROVISIONING", provider="simulation",
        )
        self.assertEqual(count_active_engine_labs(), 1)

        broken = MagicMock()
        broken.provision.side_effect = RuntimeError("engine down")
        # Patched where it is *used*: the single implementation now lives in
        # apps.labs.sessions (shared with start_lab_session) and binds
        # get_provisioner at module import, so patching apps.labs.provisioner
        # would not reach it. Same mock, same assertions below.
        with patch("apps.labs.sessions.get_provisioner", return_value=broken):
            with self.assertRaises(RuntimeError):
                pl.provision_reserved_session(session)

        session.refresh_from_db()
        self.assertEqual(session.status, "FAILED")
        self.assertEqual(count_active_engine_labs(), 0)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _sim_scenario(self, slug="sim-rhel-ssh-stop"):
        from apps.question_bank.models import Scenario, Technology

        tech, _ = Technology.objects.get_or_create(
            slug="simulation", defaults={"name": "Simulation", "is_active": True}
        )
        scenario, _ = Scenario.objects.get_or_create(
            slug=slug,
            defaults={
                "title": "RHEL SSH Stop",
                "technology": tech,
                "category": "Fix",
                "difficulty": "easy",
                "description": "test",
                "lab_mode": "simulation",
                "simulation_type": "rhel",
                "infrastructure_type": "simulation",
                "is_active": True,
            },
        )
        return scenario

    def _practical_round(self, username):
        from apps.interviews.models import (
            InterviewCampaign,
            InterviewMessage,
            InterviewRound,
        )

        user = self._create_user(username=username)
        scenario = self._sim_scenario()
        campaign = InterviewCampaign.objects.create(user=user, title="T", profile_snapshot={})
        round_obj = InterviewRound.objects.create(
            campaign=campaign,
            round_number=1,
            round_type="practical",
            title="Practical",
            status="in_progress",
        )
        InterviewMessage.objects.create(
            round=round_obj,
            role="interviewer",
            message_type="practical",
            content="Start the lab",
            metadata={"practical_config": {"scenario_slug": scenario.slug}},
        )
        return user, round_obj, scenario

    def _create_user(self, username="labuser"):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        return User.objects.create_user(username=username, password="x")


class TestPracticalCodeSubmissionFile(TestCase):
    """The live_coding problem bank greps ``_submission.py``; it must exist.

    code_exec's python harness only writes ``_runner.py`` and exec()s the
    candidate's source from an in-memory string, so every test in
    live_coding.PROBLEM_SPECS used to raise FileNotFoundError and a perfect
    answer scored 0/N. practical_lab materialises the file for exactly those
    tests.
    """

    # A submission that satisfies the source-grep tests of all three problems.
    GOOD = (
        "import sys\n"
        "from collections import Counter\n"
        "gauge = 0\n"
        "def ready():\n"
        "    return 200, 503\n"
        "def parse():\n"
        "    try:\n"
        "        for line in sys.stdin:\n"
        "            pass\n"
        "    except Exception:\n"
        "        pass\n"
    )

    def _grade(self, answer, tests, language="python"):
        from apps.interviews.services.practical_lab import _grade_code_answer

        return _grade_code_answer(
            MagicMock(id=1), None, answer,
            {"language": language, "timeout": 10, "tests": tests},
        )

    def test_every_live_coding_problem_can_be_passed(self):
        from apps.labs.code_exec import language_runtime_available
        from apps.interviews.services.live_coding import PROBLEM_SPECS

        if not language_runtime_available("python"):
            self.skipTest("no python runtime for the sandbox")

        self.assertTrue(PROBLEM_SPECS, "problem bank is empty")
        for title, spec in PROBLEM_SPECS.items():
            code = spec.get("code") or {}
            with self.subTest(problem=title):
                result = self._grade(self.GOOD, code.get("tests") or [])
                self.assertTrue(
                    result["validated"],
                    f"{title} is unpassable: {result['feedback']}",
                )

    def test_wrong_answer_still_fails(self):
        """The shim must not turn grading into a rubber stamp."""
        from apps.labs.code_exec import language_runtime_available
        from apps.interviews.services.live_coding import PROBLEM_SPECS

        if not language_runtime_available("python"):
            self.skipTest("no python runtime for the sandbox")

        for title, spec in PROBLEM_SPECS.items():
            code = spec.get("code") or {}
            with self.subTest(problem=title):
                result = self._grade("x = 1\n", code.get("tests") or [])
                self.assertFalse(result["validated"], f"{title} passed an empty answer")

    def test_shim_only_added_when_tests_read_the_file(self):
        from apps.interviews.services.practical_lab import _needs_submission_file

        self.assertTrue(_needs_submission_file([{"code": "open('_submission.py').read()"}]))
        self.assertFalse(_needs_submission_file([{"code": "assert solve(1) == 2"}]))

    def test_shim_preserves_candidate_traceback_line_numbers(self):
        """Appended, not prepended — a runtime error must cite the real line."""
        from apps.interviews.services.practical_lab import _with_submission_file

        answer = "a = 1\nb = 2\nraise ValueError('boom')\n"
        shimmed = _with_submission_file(answer)
        self.assertTrue(shimmed.startswith(answer))
        self.assertEqual(shimmed.splitlines()[2], "raise ValueError('boom')")
