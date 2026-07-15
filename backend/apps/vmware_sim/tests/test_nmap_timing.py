"""Tests for the Nmap engine's input-scaled timing model + scan lifecycle.

Focus: the backend is the *authoritative* source of scan duration (scaled by
the -T template, host count, and port count), the new timing metadata is
surfaced on the scan result, and — critically — none of the timing work
changes what the scan DISCOVERS (grading must be unaffected).
"""
from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim import nmap_engine as ne


class ParseFlagsTimingTests(TestCase):
    def test_timing_template_parsed(self):
        for n in range(6):
            caps = ne._parse_flags([f"-T{n}"])
            self.assertEqual(caps["timing"], n)

    def test_timing_defaults_to_normal(self):
        self.assertEqual(ne._parse_flags(["-sV"])["timing"], 3)

    def test_fast_flag_parsed(self):
        self.assertTrue(ne._parse_flags(["-F"])["fast"])

    def test_all_ports_dash(self):
        caps = ne._parse_flags(["-p-"])
        self.assertTrue(caps["all_ports"])

    def test_all_ports_full_range(self):
        caps = ne._parse_flags(["-p", "1-65535"])
        self.assertTrue(caps["all_ports"])

    def test_explicit_ports_not_all(self):
        caps = ne._parse_flags(["-p", "22,80,443"])
        self.assertFalse(caps["all_ports"])
        self.assertEqual(caps["ports"], [22, 80, 443])

    def test_unknown_timing_token_ignored(self):
        # -T9 is not a real template; must not crash and stays at default.
        caps = ne._parse_flags(["-T9"])
        self.assertEqual(caps["timing"], 3)


class IntendedPortCountTests(TestCase):
    def test_all_ports(self):
        self.assertEqual(ne._intended_port_count(ne._parse_flags(["-p-"])), 65535)

    def test_fast(self):
        self.assertEqual(ne._intended_port_count(ne._parse_flags(["-F"])), 100)

    def test_explicit(self):
        self.assertEqual(
            ne._intended_port_count(ne._parse_flags(["-p", "22,80,443"])), 3)

    def test_default_top_ports(self):
        self.assertEqual(ne._intended_port_count(ne._parse_flags(["-sV"])), 1000)


class EstimateDurationTests(TestCase):
    def test_positive_and_clamped(self):
        d = ne.estimate_duration(ne._parse_flags(["-sV"]), 1)
        self.assertGreaterEqual(d, 1.2)
        self.assertLessEqual(d, 240.0)

    def test_faster_template_is_faster(self):
        slow = ne.estimate_duration(ne._parse_flags(["-T2", "-p", "1-65535"]), 4)
        fast = ne.estimate_duration(ne._parse_flags(["-T5", "-p", "1-65535"]), 4)
        self.assertGreater(slow, fast)

    def test_more_ports_is_slower(self):
        few = ne.estimate_duration(ne._parse_flags(["-T4", "-F"]), 2)
        many = ne.estimate_duration(ne._parse_flags(["-T4", "-p-"]), 2)
        self.assertGreater(many, few)

    def test_more_hosts_is_slower(self):
        one = ne.estimate_duration(ne._parse_flags(["-T4"]), 1)
        many = ne.estimate_duration(ne._parse_flags(["-T4"]), 50)
        self.assertGreater(many, one)

    def test_ping_sweep_cheaper_than_port_scan(self):
        sweep = ne.estimate_duration(ne._parse_flags(["-sn"]), 20)
        portscan = ne.estimate_duration(ne._parse_flags(["-sV", "-p-"]), 20)
        self.assertGreater(portscan, sweep)

    def test_deterministic(self):
        caps = ne._parse_flags(["-T4", "-sV", "-p", "1-1000"])
        self.assertEqual(
            ne.estimate_duration(caps, 10), ne.estimate_duration(caps, 10))

    def test_version_and_os_add_cost(self):
        plain = ne.estimate_duration(ne._parse_flags(["-T4", "-p", "22,80"]), 3)
        heavy = ne.estimate_duration(
            {**ne._parse_flags(["-T4", "-p", "22,80"]),
             "version": True, "os_detect": True}, 3)
        self.assertGreater(heavy, plain)


class ScanResultTimingTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_scan_result_exposes_timing_fields(self):
        ne._ensure_session("timing-sess-1", "open-ports")
        res = ne.apply_action("timing-sess-1", "scan", {
            "targets": "10.10.10.10", "flags": ["-sV", "-T4"], "sudo": False})
        scan = res["scan"]
        for key in ("duration", "timing", "port_count", "host_count"):
            self.assertIn(key, scan)
        self.assertEqual(scan["timing"], 4)
        self.assertEqual(scan["host_count"], 1)
        self.assertGreaterEqual(scan["duration"], 1.2)
        self.assertIn("seconds", scan["summary"])

    def test_duration_authoritative_matches_estimate(self):
        ne._ensure_session("timing-sess-2", "open-ports")
        res = ne.apply_action("timing-sess-2", "scan", {
            "targets": "10.10.10.0/24", "flags": ["-T4", "-F"], "sudo": False})
        scan = res["scan"]
        # The result's duration is exactly what estimate_duration would return
        # for the same effective caps + host count (backend owns the clock).
        caps = ne._parse_flags(["-T4", "-F"])
        caps["connect_scan"] = True  # default unprivileged technique
        expected = ne.estimate_duration(caps, scan["host_count"])
        self.assertEqual(scan["duration"], expected)


class GradingUnaffectedByTimingTests(TestCase):
    """Timing metadata must be display-only — discovery/grading unchanged."""

    def setUp(self):
        cache.clear()

    def test_open_ports_grading_still_passes(self):
        ne._ensure_session("grade-ports", "open-ports")
        ne.apply_action("grade-ports", "scan", {
            "targets": "10.10.10.10", "flags": ["-sV", "-T4"], "sudo": False})
        ok, _ = ne.validate_nmap_lab("grade-ports", "open-ports")
        self.assertTrue(ok)

    def test_live_hosts_grading_still_passes(self):
        ne._ensure_session("grade-hosts", "live-hosts")
        ne.apply_action("grade-hosts", "scan", {
            "targets": "all", "flags": ["-sn", "-T5"], "sudo": False})
        # -sn misses the icmp-blocked bastion; the four required hosts respond.
        ok, _ = ne.validate_nmap_lab("grade-hosts", "live-hosts")
        self.assertTrue(ok)

    def test_blocked_syn_grading_still_needs_sudo_syn(self):
        ne._ensure_session("grade-fw", "blocked-syn")
        # Unprivileged: 5432 stays filtered regardless of the -T template.
        ne.apply_action("grade-fw", "scan", {
            "targets": "10.10.10.20", "flags": ["-sV", "-T4"], "sudo": False})
        ok, _ = ne.validate_nmap_lab("grade-fw", "blocked-syn")
        self.assertFalse(ok)
        # Privileged SYN scan (fast template shouldn't change the outcome).
        ne.apply_action("grade-fw", "scan", {
            "targets": "10.10.10.20", "flags": ["-sS", "-T5"],
            "ports": "5432", "sudo": True})
        ok, _ = ne.validate_nmap_lab("grade-fw", "blocked-syn")
        self.assertTrue(ok)

    def test_ports_payload_field_scopes_scan(self):
        # The UI's dedicated `ports` field is folded into flags as -p <spec>,
        # so it scopes enumeration + timing (previously it was dropped).
        ne._ensure_session("ports-field", "open-ports")
        res = ne.apply_action("ports-field", "scan", {
            "targets": "10.10.10.10", "flags": ["-sV", "-T4"],
            "ports": "22,80,443", "sudo": False})
        self.assertEqual(res["scan"]["port_count"], 3)
        ok, _ = ne.validate_nmap_lab("ports-field", "open-ports")
        self.assertTrue(ok)

    def test_inline_ports_flag_takes_precedence_over_field(self):
        ne._ensure_session("ports-inline", "open-ports")
        res = ne.apply_action("ports-inline", "scan", {
            "targets": "10.10.10.10", "flags": ["-sV", "-p", "80"],
            "ports": "22,443", "sudo": False})
        # inline -p 80 wins; the field is not double-appended.
        self.assertEqual(res["scan"]["port_count"], 1)

    def test_no_ports_field_uses_default(self):
        ne._ensure_session("ports-none", "open-ports")
        res = ne.apply_action("ports-none", "scan", {
            "targets": "10.10.10.10", "flags": ["-sV"], "sudo": False})
        self.assertEqual(res["scan"]["port_count"], 1000)

    def test_fast_all_ports_flags_do_not_alter_discovered_state(self):
        # A -F or -p- flag changes timing but must not fabricate/omit findings
        # for known ports — web01 open ports are the same either way.
        ne._ensure_session("grade-eq-a", "open-ports")
        ne.apply_action("grade-eq-a", "scan", {
            "targets": "10.10.10.10", "flags": ["-sV"], "ports": "22,80,443",
            "sudo": False})
        state_a = ne.get_state("grade-eq-a", "open-ports")

        ne._ensure_session("grade-eq-b", "open-ports")
        ne.apply_action("grade-eq-b", "scan", {
            "targets": "10.10.10.10", "flags": ["-sV", "-T5"], "ports": "22,80,443",
            "sudo": False})
        state_b = ne.get_state("grade-eq-b", "open-ports")

        def open_ports(state):
            hosts = state["inventory"]["discovered_hosts"]
            return sorted(
                p["port"] for h in hosts for p in h["ports"]
                if p.get("state") == "open")

        self.assertEqual(open_ports(state_a), open_ports(state_b))


