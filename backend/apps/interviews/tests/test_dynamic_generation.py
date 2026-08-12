"""Tests for the DYNAMIC, generation-driven interview engine.

The interview bot no longer depends on the static admin-uploaded question bank
as its primary driver. Questions are GENERATED on the fly from the candidate's
answers + resume + chosen tech/level (``question_generator``), with the DB bank
demoted to a seed/supplement/safety-net.

These tests lock in the brief's three core guarantees, all on the FREE,
deterministic engine (no OpenAI/Anthropic / paid API):

  (a) an interview runs FULLY with an EMPTY question bank (pure generation),
  (b) follow-ups reference the candidate's OWN answer (cross-questioning),
  (c) difficulty ADAPTS upward after strong answers.

Plus unit coverage for the generator itself (resume→topics, determinism,
never-returns-None, no repeats).
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.interviews.models import (
    InterviewCampaign,
    InterviewEntitlement,
    InterviewMessage,
    InterviewQuestion,
    InterviewRound,
)
from apps.interviews.services import engine
from apps.interviews.services.entitlements import ensure_interview_defaults
from apps.interviews.services.question_generator import (
    GeneratedQuestion,
    generate_question,
    plan_round_topics,
    starting_difficulty,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# (a) Full interview with an EMPTY question bank — pure generation.
# ---------------------------------------------------------------------------

class EmptyBankInterviewTest(TestCase):
    """With ZERO ``InterviewQuestion`` rows, a round must still ask many
    questions, score answers, reply, and end with a report — entirely from
    generation. This proves the bank is no longer a hard dependency."""

    def setUp(self):
        ensure_interview_defaults()
        # Critical: blow away any seeded bank so we test pure generation.
        InterviewQuestion.objects.all().delete()
        self.user = User.objects.create_user(
            username="iv_empty", email="iv_empty@example.com", password="x"
        )
        ent, _ = InterviewEntitlement.objects.get_or_create(user=self.user)
        ent.is_complimentary = True
        ent.is_active = True
        ent.save()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _campaign(self):
        return InterviewCampaign.objects.create(
            user=self.user,
            title="empty-bank",
            status="in_progress",
            experience_level="senior",
            profile_snapshot={
                "experience_level": "senior",
                "years_experience": 7,
                "target_role": "SRE",
                "current_company": "Acme",
                "primary_technology_name": "Kubernetes",
                "secondary_technologies": ["Prometheus", "Terraform"],
                "resume_parsed": {
                    "skills_detected": ["kubernetes", "prometheus", "linux", "terraform"],
                    "years_experience_hint": 7,
                },
            },
        )

    def test_first_question_generated_with_empty_bank(self):
        self.assertEqual(InterviewQuestion.objects.count(), 0)
        camp = self._campaign()
        rnd = InterviewRound.objects.create(
            campaign=camp, round_number=1, round_type="technical",
            title="r", status="schedulable", duration_minutes=30,
        )
        engine.start_round(rnd)
        first_q = engine.ask_next_question(rnd)
        self.assertIsNotNone(first_q, "generation must produce a question with no bank")
        self.assertIn(first_q.message_type, ("question", "practical"))
        self.assertEqual(first_q.metadata.get("source"), "generated")
        self.assertTrue(first_q.content.strip())

    def test_full_round_runs_on_generation_only(self):
        camp = self._campaign()
        rnd = InterviewRound.objects.create(
            campaign=camp, round_number=1, round_type="technical",
            title="r", status="schedulable", duration_minutes=30,
        )
        engine.start_round(rnd)
        engine.ask_next_question(rnd)

        answers = [
            "I checked the pod logs and saw an OOMKill, so I looked at the memory limit "
            "and a recent cache TTL change that caused unbounded growth.",
            "I'd roll back the deploy first to stop the bleeding, then add a cache size cap "
            "and watch p99 latency and memory for 24 hours.",
            "For zero downtime I use a rolling update with readiness probes and an automatic "
            "rollback if error rate crosses the budget.",
            "I instrument with Prometheus, define SLOs on latency and error rate, and alert "
            "on user-facing impact rather than a single replica.",
            "I'd reproduce in staging, capture a heap profile, and compare against the last "
            "good release to isolate the regression.",
        ]
        for ans in answers:
            result = engine.submit_answer(rnd, ans, {"input_type": "text"})
            self.assertTrue(result["interviewer_reply"].content.strip())
            self.assertIn("score", result)

        rnd.refresh_from_db()
        # Many questions were asked, all generated (no bank rows exist at all).
        self.assertGreaterEqual(rnd.questions_asked, 5)
        self.assertEqual(InterviewQuestion.objects.count(), 0)
        generated = InterviewMessage.objects.filter(
            round=rnd, role="interviewer", message_type__in=("question", "practical")
        )
        self.assertGreaterEqual(generated.count(), 5)
        self.assertTrue(
            all(m.metadata.get("source") == "generated" for m in generated),
            "every question must be generated when the bank is empty",
        )

        # The round ends with a full report — the cycle is complete.
        out = engine.end_round(rnd, reason="completed")
        self.assertIn("report", out)
        self.assertIsNotNone(out["report"].overall_score)

    def test_message_endpoint_works_with_empty_bank(self):
        """End-to-end through the API: no bank, answer is scored, a reply and a
        next generated question come back."""
        camp = self._campaign()
        rnd = InterviewRound.objects.create(
            campaign=camp, round_number=1, round_type="technical",
            title="r", status="in_progress", duration_minutes=30,
        )
        # Seed an opening generated question to answer.
        engine.ask_next_question(rnd)
        resp = self.client.post(
            f"/api/interviews/rounds/{rnd.id}/message/",
            {
                "answer": "I restarted the nginx upstream and tuned the cache TTL to fix the 502s.",
                "input_type": "text",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data["interviewer_reply"]["content"])
        # A next question is generated (not pulled from an empty bank).
        if resp.data.get("next_question"):
            self.assertEqual(
                resp.data["next_question"]["metadata"].get("source"), "generated"
            )


# ---------------------------------------------------------------------------
# (b) Follow-ups reference the candidate's OWN answer (cross-questioning).
# ---------------------------------------------------------------------------

class FollowUpReferencesAnswerTest(TestCase):
    """A generated follow-up must quote/probe a phrase the candidate actually
    used — the 'you said X, how does that handle Y' human-interviewer move."""

    SNAP = {
        "experience_level": "mid",
        "primary_technology_name": "Kubernetes",
        "resume_parsed": {"skills_detected": ["kubernetes"], "years_experience_hint": 4},
    }

    def test_cross_question_quotes_candidate_phrase(self):
        # A distinctive technical bigram the candidate used must surface in the
        # next question. We try a few deterministic seeds (different conversation
        # states) and assert at least one cross-questions the phrase.
        found = False
        for i in range(8):
            q = generate_question(
                round_type="technical",
                profile_snapshot=self.SNAP,
                difficulty=3,
                questions_asked=i,
                last_answer="We tuned the cache TTL down to fix the memory leak in the pod.",
                last_answer_quality="strong",
                conversation_tail=[
                    {"role": "interviewer", "content": f"q{i}"},
                    {"role": "candidate", "content": "tuned cache ttl"},
                ],
            )
            if "cache ttl" in q.text.lower() or "memory leak" in q.text.lower():
                found = True
                # conversational_* kinds (grounded follow-ups from the services/
                # conversation engine) are valid alongside cross/drill/followup.
                self.assertTrue(
                    q.kind in ("cross", "drill", "followup") or (q.kind or "").startswith("conversational"),
                    f"unexpected follow-up kind: {q.kind!r}",
                )
                break
        self.assertTrue(found, "a follow-up must reference the candidate's own words")

    def test_followup_drills_the_topic_the_candidate_raised(self):
        # Candidate clearly talks Kubernetes -> the follow-up stays on Kubernetes
        # even though the round-level agenda might point elsewhere.
        q = generate_question(
            round_type="technical",
            profile_snapshot={"experience_level": "mid"},
            difficulty=2,
            questions_asked=3,
            last_answer=(
                "I debugged a CrashLoopBackOff by checking kubectl describe pod and the "
                "deployment readiness probe configuration."
            ),
            last_answer_quality="adequate",
            topic_agenda=["linux"],  # agenda says linux...
            conversation_tail=[{"role": "candidate", "content": "kubernetes crashloop"}],
        )
        # ...but generation follows the candidate onto kubernetes.
        self.assertEqual(q.topic, "kubernetes")

    def test_skipped_answer_does_not_quote(self):
        # No quoting/probing when the candidate skipped — we just move on.
        q = generate_question(
            round_type="technical",
            profile_snapshot=self.SNAP,
            difficulty=2,
            questions_asked=2,
            last_answer="",
            last_answer_quality="skipped",
        )
        self.assertNotIn("you said", q.text.lower())
        self.assertNotIn("you mentioned", q.text.lower())
        self.assertTrue(q.text.strip())

    def test_engine_followup_references_prior_answer_end_to_end(self):
        """Through the engine: after a substantive answer, the *next generated
        question* references the candidate's words (free, deterministic)."""
        InterviewQuestion.objects.all().delete()
        user = User.objects.create_user(
            username="iv_fu", email="iv_fu@example.com", password="x"
        )
        camp = InterviewCampaign.objects.create(
            user=user, title="t", status="in_progress", experience_level="mid",
            profile_snapshot=self.SNAP,
        )
        rnd = InterviewRound.objects.create(
            campaign=camp, round_number=1, round_type="technical",
            title="r", status="schedulable", duration_minutes=30,
        )
        engine.start_round(rnd)
        engine.ask_next_question(rnd)
        # Answer with a memorable, probe-worthy phrase several times; at least one
        # subsequent question should reference it.
        referenced = False
        for _ in range(5):
            res = engine.submit_answer(
                rnd,
                "I added a circuit breaker around the payment call and watched the error budget.",
                {"input_type": "text"},
            )
            nxt = res.get("next_question")
            reply = res["interviewer_reply"].content.lower()
            blob = (nxt.content.lower() if nxt else "") + " " + reply
            if "circuit breaker" in blob or "error budget" in blob:
                referenced = True
                break
        self.assertTrue(referenced, "follow-up/reply must reference the candidate's own phrase")


