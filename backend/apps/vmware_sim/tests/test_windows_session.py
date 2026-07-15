"""Tests for the Windows engine's RDP / interactive-session lifecycle.

A signed-in session idles then auto-locks on wall-clock; a disconnected RDP
session logs off later. Time is patched via the engine's ``_now`` so tests run
instantly. The session block is not graded — these tests also confirm grading is
unaffected.
"""

from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim import windows_engine as win


class WindowsSessionLifecycleTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _session(self, slug="win-gui-unlock-ad-user"):
        sid = f"test-win-{slug}"
        win.drop_session(sid)
        win.get_state(sid, slug)
        return sid

    def test_login_sets_active_state_and_rdp_session(self):
        sid = self._session()
        base = 1_000_000.0
        with mock.patch.object(win, "_now", return_value=base):
            res = win.apply_action(sid, "login", {"rdp": True, "user": "CORP\\Administrator"})
            self.assertTrue(res["ok"], res)
            st = win.get_state(sid)
        self.assertEqual(st["session"]["state"], "active")
        self.assertEqual(st["session"]["logon_type"], "RemoteInteractive")
        interactive = [r for r in st["rdp_sessions"] if r["type"] != "Services"]
        self.assertTrue(interactive)
        self.assertEqual(interactive[0]["state"], "Active")

    def test_idle_then_auto_lock_over_wall_clock(self):
        sid = self._session()
        base = 2_000_000.0
        with mock.patch.object(win, "_now", return_value=base):
            win.apply_action(sid, "login", {})
        # Half the idle window -> idle (not yet locked).
        with mock.patch.object(win, "_now", return_value=base + win.SESSION_IDLE_LOCK_SECONDS / 2 + 1):
            st = win.get_state(sid)
            self.assertEqual(st["session"]["state"], "idle")
            self.assertFalse(st["session"]["locked"])
        # Past the full idle window -> auto-locked.
        with mock.patch.object(win, "_now", return_value=base + win.SESSION_IDLE_LOCK_SECONDS + 1):
            st = win.get_state(sid)
            self.assertTrue(st["session"]["locked"])
            self.assertEqual(st["session"]["state"], "locked")

    def test_activity_resets_idle_timer(self):
        sid = self._session()
        base = 3_000_000.0
        with mock.patch.object(win, "_now", return_value=base):
            win.apply_action(sid, "login", {})
        # Just before lock, a GUI action counts as activity and resets the timer.
        with mock.patch.object(win, "_now", return_value=base + win.SESSION_IDLE_LOCK_SECONDS - 1):
            win.apply_action(sid, "unlock_ad_user", {"user": "jsmith"})
        # A bit later (but < idle window since the action) it should NOT be locked.
        with mock.patch.object(win, "_now", return_value=base + win.SESSION_IDLE_LOCK_SECONDS + 1):
            st = win.get_state(sid)
            self.assertFalse(st["session"]["locked"])

    def test_disconnect_then_logoff_over_wall_clock(self):
        sid = self._session()
        base = 4_000_000.0
        with mock.patch.object(win, "_now", return_value=base):
            win.apply_action(sid, "login", {"rdp": True})
            res = win.apply_action(sid, "disconnect_rdp", {})
            self.assertTrue(res["ok"], res)
            st = win.get_state(sid)
            interactive = [r for r in st["rdp_sessions"] if r["type"] != "Services"]
            self.assertEqual(interactive[0]["state"], "Disconnected")
        with mock.patch.object(win, "_now", return_value=base + win.RDP_DISCONNECT_LOGOFF_SECONDS + 1):
            st = win.get_state(sid)
            interactive = [r for r in st["rdp_sessions"] if r["type"] != "Services"]
            self.assertEqual(interactive[0]["state"], "LoggedOff")

    def test_logout_drops_interactive_session(self):
        sid = self._session()
        win.apply_action(sid, "login", {"user": "CORP\\Administrator"})
        win.apply_action(sid, "logout", {})
        st = win.get_state(sid)
        self.assertEqual(st["session"]["state"], "logged_off")
        self.assertFalse(st["session"]["logged_in"])
        interactive = [r for r in st["rdp_sessions"] if r["type"] != "Services"]
        self.assertEqual(interactive, [])

    def test_services_session_always_present(self):
        sid = self._session()
        st = win.get_state(sid)
        self.assertTrue(any(r["type"] == "Services" for r in st["rdp_sessions"]))


class WindowsSessionGradingUnaffectedTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_unlock_user_grading_after_idle_lock(self):
        # Even if the admin's own session idle-locks, the graded fix (unlocking
        # jsmith) still passes — the session block is never inspected by the grader.
        sid = "win-grade-idle"
        win.drop_session(sid)
        win.get_state(sid, "win-gui-unlock-ad-user")
        base = 6_000_000.0
        with mock.patch.object(win, "_now", return_value=base):
            win.apply_action(sid, "login", {})
            win.apply_action(sid, "unlock_ad_user", {"user": "jsmith"})
            win.apply_action(sid, "enable_ad_user", {"user": "jsmith"})
        with mock.patch.object(win, "_now", return_value=base + win.SESSION_IDLE_LOCK_SECONDS + 100):
            win.get_state(sid)  # session idle-locks here
            ok, msg = win.validate_windows_lab(sid, "win-gui-unlock-ad-user")
            self.assertTrue(ok, msg)