class PortTransitionLifecycleTests(TestCase):
    """A service a learner stops closes after a wall-clock delay; an immediate
    re-scan still shows it open, a later re-scan shows it closed. Grading is
    unaffected (it reads `discovered`, not ground truth)."""

    def setUp(self):
        cache.clear()

    def _observed(self, sid, ip, port, sudo=False):
        res = ne.apply_action(sid, "scan", {"targets": ip, "flags": ["-p", str(port)], "sudo": sudo})
        for h in res["scan"]["hosts"]:
            if h["ip"] == ip:
                for p in h["ports"]:
                    if p["port"] == port:
                        return p["state"]
        return None

    def test_stop_service_delays_then_closes_on_rescan(self):
        sid = "port-trans-1"
        ne._ensure_session(sid, "open-ports")
        base = 5_000_000.0
        # web01:80 starts open.
        with mock.patch.object(ne, "_now", return_value=base):
            self.assertEqual(self._observed(sid, "10.10.10.10", 80), "open")
            res = ne.apply_action(sid, "stop_service", {"ip": "10.10.10.10", "port": 80})
            self.assertTrue(res["ok"], res)
        # Immediately after: transition hasn't elapsed — still open.
        with mock.patch.object(ne, "_now", return_value=base + 1):
            self.assertEqual(self._observed(sid, "10.10.10.10", 80), "open")
        # After the delay: a re-scan reflects the closed port.
        with mock.patch.object(ne, "_now", return_value=base + ne.PORT_TRANSITION_SECONDS + 1):
            self.assertEqual(self._observed(sid, "10.10.10.10", 80), "closed")

    def test_start_service_opens_new_port_after_delay(self):
        sid = "port-trans-2"
        ne._ensure_session(sid, "open-ports")
        base = 6_000_000.0
        # Port 9000 not listening initially — start it.
        with mock.patch.object(ne, "_now", return_value=base):
            res = ne.apply_action(sid, "start_service",
                                  {"ip": "10.10.10.10", "port": 9000, "service": "custom"})
            self.assertTrue(res["ok"], res)
        with mock.patch.object(ne, "_now", return_value=base + ne.PORT_TRANSITION_SECONDS + 1):
            self.assertEqual(self._observed(sid, "10.10.10.10", 9000), "open")

    def test_pending_transitions_surfaced_in_state(self):
        sid = "port-trans-3"
        ne._ensure_session(sid, "open-ports")
        base = 7_000_000.0
        with mock.patch.object(ne, "_now", return_value=base):
            ne.apply_action(sid, "stop_service", {"ip": "10.10.10.10", "port": 443})
            st = ne.get_state(sid, "open-ports")
        pending = st["pending_transitions"]
        self.assertTrue(any(p["port"] == 443 and p["to"] == "closed" for p in pending))

    def test_grading_unaffected_by_stop_service(self):
        # Discovering the open ports still passes even after stopping one, because
        # grading reads what was DISCOVERED, not the live ground-truth port state.
        sid = "port-trans-grade"
        ne._ensure_session(sid, "open-ports")
        ne.apply_action(sid, "scan", {"targets": "10.10.10.10", "flags": ["-sV"],
                                      "ports": "22,80,443", "sudo": False})
        ne.apply_action(sid, "stop_service", {"ip": "10.10.10.10", "port": 80})
        ok, _ = ne.validate_nmap_lab(sid, "open-ports")
        self.assertTrue(ok)

    def test_stop_unknown_host_errors_gracefully(self):
        sid = "port-trans-err"
        ne._ensure_session(sid, "open-ports")
        res = ne.apply_action(sid, "stop_service", {"ip": "10.10.10.222", "port": 80})
        self.assertFalse(res["ok"])