# ---------------------------------------------------------------------------
# (c) Difficulty adapts after strong answers.
# ---------------------------------------------------------------------------

class DifficultyAdaptsTest(TestCase):
    SNAP = {
        "experience_level": "mid",
        "primary_technology_name": "Kubernetes",
        "resume_parsed": {"skills_detected": ["kubernetes"]},
    }

    def test_generator_raises_difficulty_on_strong_streak(self):
        base = generate_question(
            round_type="technical", profile_snapshot=self.SNAP,
            difficulty=2, questions_asked=1, last_answer="ok", strong_streak=0,
        )
        hot = generate_question(
            round_type="technical", profile_snapshot=self.SNAP,
            difficulty=2, questions_asked=1, last_answer="ok", strong_streak=4,
        )
        self.assertGreater(
            hot.difficulty, base.difficulty,
            "a strong streak must escalate generated question difficulty",
        )

    def test_engine_bumps_difficulty_after_repeated_strong_answers(self):
        InterviewQuestion.objects.all().delete()
        user = User.objects.create_user(
            username="iv_diff", email="iv_diff@example.com", password="x"
        )
        camp = InterviewCampaign.objects.create(
            user=user, title="t", status="in_progress", experience_level="mid",
            profile_snapshot=self.SNAP,
        )
        rnd = InterviewRound.objects.create(
            campaign=camp, round_number=1, round_type="technical",
            title="r", status="schedulable", duration_minutes=40,
        )
        engine.start_round(rnd)
        rnd.refresh_from_db()
        start_difficulty = rnd.difficulty_level
        engine.ask_next_question(rnd)

        strong = (
            "When our cluster had an OOMKill incident, I was responsible for the fix. "
            "I rolled back the deploy, added a cache size limit, and as a result we cut "
            "the error rate to zero and shipped a postmortem with owners. I watched p99 "
            "latency and memory at 490Mi to confirm the fix held with zero downtime."
        )
        for _ in range(6):
            engine.submit_answer(rnd, strong, {"input_type": "text"})

        rnd.refresh_from_db()
        self.assertGreater(rnd.strong_answers_streak, 0)
        self.assertGreaterEqual(
            rnd.difficulty_level, start_difficulty + 1,
            "difficulty must increase after a run of strong answers",
        )

    def test_seniority_sets_starting_difficulty(self):
        self.assertLess(
            starting_difficulty({"experience_level": "junior"}),
            starting_difficulty({"experience_level": "lead"}),
        )
        # Many years overrides a modest level.
        self.assertGreaterEqual(
            starting_difficulty(
                {"experience_level": "mid", "resume_parsed": {"years_experience_hint": 11}}
            ),
            4,
        )


