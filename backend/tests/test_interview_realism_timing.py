"""P2.R1 realism timing + framing beats."""

from django.test import SimpleTestCase

from apps.interviews.services.realism.framing import (
    framing_beat_sequence,
    framing_opener,
    framing_signoff,
)
from apps.interviews.services.realism.timing import compute_thinking_delay_ms
from apps.interviews.services.persona_style import thinking_delay_ms


class RealismTimingTests(SimpleTestCase):
    def test_delay_clamped_and_jittered(self):
        import random

        rng = random.Random(42)
        a = compute_thinking_delay_ms("technical", difficulty=2, rng=rng)
        b = compute_thinking_delay_ms("technical", difficulty=2, rng=rng)
        self.assertGreaterEqual(a, 500)
        self.assertLessEqual(a, 3500)
        self.assertGreaterEqual(b, 500)
        # Same seed stream → not identical consecutive draws after advancing rng
        self.assertNotEqual(a, b)

    def test_long_answer_and_probe_increase_delay(self):
        import random

        short = compute_thinking_delay_ms(
            "technical",
            difficulty=2,
            answer_text="yes",
            rng=random.Random(1),
        )
        long = compute_thinking_delay_ms(
            "technical",
            difficulty=2,
            answer_text=" ".join(["topology"] * 80),
            next_move="probe",
            rng=random.Random(1),
        )
        self.assertGreater(long, short)

    def test_scoring_elapsed_reduces_delay(self):
        import random

        base = compute_thinking_delay_ms(
            "deep_dive",
            difficulty=4,
            category="system_design",
            scoring_elapsed_ms=0,
            rng=random.Random(7),
        )
        reduced = compute_thinking_delay_ms(
            "deep_dive",
            difficulty=4,
            category="system_design",
            scoring_elapsed_ms=2800,
            rng=random.Random(7),
        )
        self.assertLess(reduced, base)

    def test_persona_style_delegates(self):
        import random

        d = thinking_delay_ms(
            "hr",
            difficulty=2,
            answer_text="I led a team of five",
            rng=random.Random(3),
        )
        self.assertGreaterEqual(d, 500)
        self.assertLessEqual(d, 3500)


class RealismFramingTests(SimpleTestCase):
    def test_framing_beats(self):
        beats = framing_beat_sequence(duration_minutes=45)
        self.assertEqual(len(beats), 2)
        self.assertTrue(beats[0]["content"])
        self.assertIn("minute", beats[1]["content"])
        self.assertTrue(framing_opener())
        self.assertTrue(framing_signoff())


class RealismPhrasingTests(SimpleTestCase):
    def test_opener_not_repeated(self):
        import random

        from apps.interviews.services.realism.phrasing import apply_variety, pick_opener

        rng = random.Random(11)
        used = []
        for _ in range(5):
            opener = pick_opener("strong", used, rng=rng)
            self.assertNotIn(opener, used)
            used.append(opener)
        text, used2 = apply_variety(
            "Let's dig into the failover path.",
            reaction="strong",
            used_openers=[],
            rng=random.Random(2),
        )
        self.assertTrue(text)
        self.assertEqual(len(used2), 1)


class RealismCallbackTests(SimpleTestCase):
    def test_extract_and_callback(self):
        import random

        from apps.interviews.services.realism.callbacks import (
            extract_callback_phrases,
            maybe_callback_opener,
            remember_phrases,
            phrases_from_meta,
        )

        phrases = extract_callback_phrases(
            "I would roll the nvidia driver with AWX across the MAAS inventory."
        )
        self.assertTrue(phrases)
        joined = " ".join(p.lower() for p in phrases)
        self.assertTrue("nvidia" in joined or "awx" in joined or "maas" in joined)
        meta = remember_phrases({}, phrases)
        self.assertEqual(phrases_from_meta(meta), phrases)
        cb = maybe_callback_opener(phrases, chance=1.0, rng=random.Random(1))
        self.assertIsNotNone(cb)
        self.assertTrue(any(p.lower() in cb.lower() for p in phrases))
