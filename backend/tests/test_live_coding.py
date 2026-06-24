"""Live coding engine tests."""

import random
import unittest

from django.test import SimpleTestCase


class LiveCodingEngineTest(SimpleTestCase):
    def test_signal_detection(self):
        from apps.interviews.services.live_coding import grade_by_signals, signal_hit_rate

        text = "from prometheus_client import Gauge, start_http_server"
        rate = signal_hit_rate(text, ["prometheus_client", "Gauge", "start_http_server"])
        self.assertGreaterEqual(rate, 0.66)
        result = grade_by_signals(text, ["prometheus_client", "Gauge"])
        self.assertTrue(result["validated"])

    def test_followup_cycles_phases(self):
        from apps.interviews.services.live_coding import generate_followup

        text, phase, _ = generate_followup(
            last_answer="I use Gauge and start_http_server from prometheus_client with statvfs",
            coding_title="Prometheus exporter",
            expected_signals=["prometheus_client", "Gauge"],
            phase="edge_case",
            used=set(),
            rng=random.Random(1),
        )
        self.assertTrue(len(text) > 10)
        self.assertIn(phase, ("complexity", "failure", "test", "readability", "edge_case"))

    def test_opening_includes_code_config(self):
        from apps.interviews.services.live_coding import generate_opening

        out = generate_opening(used=set(), rng=random.Random(2), difficulty=2)
        self.assertIsNotNone(out)
        text, cfg = out
        self.assertIn("coding", text.lower())
        self.assertEqual(cfg.get("kind"), "code")
        self.assertTrue(cfg.get("expected_signals"))

    def test_generator_live_coding_followup(self):
        from apps.interviews.services.question_generator import generate_question

        q = generate_question(
            round_type="live_coding",
            profile_snapshot={},
            difficulty=3,
            questions_asked=4,
            last_answer="def handler(): return 503 if not os.path.exists('/tmp/ready') else 200",
            last_answer_quality="adequate",
            category_preference="technical",
            last_question_kind="live_coding",
            last_practical_config={
                "coding_title": "K8s health sidecar",
                "expected_signals": ["HTTP", "200", "503"],
                "live_coding_phase": "edge_case",
                "kind": "code",
            },
        )
        self.assertIn(q.kind, ("live_coding_followup", "generated", "cross", "drill"))
