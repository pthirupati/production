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


class SocQueryLanguageTests(SimpleTestCase):
    """The SPL-subset parser itself, independent of session state."""

    def setUp(self):
        self.rows = se._base_state()["log_index"]

    def _q(self, query):
        return se.run_soc_query(self.rows, query)

    def test_bare_term_matches_substring_across_fields(self):
        self.assertEqual(len(self._q("203.0.113.55")), 1)

    def test_field_equality_is_field_scoped(self):
        # 'sshd' is the source of 3 rows, but it is not any row's host, so a
        # field-scoped query must not match the way a substring search would.
        self.assertEqual(len(self._q("source=sshd")), 3)
        self.assertEqual(len(self._q("host=sshd")), 0)

    def test_boolean_and_or_not_and_parentheses(self):
        self.assertEqual(len(self._q("host=web01 AND \"Failed password\"")), 3)
        self.assertEqual(len(self._q("host=web01 OR host=ws-finance-07")), 5)
        self.assertEqual(len(self._q("NOT host=web01")), 2)
        self.assertEqual(len(self._q("(host=web01 OR host=db01) AND admin")), 1)

    def test_implicit_and_between_juxtaposed_terms(self):
        self.assertEqual(len(self._q("host=web01 admin")), 1)

    def test_negation_operator_on_field(self):
        self.assertEqual(len(self._q("host!=web01")), 2)

    def test_wildcard_glob_matching(self):
        self.assertEqual(len(self._q("host=ws-*")), 2)
        self.assertEqual(len(self._q("powershell*")), 1)

    def test_lexicographic_comparison_on_iso_timestamps(self):
        self.assertEqual(len(self._q("time>2026-07-16T10:00:00Z")), 2)
        self.assertEqual(len(self._q("time<2026-07-16T10:00:00Z")), 3)

    def test_stats_count_and_group_by(self):
        self.assertEqual(self._q("source=sshd | stats count"), [{"count": 3}])
        self.assertEqual(self._q("source=sshd | stats count by host"), [{"host": "web01", "count": 3}])

    def test_fields_projection(self):
        rows = self._q("203.0.113.55 | fields host,message")
        self.assertEqual(set(rows[0].keys()), {"host", "message"})

    def test_head_tail_dedup_sort_rename(self):
        self.assertEqual(len(self._q("source=sshd | head 2")), 2)
        self.assertEqual(len(self._q("source=sshd | tail 1")), 1)
        # 3 sshd rows, but only 2 distinct messages.
        self.assertEqual(len(self._q("source=sshd | dedup message")), 2)
        newest = self._q("source=sshd | sort -time | head 1")[0]
        self.assertEqual(newest["time"], "2026-07-16T09:58:04Z")
        renamed = self._q("source=sshd | rename host as source_host | head 1")[0]
        self.assertIn("source_host", renamed)
        self.assertNotIn("host", renamed)

    def test_leading_pipe_uses_implicit_match_all(self):
        self.assertEqual(self._q("| stats count"), [{"count": 5}])

    def test_malformed_queries_raise_rather_than_matching_everything(self):
        for bad in (
            "host=",
            "| bogus",
            "((host=web01)",
            "| stats sum by host",
            "foo | where",
            "",
            "| fields",
            "| sort",
            "| dedup",
            "| rename host",
        ):
            with self.assertRaises(se.SocQueryError, msg=f"{bad!r} should not parse"):
                self._q(bad)


class SocLogSearchActionTests(SocEngineBase):
    """search_logs wiring: fail-closed on bad syntax, result-driven grading."""

    SLUG = "soc-threat-hunt-attacker-ip"

    def test_malformed_query_fails_and_does_not_clear_the_objective(self):
        self._login(self.SLUG)
        res = se.apply_action(self.sid, "search_logs", {"query": "host="})
        self.assertFalse(res["ok"])
        self.assertEqual(res["results"], [])
        self.assertIn("syntax error", res["error"])
        ok, _ = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertFalse(ok, "an unparseable query must never satisfy the hunt")

    def test_match_everything_query_does_not_clear_the_objective(self):
        """A wildcard that returns the whole index is not a hunt."""
        self._login(self.SLUG)
        res = se.apply_action(self.sid, "search_logs", {"query": "*"})
        self.assertTrue(res["ok"], res)
        self.assertEqual(len(res["results"]), 5)
        ok, _ = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertFalse(ok, "'*' returns every row and must not pass the hunt")

    def test_wrong_indicator_does_not_clear_the_objective(self):
        self._login(self.SLUG)
        # A valid, narrowing query — but for the brute-force IP, not the C2 IP.
        se.apply_action(self.sid, "search_logs", {"query": "198.51.100.23"})
        ok, _ = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertFalse(ok)

    def test_structured_query_for_the_target_clears_the_objective(self):
        """A field-scoped query is a *better* hunt than pasting the bare IP and
        must pass — the old grader only accepted the literal string."""
        self._login(self.SLUG)
        res = se.apply_action(
            self.sid, "search_logs", {"query": 'host=ws-finance-07 AND "203.0.113.55"'}
        )
        self.assertTrue(res["ok"], res)
        self.assertEqual(len(res["results"]), 1)
        ok, msg = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertTrue(ok, msg)

    def test_piped_query_for_the_target_clears_the_objective(self):
        self._login(self.SLUG)
        se.apply_action(self.sid, "search_logs", {"query": "203.0.113.55 | stats count by host"})
        ok, msg = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertTrue(ok, msg)

    def test_empty_query_is_rejected(self):
        self._login(self.SLUG)
        res = se.apply_action(self.sid, "search_logs", {"query": "   "})
        self.assertFalse(res["ok"])
        ok, _ = se.validate_soc_lab(self.sid, self.SLUG)
        self.assertFalse(ok)
