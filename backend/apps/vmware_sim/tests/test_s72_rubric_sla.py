"""Session 72: corpus reference scoring, ops ticket SLA clock."""

from django.test import SimpleTestCase

from apps.interviews.services.answer_corpus import best_reference_answer, parse_answer_text
from apps.interviews.services.conversation.scorer import compute_semantic_scores
from apps.vmware_sim.datacenter_physics_ops import (
    OPS_SLA_MINUTES,
    advance_ticket,
    build_ops_ticket,
    refresh_all_ticket_slas,
    refresh_ticket_sla,
)


class CorpusReferenceTests(SimpleTestCase):
    def test_best_reference_picks_overlapping_line(self):
        entries = parse_answer_text(
            "\n".join([
                "A: Check kubectl describe and logs for CrashLoopBackOff probe failures",
                "A: Prefer blue-green deploys with canaries for release risk",
                "A: RAID rebuilds need spare disks and write-hole awareness",
            ])
        )
        ref = best_reference_answer(
            "How do you debug a CrashLoopBackOff pod?",
            entries=entries,
        )
        self.assertIn("CrashLoopBackOff", ref)
        self.assertIn("kubectl", ref.lower())

    def test_good_answer_beats_bad_with_reference(self):
        q = "How do you debug a CrashLoopBackOff Kubernetes pod?"
        ref = (
            "Inspect kubectl describe events and container logs, look for OOMKilled "
            "or failing liveness probes, then fix the image tag or probe thresholds"
        )
        good = (
            "I run kubectl describe and logs, check for OOMKilled and failed "
            "liveness probes, then correct the image or probe config"
        )
        bad = "I enjoy collaborating with teammates and delivering soft skills"
        good_s = compute_semantic_scores(
            candidate_answer=good,
            question_text=q,
            round_type="technical",
            reference_text=ref,
        )
        bad_s = compute_semantic_scores(
            candidate_answer=bad,
            question_text=q,
            round_type="technical",
            reference_text=ref,
        )
        self.assertGreater(good_s["composite_score"], bad_s["composite_score"])
        self.assertGreater(good_s["relevance_score"], bad_s["relevance_score"])


class OpsTicketSlaTests(SimpleTestCase):
    def test_build_ticket_carries_sla_clock(self):
        t0 = 1_700_000_000.0
        ticket = build_ops_ticket(
            vendor="Dell",
            ticket_type="incident",
            asset_id="srv-r01-u08",
            hostname="esx01",
            component="psu",
            summary="PSU fault",
            priority="critical",
            now_ts=t0,
        )
        self.assertEqual(ticket["sla_minutes"], OPS_SLA_MINUTES["critical"])
        self.assertEqual(ticket["sla_remaining_sec"], OPS_SLA_MINUTES["critical"] * 60)
        self.assertFalse(ticket["sla_breached"])
        self.assertEqual(ticket["created_ts"], t0)

    def test_refresh_marks_breach_and_ticks_remaining(self):
        t0 = 1_700_000_000.0
        ticket = build_ops_ticket(
            vendor="HPE",
            ticket_type="incident",
            asset_id=None,
            hostname=None,
            component="fan",
            summary="Fan alarm",
            priority="high",
            now_ts=t0,
        )
        mid = t0 + 60 * 60  # 1h into a 4h SLA
        refresh_ticket_sla(ticket, now_ts=mid)
        self.assertFalse(ticket["sla_breached"])
        self.assertEqual(ticket["sla_remaining_sec"], 3 * 60 * 60)

        late = t0 + OPS_SLA_MINUTES["high"] * 60 + 5
        refresh_ticket_sla(ticket, now_ts=late)
        self.assertTrue(ticket["sla_breached"])
        self.assertEqual(ticket["sla_remaining_sec"], 0)
        self.assertTrue(any(h.get("event") == "sla_breached" for h in ticket["history"]))

    def test_escalate_tightens_sla_and_batch_refresh(self):
        t0 = 1_700_000_000.0
        ticket = build_ops_ticket(
            vendor="Dell",
            ticket_type="incident",
            asset_id="a1",
            hostname="h1",
            component="disk",
            summary="Disk fail",
            priority="medium",
            now_ts=t0,
        )
        advance_ticket(ticket, "escalate")
        self.assertEqual(ticket["priority"], "high")
        self.assertEqual(ticket["sla_minutes"], OPS_SLA_MINUTES["high"])

        state = {"tickets": [ticket]}
        # Force breach via created_ts in the past for the escalated window
        ticket["created_ts"] = t0 - OPS_SLA_MINUTES["high"] * 60 - 10
        newly = refresh_all_ticket_slas(state, now_ts=t0)
        self.assertEqual(len(newly), 1)
        self.assertTrue(ticket["sla_breached"])
