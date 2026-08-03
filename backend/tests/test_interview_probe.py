"""P2.R4 probing ladder."""

from django.test import SimpleTestCase

from apps.interviews.services.realism.probe import (
    ProbeAction,
    hint_line,
    move_on_line,
    narrow_prompt,
    next_probe_action,
)


class ProbeLadderTests(SimpleTestCase):
    def test_strong_advances(self):
        d, st = next_probe_action(question_key="q1", quality="strong")
        self.assertEqual(d.action, ProbeAction.ACK_ADVANCE)
        self.assertTrue(d.resolved)

    def test_weak_ladder_narrow_hint_move(self):
        st = {}
        d, st = next_probe_action(question_key="q1", quality="weak", probe_state=st)
        self.assertEqual(d.action, ProbeAction.NARROW)
        d, st = next_probe_action(question_key="q1", quality="wrong", probe_state=st)
        self.assertEqual(d.action, ProbeAction.HINT)
        d, st = next_probe_action(question_key="q1", quality="weak", probe_state=st)
        self.assertEqual(d.action, ProbeAction.MOVE_ON)
        self.assertFalse(d.resolved)

    def test_partial_single_hint(self):
        st = {}
        d, st = next_probe_action(question_key="q2", quality="partial", probe_state=st)
        self.assertEqual(d.action, ProbeAction.HINT)
        d, st = next_probe_action(question_key="q2", quality="partial", probe_state=st)
        self.assertEqual(d.action, ProbeAction.ACK_ADVANCE)

    def test_prompt_helpers(self):
        self.assertIn("simplify", narrow_prompt("How do you debug OOM?").lower())
        self.assertIn("Think", hint_line(["restart"]))
        self.assertTrue(move_on_line())
