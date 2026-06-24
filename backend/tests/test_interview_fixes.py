"""Interview resume score, practical lab metadata, and voice clarification tests."""

import unittest

from django.test import SimpleTestCase, TestCase, override_settings

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "iv-test"}}


class InterviewClarificationTest(SimpleTestCase):
    def test_clarify_probe_reasks_original_question(self):
        from apps.interviews.services.interview_ai import generate_clarify_probe

        q = "How would you debug elevated 5xx on an nginx ingress?"
        probe = generate_clarify_probe(candidate_answer="we use caching", question_text=q)
        self.assertIn("So again:", probe)
        self.assertIn(q, probe)

    def test_access_through_association_definition(self):
        from apps.interviews.services.interview_ai import generate_clarification_reply

        q = "Walk me through how you'd audit IAM permissions in AWS."
        reply = generate_clarification_reply(
            candidate_question="Can you go deeper on access through association with a real example?",
            question_text=q,
        )
        self.assertIn("Deployers", reply)
        self.assertIn("Alice", reply)
        self.assertIn(q, reply)

    def test_long_answer_with_iam_not_treated_as_question(self):
        from apps.interviews.services.interview_ai import is_candidate_question

        answer = (
            "I would audit IAM by listing users and roles, checking group membership, "
            "and tracing access through association — for example policies attached to "
            "groups rather than users directly?"
        )
        self.assertFalse(is_candidate_question(answer))

    def test_short_correct_answer_not_reprompted(self):
        from apps.interviews.services.engine import _should_reprompt_answer
        from apps.interviews.services.scoring import CORRECTNESS_CORRECT, score_answer

        class Q:
            question_text = "How do you restart nginx on a Linux host?"
            expected_keywords = ["systemctl", "restart", "nginx", "service"]
            technology_id = None

        result = score_answer(Q(), "Run systemctl restart nginx and verify with curl localhost.")
        self.assertIn(result["quality"], ("adequate", "strong", "brief"))
        self.assertFalse(_should_reprompt_answer(result, CORRECTNESS_CORRECT))

    def test_force_advance_moves_to_next_question(self):
        from apps.interviews.services.interview_ai import generate_unclear_audio_reply

        reply = generate_unclear_audio_reply(
            question_text="How do you debug a pod crash loop?",
            partial_transcript="",
        )
        self.assertIn("didn't catch", reply.lower())
        self.assertIn("crash loop", reply)

    def test_unclear_audio_reply_is_empathetic_not_judgmental(self):
        from apps.interviews.services.interview_ai import generate_unclear_audio_reply

        reply = generate_unclear_audio_reply(question_text="Explain IAM roles.")
        low = reply.lower()
        self.assertTrue(
            any(p in low for p in ("didn't catch", "trouble hearing", "lost you", "audio")),
            reply,
        )
        self.assertNotIn("wrong", low)
        self.assertNotIn("off-base", low)

    def test_synonym_keyword_matching(self):
        from apps.interviews.services.interview_ai import compute_answer_scores

        result = compute_answer_scores(
            candidate_answer="Um, I'd reboot the web server with systemd — service nginx restart.",
            question_text="How do you restart nginx?",
            round_type="technical",
            expected_keywords=["restart", "nginx", "systemctl"],
        )
        self.assertGreaterEqual(result["keyword_hit_rate"], 0.66)

    def test_transition_bridge_generated(self):
        from apps.interviews.services.interview_ai import generate_transition_bridge

        bridge = generate_transition_bridge(
            round_type="technical",
            quality="adequate",
            correctness="correct",
            conversation_tail=[],
        )
        self.assertTrue(len(bridge) > 5)

    def test_correct_brief_answer_gets_adequate_reaction_tone(self):
        from apps.interviews.services.interview_ai import generate_interviewer_reply

        reply = generate_interviewer_reply(
            persona_name="Alex",
            round_type="technical",
            question_text="How do you restart nginx?",
            candidate_answer="systemctl restart nginx",
            score_hint={"quality": "brief", "correctness": "correct"},
            profile_snapshot={},
            conversation_tail=[],
        )
        low = reply.lower()
        self.assertFalse(any(p in low for p in ("go deeper", "expand on that", "short answer")))

    def test_system_design_drills_missing_dimension(self):
        from apps.interviews.services.system_design import (
            detect_covered_dimensions,
            generate_system_design_question,
        )

        covered = detect_covered_dimensions("I'd use REST APIs and Postgres for storage")
        self.assertIn("api", covered)
        self.assertIn("data", covered)
        self.assertNotIn("capacity", covered)

        import random
        text, phase, kind = generate_system_design_question(
            last_answer="REST API with Postgres",
            active_prompt="Design a URL shortener for 100K RPS",
            phase="api",
            difficulty=3,
            used=set(),
            rng=random.Random(1),
        )
        self.assertTrue(len(text) > 20)
        self.assertIn(phase, ("capacity", "cache", "reliability", "api", "scale"))

    def test_persona_thinking_delay_scales_with_difficulty(self):
        from apps.interviews.services.persona_style import thinking_delay_ms

        easy = thinking_delay_ms("technical", difficulty=1, category="technical")
        hard = thinking_delay_ms("deep_dive", difficulty=5, category="system_design")
        self.assertLess(easy, hard)

    def test_phrase_coaching_references_candidate_words(self):
        from apps.interviews.services.coaching import build_phrase_coaching

        report = build_phrase_coaching(
            [
                {
                    "role": "candidate",
                    "content": "I would use circuit breakers on the payment API to stop cascading failures",
                    "score": 45,
                    "metadata": {"quality": "brief", "score": 45},
                },
            ],
            round_type="technical",
        )
        self.assertTrue(report["improvements"])
        self.assertTrue(
            any("circuit breaker" in imp.lower() for imp in report["improvements"]),
            report["improvements"],
        )

    def test_conversation_memory_threads_and_tone(self):
        from apps.interviews.services.conversation_intelligence import (
            empty_memory,
            infer_tone,
            update_memory,
            generate_thread_callback,
        )
        import random

        mem = empty_memory()
        mem = update_memory(
            mem,
            answer_text="Um, I would use kubectl get pods and check the nginx logs for 502 errors",
            score_result={"quality": "adequate", "score": 62},
            question_topic="kubernetes",
        )
        mem = update_memory(
            mem,
            answer_text="Like, we restart the deployment with kubectl rollout restart",
            score_result={"quality": "brief", "score": 48},
            question_topic="kubernetes",
        )
        self.assertIn("kubernetes", mem["topics_hit"])
        self.assertGreaterEqual(len(mem["phrases"]), 1)
        thread = generate_thread_callback(mem, set(), random.Random(1))
        self.assertTrue(thread is None or "Earlier" in thread or "earlier" in thread.lower())
        self.assertIn(
            infer_tone(answer_text="um uh like maybe", quality="brief", brief_streak=2, skipped_count=0),
            ("nervous", "frustrated"),
        )

    def test_incident_scenario_reveals_clues(self):
        import random
        from apps.interviews.services.incident_scenarios import generate_incident_turn, pick_scenario

        scen = pick_scenario(set(), random.Random(3))
        text, rev, phase = generate_incident_turn(
            scenario=scen, last_answer="", revealed_clues=0, phase="open", used=set(), rng=random.Random(3),
        )
        self.assertIn("first step", text.lower())
        text2, rev2, _ = generate_incident_turn(
            scenario=scen,
            last_answer="I would kubectl describe pod and check OOM",
            revealed_clues=rev,
            phase=phase,
            used=set(),
            rng=random.Random(4),
        )
        self.assertGreaterEqual(rev2, rev)

    def test_round_closing_generated(self):
        from apps.interviews.services.interview_ai import generate_round_closing

        line = generate_round_closing(round_type="technical", passed=True, memory={}, persona_name="Alex Chen")
        self.assertIn("Alex", line)

    def test_devops_debug_category_mix_is_incident_heavy(self):
        from apps.interviews.services.question_selector import round_category_mix

        after_intro = [round_category_mix("devops_debug", i) for i in range(2, 8)]
        self.assertTrue(all(c in ("scenario", "troubleshooting", "technical") for c in after_intro))

    def test_sre_oncall_prefers_sla_and_itil(self):
        from apps.interviews.services.question_selector import round_category_mix

        mix = {round_category_mix("sre_oncall", i) for i in range(2, 10)}
        self.assertIn("scenario", mix)
        self.assertTrue(mix & {"sla", "itil"})

    def test_eval_weights_shift_overall_for_oncall(self):
        from apps.interviews.services.scoring import aggregate_round_scores

        scores = [70.0, 75.0, 80.0]
        tech = aggregate_round_scores(scores, round_type="technical")
        oncall = aggregate_round_scores(scores, round_type="sre_oncall")
        self.assertNotEqual(tech["overall_score"], oncall["overall_score"])


