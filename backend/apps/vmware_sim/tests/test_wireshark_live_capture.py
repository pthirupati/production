"""Tests for the Wireshark capture being fed by the learner's live nmap scans.

The wireshark and nmap engines share a LabSession id, so a scan run in the nmap
pane must show up on the wire in the capture pane. What this file mostly guards
is the *other* half of that: the five existing wireshark presets grade on the
fixed five-stream fixture, and folding in live scan traffic must not perturb any
of them. A scan probe landing on a graded port (80/443/22) would join the result
set of a documented filter like `tcp.port==80` and silently fail a lab the
learner solved correctly.
"""
from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim import nmap_engine as ne
from apps.vmware_sim import wireshark_engine as we

# The documented solve path for each preset, and the slug that selects it.
PRESET_SOLVES = {
    "wireshark-find-http-traffic": [("set_display_filter", {"filter": "http"})],
    "wireshark-isolate-conversation": [("set_display_filter", {"filter": "tcp.port==80"})],
    "wireshark-follow-stream": [("follow_tcp_stream", {"stream_id": 0})],
    "wireshark-fix-capture": [("set_capture_filter", {"filter": "tcp port 80"})],
    "wireshark-diagnose-tcp-rst": [
        ("set_display_filter", {"filter": "tcp.flags.reset==1"}),
        ("mark_packet", {"packet_no": 26}),
    ],
}


def _run_scan(session_id, flags=("-sS",)):
    ne.get_state(session_id, "nmap-open-ports")
    return ne.apply_action(session_id, "scan",
                           {"targets": "all", "flags": list(flags), "sudo": True})


class WiresharkFallbackTests(TestCase):
    """With no nmap session, the capture is exactly the fixed fixture."""

    def setUp(self):
        cache.clear()

    def test_wire_is_fixture_when_no_nmap_session(self):
        state = we.get_state("no-nmap", "wireshark-find-http-traffic")
        self.assertEqual(state["summary"]["wire_packets"], len(we._full_packet_set()))

    def test_no_derived_packets_before_any_scan(self):
        # An nmap session that exists but has run no scans puts nothing on the wire:
        # the fixture is the fallback, not a dead literal.
        ne.get_state("idle-nmap", "nmap-open-ports")
        state = we.get_state("idle-nmap", "wireshark-find-http-traffic")
        self.assertEqual(state["summary"]["wire_packets"], len(we._full_packet_set()))

    def test_malformed_nmap_session_does_not_break_capture(self):
        cache.set(ne._session_key("junk"), '{"state": {"discovered": "not-a-dict"}}', 60)
        state = we.get_state("junk", "wireshark-find-http-traffic")
        self.assertEqual(state["summary"]["wire_packets"], len(we._full_packet_set()))


class WiresharkLiveScanTrafficTests(TestCase):
    """A scan the learner actually ran must appear in the capture."""

    def setUp(self):
        cache.clear()

    def test_scan_adds_packets_to_the_wire(self):
        we.get_state("live", "wireshark-find-http-traffic")
        before = we.get_state("live", "")["summary"]["wire_packets"]
        self.assertTrue(_run_scan("live").get("ok"))
        after = we.get_state("live", "")["summary"]["wire_packets"]
        self.assertGreater(after, before)

    def test_derived_packets_come_from_discovered_hosts(self):
        we.get_state("live2", "wireshark-find-http-traffic")
        _run_scan("live2")
        state = we.get_state("live2", "")
        derived = [p for p in state["inventory"]["captured_packets"]
                   if (p["stream_id"] or 0) >= we._SCAN_STREAM_BASE]
        self.assertTrue(derived)
        scanner = ne._base_inventory()["scanner_ip"]
        # Every probe is between the scanner and a host nmap reported as up.
        discovered = set(ne.get_state("live2", "")["inventory"]
                         and [h["ip"] for h in ne.get_state("live2", "")["inventory"]["discovered_hosts"]])
        for p in derived:
            self.assertIn(scanner, (p["src"], p["dst"]))
            self.assertTrue(set((p["src"], p["dst"])) & discovered)

    def test_open_port_probe_gets_syn_ack(self):
        we.get_state("live3", "wireshark-find-http-traffic")
        _run_scan("live3")
        derived = [p for p in we.get_state("live3", "")["inventory"]["captured_packets"]
                   if (p["stream_id"] or 0) >= we._SCAN_STREAM_BASE]
        self.assertTrue(any("SYN, ACK" in (p["tcp_flags"] or "") for p in derived))

    def test_derived_packets_are_selectable_and_markable(self):
        we.get_state("live4", "wireshark-find-http-traffic")
        _run_scan("live4")
        derived = [p for p in we.get_state("live4", "")["inventory"]["captured_packets"]
                   if (p["stream_id"] or 0) >= we._SCAN_STREAM_BASE]
        no = derived[0]["no"]
        self.assertTrue(we.apply_action("live4", "select_packet", {"packet_no": no}).get("ok"))
        self.assertTrue(we.apply_action("live4", "mark_packet", {"packet_no": no}).get("ok"))


