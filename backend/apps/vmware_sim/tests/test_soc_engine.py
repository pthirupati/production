"""Tests for the SOC/SIEM console simulator (apps.vmware_sim.soc_engine).

Covers every `_apply_preset` kind (fail-closed before the fix, passing only
after) — closing the test-coverage gap where only quarantine/block_ip had
dedicated tests (see backend/tests/test_enterprise_sims.py) while
escalate/playbook/log-search/close/red-vs-blue had none.
"""

from django.core.cache import cache
from django.test import SimpleTestCase

from apps.vmware_sim import soc_engine as se


class SocEngineBase(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.sid = "soc-test-session"
        se.drop_session(self.sid)
        self.addCleanup(se.drop_session, self.sid)

    def _login(self, slug: str = ""):
        se._ensure(self.sid, slug)
        se.apply_action(self.sid, "login", {"user": "analyst"})


class LoginGateTests(SocEngineBase):
    def test_actions_require_login(self):
        se._ensure(self.sid, "")
        res = se.apply_action(self.sid, "acknowledge_alert", {"alert_id": "AL-1003"})
        self.assertFalse(res["ok"])
        self.assertIn("Sign in", res["error"])

    def test_login_then_action_succeeds(self):
        self._login()
        res = se.apply_action(self.sid, "acknowledge_alert", {"alert_id": "AL-1003"})
        self.assertTrue(res["ok"], res)


class QuarantinePresetTests(SocEngineBase):
    SLUG = "soc-ransomware-quarantine"

    def test_fails_before_and_passes_after(self):
        self._login(self.SLUG)
        ok, _ = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertFalse(ok)

        # This preset plants TWO broken markers (open_critical_alert AND
        # needs_quarantine) — quarantining alone is not enough, the alert
        # must also be closed.
        se.apply_action(self.sid, "quarantine_host", {"asset": "ws-finance-07"})
        ok_partial, _ = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertFalse(ok_partial)

        se.apply_action(self.sid, "close_incident", {"alert_id": "AL-1003"})
        ok2, msg = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertTrue(ok2, msg)


class BruteForcePresetTests(SocEngineBase):
    SLUG = "soc-brute-force-block-ip"

    def test_fails_before_and_passes_after(self):
        self._login(self.SLUG)
        ok, _ = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertFalse(ok)

        se.apply_action(self.sid, "block_ip", {"ip": "198.51.100.23"})
        se.apply_action(self.sid, "close_incident", {"alert_id": "AL-1002"})
        ok2, msg = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertTrue(ok2, msg)

    def test_blocking_wrong_ip_does_not_clear_the_fault(self):
        self._login(self.SLUG)
        se.apply_action(self.sid, "block_ip", {"ip": "1.2.3.4"})
        ok, _ = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertFalse(ok)


class EscalatePresetTests(SocEngineBase):
    SLUG = "soc-escalate-critical-alert"

    def test_fails_before_and_passes_after(self):
        self._login(self.SLUG)
        ok, _ = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertFalse(ok)

        res = se.apply_action(self.sid, "escalate_incident", {"alert_id": "AL-1003"})
        self.assertTrue(res["ok"], res)
        self.assertTrue(res.get("incident_id", "").startswith("INC-"))
        ok2, msg = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertTrue(ok2, msg)

    def test_escalating_unknown_alert_fails(self):
        self._login(self.SLUG)
        res = se.apply_action(self.sid, "escalate_incident", {"alert_id": "AL-9999"})
        self.assertFalse(res["ok"])


class PlaybookPresetTests(SocEngineBase):
    SLUG = "soc-execute-containment-playbook"

    def test_fails_before_and_passes_after(self):
        self._login(self.SLUG)
        ok, _ = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertFalse(ok)

        res = se.apply_action(self.sid, "run_playbook", {"playbook_id": "pb-malware-contain"})
        self.assertTrue(res["ok"], res)
        self.assertIn("Isolate host", res.get("steps", []))
        ok2, msg = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertTrue(ok2, msg)

    def test_running_unknown_playbook_fails(self):
        self._login(self.SLUG)
        res = se.apply_action(self.sid, "run_playbook", {"playbook_id": "pb-does-not-exist"})
        self.assertFalse(res["ok"])


class ThreatHuntPresetTests(SocEngineBase):
    SLUG = "soc-threat-hunt-attacker-ip"

    def test_fails_before_and_passes_after(self):
        self._login(self.SLUG)
        ok, _ = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertFalse(ok)

        res = se.apply_action(self.sid, "search_logs", {"query": "203.0.113.55"})
        self.assertTrue(res["ok"], res)
        self.assertGreater(len(res.get("results", [])), 0)
        ok2, msg = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertTrue(ok2, msg)

    def test_searching_unrelated_term_does_not_clear_the_fault(self):
        self._login(self.SLUG)
        se.apply_action(self.sid, "search_logs", {"query": "nonexistent-term"})
        ok, _ = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertFalse(ok)


class RedVsBluePresetTests(SocEngineBase):
    SLUG = "soc-red-vs-blue-dual-containment"

    def test_fails_before_and_requires_both_fixes(self):
        self._login(self.SLUG)
        ok, _ = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertFalse(ok)

        # Clearing only ONE of the two vectors must not pass yet.
        se.apply_action(self.sid, "quarantine_host", {"asset": "ws-finance-07"})
        ok_partial, _ = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertFalse(ok_partial)

        se.apply_action(self.sid, "block_ip", {"ip": "198.51.100.23"})
        ok2, msg = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertTrue(ok2, msg)

    def test_red_vs_blue_slug_is_not_misrouted_to_single_fix_branches(self):
        """A red-vs-blue slug must never fall into the quarantine-only or
        block-only branches (which would only set one broken key)."""
        entry = se._ensure(self.sid, self.SLUG)
        broken = entry["state"]["broken"]
        self.assertIn("needs_quarantine", broken)
        self.assertIn("needs_block_ip", broken)


class ClosePresetTests(SocEngineBase):
    SLUG = "soc-close-out-critical-alert"

    def test_fails_before_and_passes_after(self):
        self._login(self.SLUG)
        ok, _ = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertFalse(ok)

        res = se.apply_action(self.sid, "close_incident", {"alert_id": "AL-1003"})
        self.assertTrue(res["ok"], res)
        ok2, msg = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertTrue(ok2, msg)