# ---------------------------------------------------------------------------
# Generator unit tests — resume→topics, determinism, never-None, no repeats.
# ---------------------------------------------------------------------------

class QuestionGeneratorUnitTest(TestCase):
    def test_plan_round_topics_from_resume(self):
        snap = {
            "primary_technology_name": "Kubernetes",
            "secondary_technologies": ["Terraform"],
            "resume_parsed": {"skills_detected": ["prometheus", "linux"]},
        }
        topics = plan_round_topics("technical", snap)
        self.assertEqual(topics[0], "kubernetes")  # primary tech first
        self.assertIn("monitoring", topics)        # prometheus -> monitoring
        self.assertIn("linux", topics)
        self.assertIn("terraform", topics)

    def test_hr_round_has_no_technical_agenda(self):
        self.assertEqual(plan_round_topics("hr", {"primary_technology_name": "Linux"}), [])

    def test_empty_resume_falls_back_to_default_agenda(self):
        topics = plan_round_topics("technical", {})
        self.assertTrue(topics, "must always have somewhere to drill")

    def test_generate_never_returns_none(self):
        # Even with no profile, no answer, no agenda — always a question.
        q = generate_question(
            round_type="technical", profile_snapshot={}, difficulty=2, questions_asked=0,
        )
        self.assertIsInstance(q, GeneratedQuestion)
        self.assertTrue(q.text.strip())

    def test_generation_is_deterministic_for_same_state(self):
        kwargs = dict(
            round_type="technical",
            profile_snapshot={"primary_technology_name": "Linux"},
            difficulty=2,
            questions_asked=3,
            last_answer="I checked the disk with df and du.",
            last_answer_quality="adequate",
            conversation_tail=[{"role": "candidate", "content": "disk full"}],
        )
        a = generate_question(**kwargs)
        b = generate_question(**kwargs)
        self.assertEqual(a.text, b.text, "same state must yield the same question (free + deterministic)")

    def test_seed_is_stable_across_interpreter_processes(self):
        """The seed must survive a *new interpreter*, not just a new call.

        ``_seed_from`` originally used Python's built-in ``hash()``, which is
        salted per-process by PYTHONHASHSEED. In-process determinism tests (the
        one above) pass happily under that bug because both calls share one
        salt; only a fresh interpreter exposes it. Audit §I8.

        We spawn two children with *explicitly different* PYTHONHASHSEED values
        rather than letting them inherit the parent's. If the runner is ever
        started with a fixed PYTHONHASHSEED (CI sometimes pins it for
        reproducibility), inherited children would share one salt and the test
        would silently prove nothing even with ``hash()`` restored.
        """
        import json as _json
        import os
        import subprocess
        import sys
        from pathlib import Path

        # apps/interviews/tests/<this file> -> backend/
        backend_root = Path(__file__).resolve().parents[3]
        probe = (
            "import sys, json;"
            f"sys.path.insert(0, {str(backend_root)!r});"
            "from apps.interviews.services.question_generator import _seed_from;"
            'print(json.dumps([_seed_from([{"role": "candidate", "content": "disk full on /var"}], 3),'
            ' _seed_from([], 0)]))'
        )

        seeds = []
        for hash_seed in ("1", "9999"):
            env = dict(os.environ, PYTHONHASHSEED=hash_seed)
            # Avoid pulling in the parent's Django settings module; the
            # generator is a pure module and imports without django.setup().
            env.pop("DJANGO_SETTINGS_MODULE", None)
            out = subprocess.run(
                [sys.executable, "-c", probe],
                capture_output=True, text=True, timeout=120, env=env, cwd=str(backend_root),
            )
            self.assertEqual(
                out.returncode, 0,
                f"seed probe failed under PYTHONHASHSEED={hash_seed}: {out.stderr[-2000:]}",
            )
            seeds.append(_json.loads(out.stdout.strip().splitlines()[-1]))

        self.assertEqual(
            seeds[0], seeds[1],
            "_seed_from must not depend on PYTHONHASHSEED — use blake2b, not hash()",
        )
        # Pinned blake2b values: catches a silent switch to any other salted or
        # version-dependent digest that would still be self-consistent above.
        self.assertEqual(seeds[0], [1115959761, 262550522])

    def test_generation_avoids_repeating_asked_questions(self):
        snap = {"primary_technology_name": "Linux"}
        asked: list[str] = []
        seen: set[str] = set()
        for i in range(6):
            q = generate_question(
                round_type="technical", profile_snapshot=snap,
                difficulty=2, questions_asked=i, last_answer="", asked_texts=asked,
            )
            self.assertNotIn(q.text, asked, "generator repeated a question already asked")
            asked.append(q.text)
            seen.add(q.text)
        self.assertGreater(len(seen), 1)

    def test_single_topic_many_empty_answers_never_repeats_verbatim(self):
        """The brutal case for the fallback path. A single-topic resume plus a long
        run of short/empty answers means nothing is ever 'substantive', so the
        cross-question / topic-drill / discussion branches never fire and EVERY turn
        falls through to the section-5 generic fallback. Across many turns within one
        round, no two interviewer questions may be verbatim-identical (normalized).

        This locks in FIX 4: (a) the 'absolute last resort' ``_pick`` must honor
        ``used`` (not an empty set) so it stops handing back already-asked bank
        questions, and (b) once the generic bank AND the open-ended pool are drained,
        the fallback must synthesize a rotating, non-repeating variant rather than
        returning one hardcoded line over and over.

        We empty the topic agenda so the run is driven purely by the generic
        fallback — the exact code path FIX 4 repairs — and feed back the running
        ``asked_texts`` the way the engine does. Pre-fix this yields only ~8 distinct
        questions out of 20 (the hardcoded prompt repeats up to 5x); post-fix all 20
        are distinct.
        """
        from apps.interviews.services.interview_ai import _normalize

        # Single-topic resume; the candidate barely engages, so the bot can never
        # cross-question or drill and must lean entirely on the generic fallback.
        snap = {
            "experience_level": "mid",
            "primary_technology_name": "Linux",
            "resume_parsed": {"skills_detected": ["linux"], "years_experience_hint": "4 years"},
        }
        # Short / empty answers — never "substantive", so no quotable phrase, no
        # topic detected from the answer. Mixed skipped/brief to be realistic.
        thin_answers = ["", "ok", "", "sure", "idk", "", "yes", "no", "", "maybe"]
        TURNS = 20
        asked: list[str] = []
        normalized_seen: list[str] = []
        for i in range(TURNS):
            q = generate_question(
                round_type="technical",
                profile_snapshot=snap,
                difficulty=2,
                questions_asked=i,
                last_answer=thin_answers[i % len(thin_answers)],
                last_answer_quality="skipped" if i % 2 == 0 else "brief",
                asked_texts=asked,
                # Empty agenda: no topic bank to fall back on, so generation is
                # forced down the section-5 generic path every single turn.
                topic_agenda=[],
                conversation_tail=[
                    {"role": "candidate", "content": thin_answers[i % len(thin_answers)]}
                ],
            )
            self.assertTrue(q.text.strip(), "fallback must always produce a non-empty question")
            asked.append(q.text)
            normalized_seen.append(_normalize(q.text))

        # The core guarantee: ZERO verbatim-duplicate questions across the round.
        dupes = sorted({t for t in normalized_seen if normalized_seen.count(t) > 1})
        self.assertEqual(
            len(set(normalized_seen)),
            TURNS,
            f"verbatim-duplicate question(s) asked within one round: {dupes}",
        )
        # And it must still be deterministic — re-running the identical sequence
        # reproduces the identical questions (no Date/random module calls).
        asked2: list[str] = []
        for i in range(TURNS):
            q2 = generate_question(
                round_type="technical",
                profile_snapshot=snap,
                difficulty=2,
                questions_asked=i,
                last_answer=thin_answers[i % len(thin_answers)],
                last_answer_quality="skipped" if i % 2 == 0 else "brief",
                asked_texts=asked2,
                topic_agenda=[],
                conversation_tail=[
                    {"role": "candidate", "content": thin_answers[i % len(thin_answers)]}
                ],
            )
            asked2.append(q2.text)
        self.assertEqual(asked, asked2, "fallback variation must be deterministic for the same state")

    def test_hr_round_generates_behavioral_not_kubectl(self):
        q = generate_question(
            round_type="hr",
            profile_snapshot={"experience_level": "mid"},
            difficulty=2,
            questions_asked=1,
            last_answer="I love working on reliable systems.",
            last_answer_quality="adequate",
            category_preference="behavioral",
        )
        self.assertIn(q.category, ("behavioral", "casual"))
        self.assertNotIn("kubectl", q.text.lower())

    def test_no_paid_api_imports(self):
        # The generator must be 100% free — no anthropic/openai client usage.
        # We check for actual imports / SDK calls, not prose (the module docstring
        # legitimately *mentions* "no OpenAI/Anthropic").
        import re as _re

        import apps.interviews.services.question_generator as gen

        src = open(gen.__file__).read()
        # Strip the module docstring + comments so we only inspect real code.
        code = _re.sub(r'""".*?"""', "", src, flags=_re.DOTALL)
        code = "\n".join(
            line.split("#", 1)[0] for line in code.splitlines()
        ).lower()
        for forbidden in ("import anthropic", "import openai", "anthropic.anthropic", "openai.openai", "api_key"):
            self.assertNotIn(forbidden, code, f"paid-API usage found: {forbidden!r}")
