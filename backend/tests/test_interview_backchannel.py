"""P2.R2 backchannel picker."""

from django.test import SimpleTestCase

from apps.interviews.services.realism.backchannel import (
    BackchannelState,
    pick_backchannel,
)


class BackchannelTests(SimpleTestCase):
    def test_no_fire_until_sustained(self):
        st = BackchannelState()
        cue, st = pick_backchannel(st, now_ms=1000, speech_active=True, speech_started_at_ms=1000)
        self.assertIsNone(cue)
        cue, st = pick_backchannel(st, now_ms=3000, speech_active=True)
        self.assertIsNone(cue)

    def test_fires_after_threshold_and_throttles(self):
        import random

        rng = random.Random(0)
        st = BackchannelState()
        cue, st = pick_backchannel(
            st,
            now_ms=10_000,
            speech_active=True,
            speech_started_at_ms=1000,
            rng=rng,
        )
        self.assertIsNotNone(cue)
        first = cue
        cue2, st = pick_backchannel(
            st,
            now_ms=12_000,
            speech_active=True,
            rng=rng,
        )
        self.assertIsNone(cue2)  # throttle
        cue3, st = pick_backchannel(
            st,
            now_ms=30_000,
            speech_active=True,
            rng=rng,
        )
        self.assertIsNotNone(cue3)
        self.assertNotEqual(cue3, first)