class WiresharkGradingUnaffectedTests(TestCase):
    """The load-bearing guarantee: live scan traffic changes no preset's grade."""

    def setUp(self):
        cache.clear()

    def test_scan_traffic_avoids_graded_ports(self):
        # This is the invariant that keeps `tcp.port==80` isolating one stream.
        we.get_state("ports", "wireshark-isolate-conversation")
        _run_scan("ports", flags=("-sS", "-sV"))
        derived = [p for p in we.get_state("ports", "")["inventory"]["captured_packets"]
                   if (p["stream_id"] or 0) >= we._SCAN_STREAM_BASE]
        self.assertTrue(derived)
        for p in derived:
            self.assertNotIn(p["src_port"], we._GRADED_PORTS)
            self.assertNotIn(p["dst_port"], we._GRADED_PORTS)

    def test_derived_streams_never_alias_fixture_streams(self):
        we.get_state("streams", "wireshark-isolate-conversation")
        _run_scan("streams")
        fixture_streams = {p["stream_id"] for p in we._full_packet_set()}
        derived = [p for p in we.get_state("streams", "")["inventory"]["captured_packets"]
                   if (p["stream_id"] or 0) >= we._SCAN_STREAM_BASE]
        for p in derived:
            self.assertNotIn(p["stream_id"], fixture_streams)

    def test_every_preset_grades_identically_with_and_without_scan_traffic(self):
        for slug, steps in PRESET_SOLVES.items():
            results = {}
            for scanned in (False, True):
                sid = f"grade-{slug}-{scanned}"
                we.get_state(sid, slug)
                if scanned:
                    _run_scan(sid, flags=("-sS", "-sV"))
                # A fresh session must always fail.
                self.assertFalse(we.validate_wireshark_lab(sid, slug)[0],
                                 f"{slug} passed before being solved (scanned={scanned})")
                for action, payload in steps:
                    self.assertTrue(we.apply_action(sid, action, payload).get("ok"),
                                    f"{slug}: action {action} failed (scanned={scanned})")
                ok, msg = we.validate_wireshark_lab(sid, slug)
                self.assertTrue(ok, f"{slug} unsolvable when scanned={scanned}: {msg}")
                results[scanned] = msg
            # Same grade AND same message (the messages embed packet counts, so
            # this catches scan traffic leaking into a graded result set).
            self.assertEqual(results[False], results[True],
                             f"{slug} grading message drifted once a scan ran")

    def test_isolate_conversation_still_sees_exactly_one_stream(self):
        sid = "isolate"
        we.get_state(sid, "wireshark-isolate-conversation")
        _run_scan(sid, flags=("-sS", "-sV"))
        we.apply_action(sid, "set_display_filter", {"filter": "tcp.port==80"})
        view = we.get_state(sid, "")["inventory"]["packets"]
        self.assertEqual({p["stream_id"] for p in view}, {0})

    def test_scan_rst_does_not_satisfy_the_rst_marking_lab(self):
        # nmap -sS tears down every half-open probe with a RST. Accepting one of
        # those would pass the lab without the learner finding the broken
        # conversation at all.
        sid = "rst"
        slug = "wireshark-diagnose-tcp-rst"
        we.get_state(sid, slug)
        _run_scan(sid)
        we.apply_action(sid, "set_display_filter", {"filter": "tcp.flags.reset==1"})
        scan_rsts = [p for p in we.get_state(sid, "")["inventory"]["packets"]
                     if (p["stream_id"] or 0) >= we._SCAN_STREAM_BASE
                     and "RST" in (p["tcp_flags"] or "")]
        self.assertTrue(scan_rsts, "expected the -sS scan to emit RST teardowns")
        we.apply_action(sid, "mark_packet", {"packet_no": scan_rsts[0]["no"]})
        self.assertFalse(we.validate_wireshark_lab(sid, slug)[0],
                         "marking a scan RST must not pass the lab")
        # The real culprit still does.
        we.apply_action(sid, "mark_packet", {"packet_no": 26})
        self.assertTrue(we.validate_wireshark_lab(sid, slug)[0])