class ResumeScoreWithoutFileTest(unittest.TestCase):
    def test_no_resume_returns_null_score(self):
        from apps.interviews.services.resume_parser import score_resume

        result = score_resume({}, resume_text="", target_technology="Linux", target_role="SRE")
        self.assertFalse(result["has_resume"])
        self.assertIsNone(result["overall_score"])
        self.assertEqual(result.get("message"), "No resume uploaded")


class PracticalLabMetadataTest(TestCase):
    @override_settings(CACHES=LOCMEM)
    def test_generated_practical_uses_message_metadata(self):
        from django.contrib.auth import get_user_model

        from apps.interviews.models import InterviewCampaign, InterviewMessage, InterviewRound
        from apps.interviews.services.practical_lab import (
            _current_practical_message,
            _practical_config_from_message,
            _practical_scenario_slug,
            validate_practical_answer,
        )

        User = get_user_model()
        user = User.objects.create_user(username="plab-meta", email="plab@example.com", password="x")
        campaign = InterviewCampaign.objects.create(user=user, title="t", experience_level="mid")
        rnd = InterviewRound.objects.create(campaign=campaign, round_number=1, round_type="technical")
        msg = InterviewMessage.objects.create(
            round=rnd,
            role="interviewer",
            content="Fix the service",
            message_type="practical",
            metadata={
                "practical_config": {
                    "kind": "command",
                    "scenario_slug": "sim-rhel-ssh-stop",
                    "validate_commands": ["systemctl start sshd"],
                },
            },
        )
        cfg = _practical_config_from_message(msg)
        self.assertEqual(cfg.get("scenario_slug"), "sim-rhel-ssh-stop")
        self.assertEqual(_current_practical_message(rnd).id, msg.id)
        self.assertEqual(_practical_scenario_slug(rnd), "sim-rhel-ssh-stop")
        result = validate_practical_answer(rnd, "systemctl start sshd")
        self.assertTrue(result["validated"])
        self.assertEqual(result["validation_key"], f"msg:{msg.id}")
