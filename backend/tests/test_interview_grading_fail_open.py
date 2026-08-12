"""Audit 2026-08 L329/L333/L336/L339: interview grading must not fail open.

Four interlocking defects made the grader decorative on the generated-question
path (no expected_keywords):

* L339 — topic was detected from ``f"{question} {answer}"``, so topic_detected was
  truthy for any answer to a topical question.
* L336 — with no keywords, quality == "strong" returned CORRECT unconditionally,
  and quality is length/structure driven, so fluent content-free prose graded
  correct.
* L333 — relevance was a TF-IDF cosine over a 2-document corpus. IDF is degenerate
  at n=2, so it reduced to shared-token overlap: it scored a genuine paraphrase
  near 0 and a bare keyword dump near 1.
* L329 — the anti-gaming multiplier keyed on ``word_count > 80 and relevance < 35``,
  which therefore punished long real answers and never fired on short stuffed ones.

The L336 fix left a residual hole on the same path: ``_detect_topic`` fires on the
question's own vocabulary echoed back, so a pure question-echo reached
quality == "adequate" with a truthy topic and still graded CORRECT. Closed by also
requiring the answer to clear ``CORRECTNESS_RELEVANCE_FLOOR`` — see
``EchoRelevanceFloorTest``.

Each test below fails if the corresponding fix is reverted. Fully offline.
"""

from django.test import SimpleTestCase

from apps.interviews.services.conversation.analysis import _relevance
from apps.interviews.services.conversation.scorer import compute_semantic_scores
from apps.interviews.services.scoring import (
    CORRECTNESS_CORRECT,
    CORRECTNESS_RELEVANCE_FLOOR,
    correctness_signal,
)

QUESTION = "How would you debug a Kubernetes pod that is stuck in CrashLoopBackOff?"

# A real answer that explains the method in its own words instead of echoing the
# prompt's vocabulary. This is the case the old TF-IDF scored at 3/100.
GENUINE_PARAPHRASE = (
    "I would begin by looking at the container runtime logs from the previous instance to see "
    "the exit reason, then check whether the process is being killed by the OOM handler by "
    "inspecting resource limits and the node memory pressure conditions. If the exit code is 1 "
    "rather than 137 I would suspect a configuration or dependency problem, so I would verify "
    "mounted secrets and config maps are present, confirm the readiness probe endpoint responds, "
    "and finally exec into an ephemeral debug container to reproduce the startup path by hand."
)

# Pure question-echo. No method, no content. The old TF-IDF scored this 100/100.
KEYWORD_STUFFED = "kubernetes pod stuck crashloopbackoff debug how would you"

# Fluent, well-structured, and completely content-free with respect to the
# question. This is what used to grade "correct".
CONTENT_FREE_FILLER = (
    "Well I think the fundamental thing here is that you really have to look at the whole "
    "picture and consider all the stakeholders involved. I ran into this before and we fixed "
    "it by working together as a team and we reduced the impact significantly which was a "
    "great result for everyone. It is about ownership and driving the outcome end to end and "
    "I deployed that approach broadly across the organisation."
)


class RelevanceSignalTest(SimpleTestCase):
    """L333 — relevance must reward substance, not question-echo."""

    def test_genuine_paraphrase_beats_keyword_stuffing(self):
        genuine = _relevance(GENUINE_PARAPHRASE, QUESTION)
        stuffed = _relevance(KEYWORD_STUFFED, QUESTION)
        self.assertGreater(
            genuine, stuffed,
            f"a real paraphrased answer ({genuine:.2f}) must be more relevant than a bare "
            f"keyword dump ({stuffed:.2f})",
        )

    def test_echoing_the_question_verbatim_is_not_full_relevance(self):
        # Repeating the prompt back scored a perfect 1.0 under 2-doc TF-IDF.
        self.assertLess(_relevance(QUESTION, QUESTION), 0.6)

    def test_buzzword_wall_scores_low(self):
        wall = (
            "scalable resilient cloud-native microservices architecture leveraging container "
            "orchestration synergy high-availability observability infrastructure automation "
        ) * 6
        self.assertLess(_relevance(wall, QUESTION), 0.35)

    def test_behavioral_answer_without_infra_vocabulary_still_scores(self):
        # Guards the domain-wordlist approach against zeroing out good STAR answers.
        behavioral_q = "Tell me about a time you had to resolve a conflict on your team."
        good = (
            "Two engineers disagreed on whether to roll back a release. I set up a short call, "
            "had each explain the risk they saw, and we agreed to roll back first and debate the "
            "fix after. The outage closed in twenty minutes and we wrote a postmortem."
        )
        empty = "I think conflict is really about communication and being a good listener honestly."
        self.assertGreater(_relevance(good, behavioral_q), _relevance(empty, behavioral_q))


class TopicDetectionTest(SimpleTestCase):
    """L339 — topic must come from the answer, not leak in from the question."""

    def test_topic_not_inherited_from_question(self):
        scored = compute_semantic_scores(
            candidate_answer=CONTENT_FREE_FILLER,
            question_text=QUESTION,
            round_type="technical",
            expected_keywords=None,
        )
        self.assertIsNone(
            scored["topic_detected"],
            "an answer that never mentions Kubernetes must not report a detected topic "
            "just because the question did",
        )

    def test_on_topic_answer_still_detects_topic(self):
        scored = compute_semantic_scores(
            candidate_answer=(
                "I'd run kubectl describe pod to read the events and exit code, then "
                "kubectl logs --previous for the crash reason."
            ),
            question_text=QUESTION,
            round_type="technical",
            expected_keywords=None,
        )
        self.assertEqual(scored["topic_detected"], "kubernetes")


class CorrectnessFailOpenTest(SimpleTestCase):
    """L336 — 'strong' quality alone must not grade an answer correct."""

    def test_strong_but_off_topic_is_not_correct(self):
        verdict = correctness_signal(
            answer_text=CONTENT_FREE_FILLER,
            quality="strong",
            keyword_hit_rate=0.0,
            has_keywords=False,
            topic_detected=None,
        )
        self.assertNotEqual(
            verdict, CORRECTNESS_CORRECT,
            "fluent prose with no on-topic content must not grade as correct",
        )

    def test_strong_and_on_topic_is_still_correct(self):
        self.assertEqual(
            correctness_signal(
                answer_text="kubectl describe pod, check exit code and liveness probe",
                quality="strong",
                keyword_hit_rate=0.0,
                has_keywords=False,
                topic_detected="kubernetes",
            ),
            CORRECTNESS_CORRECT,
        )

    def test_end_to_end_filler_does_not_grade_correct(self):
        """The full path an ungraded generated question actually takes."""
        scored = compute_semantic_scores(
            candidate_answer=CONTENT_FREE_FILLER,
            question_text=QUESTION,
            round_type="technical",
            expected_keywords=None,
        )
        verdict = correctness_signal(
            answer_text=CONTENT_FREE_FILLER,
            quality=scored["quality"],
            keyword_hit_rate=scored["keyword_hit_rate"],
            has_keywords=False,
            topic_detected=scored["topic_detected"],
        )
        self.assertNotEqual(verdict, CORRECTNESS_CORRECT)


class EchoRelevanceFloorTest(SimpleTestCase):
    """Residual L336 — an on-topic verdict must also clear the relevance floor.

    ``topic_detected`` is derived from the answer alone, but a candidate who hands
    the question straight back is technically "using" the topic's vocabulary, so
    ``_detect_topic`` returns "kubernetes" for KEYWORD_STUFFED with zero content of
    its own. That reached the quality == "adequate" branch and graded CORRECT.
    """

    # A genuine answer at the bottom of the length range — the case most at risk if
    # the floor is set too high.
    TERSE_GENUINE = "kubectl logs --previous and kubectl describe pod to see the exit code and events."

    def test_question_echo_does_not_grade_correct(self):
        """The exact reported repro, through the path a real answer takes."""
        scored = compute_semantic_scores(
            candidate_answer=KEYWORD_STUFFED,
            question_text=QUESTION,
            round_type="technical",
            expected_keywords=None,
        )
        # Preconditions: this answer clears every OTHER guard, so if the assertion
        # below ever passes for the wrong reason these will say so.
        self.assertEqual(scored["quality"], "adequate")
        self.assertTrue(
            scored["topic_detected"],
            "precondition: the echo still detects a topic — that is why the "
            "relevance floor is the guard being exercised here",
        )

        verdict = correctness_signal(
            answer_text=KEYWORD_STUFFED,
            quality=scored["quality"],
            keyword_hit_rate=scored["keyword_hit_rate"],
            has_keywords=False,
            topic_detected=scored["topic_detected"],
            relevance_score=scored["relevance_score"],
        )
        self.assertNotEqual(
            verdict, CORRECTNESS_CORRECT,
            f"echoing the question back (relevance {scored['relevance_score']}) must "
            f"not grade as correct",
        )

    def test_pure_echo_cannot_reach_the_floor(self):
        """Guards the floor's calibration against _relevance drifting under it.

        _relevance weights echo at 0.35 and gives the other 0.65 to substance, so a
        contentless answer caps at 35. The floor has to sit above that ceiling or
        the guard above is vacuous.
        """
        echo_relevance = round(_relevance(KEYWORD_STUFFED, QUESTION) * 100)
        self.assertLess(echo_relevance, CORRECTNESS_RELEVANCE_FLOOR)
        self.assertGreaterEqual(
            round(_relevance(self.TERSE_GENUINE, QUESTION) * 100),
            CORRECTNESS_RELEVANCE_FLOOR,
            "the floor must not be so high that a short but real answer trips it",
        )

    def test_terse_genuine_answer_still_grades_correct(self):
        scored = compute_semantic_scores(
            candidate_answer=self.TERSE_GENUINE,
            question_text=QUESTION,
            round_type="technical",
            expected_keywords=None,
        )
        self.assertEqual(
            correctness_signal(
                answer_text=self.TERSE_GENUINE,
                quality=scored["quality"],
                keyword_hit_rate=scored["keyword_hit_rate"],
                has_keywords=False,
                topic_detected=scored["topic_detected"],
                relevance_score=scored["relevance_score"],
            ),
            CORRECTNESS_CORRECT,
            "the floor must not cost real answers their verdict",
        )

    def test_floor_applies_to_strong_quality_too(self):
        """Padding an echo into "strong" must not buy back the correct verdict."""
        for quality in ("strong", "adequate"):
            with self.subTest(quality=quality):
                self.assertNotEqual(
                    correctness_signal(
                        answer_text=KEYWORD_STUFFED,
                        quality=quality,
                        keyword_hit_rate=0.0,
                        has_keywords=False,
                        topic_detected="kubernetes",
                        relevance_score=CORRECTNESS_RELEVANCE_FLOOR - 1,
                    ),
                    CORRECTNESS_CORRECT,
                )

    def test_relevance_is_not_required_when_the_caller_cannot_supply_it(self):
        """The interview_ai fallback scorer computes no relevance — stay topic-only."""
        self.assertEqual(
            correctness_signal(
                answer_text="kubectl describe pod, check exit code and liveness probe",
                quality="adequate",
                keyword_hit_rate=0.0,
                has_keywords=False,
                topic_detected="kubernetes",
            ),
            CORRECTNESS_CORRECT,
        )

    def test_keyword_path_is_unaffected_by_the_floor(self):
        """With expected keywords, hit rate remains the verdict — floor must not apply."""
        self.assertEqual(
            correctness_signal(
                answer_text=KEYWORD_STUFFED,
                quality="adequate",
                keyword_hit_rate=0.80,
                has_keywords=True,
                topic_detected="kubernetes",
                relevance_score=0,
            ),
            CORRECTNESS_CORRECT,
        )


class AntiGamingMultiplierTest(SimpleTestCase):
    """L329 — the penalty must key on relevance, not on length."""

    def _score(self, answer):
        return compute_semantic_scores(
            candidate_answer=answer,
            question_text=QUESTION,
            round_type="technical",
            expected_keywords=None,
        )

    def test_long_genuine_answer_outscores_short_stuffed_answer(self):
        genuine = self._score(GENUINE_PARAPHRASE)["composite_score"]
        stuffed = self._score(KEYWORD_STUFFED)["composite_score"]
        self.assertGreater(
            genuine, stuffed,
            f"long genuine answer ({genuine}) must outscore keyword stuffing ({stuffed})",
        )

    def test_penalty_does_not_depend_on_length(self):
        """Isolates the multiplier itself.

        Same irrelevant sentence repeated: the short and long variants have
        identical relevance, so the irrelevance penalty must apply to BOTH. Under
        the old `word_count > 80 and relevance < 35` rule only the long variant was
        multiplied by 0.55 — a pure length bias, since padding was the only
        difference. Asserting on the ratio (rather than raw scores) keeps this
        meaningful even though the absolute composites are small.
        """
        unit = (
            "Basically the important thing overall is really the approach and the "
            "mindset and the culture. "
        )
        short = self._score(unit)
        long = self._score(unit * 8)

        self.assertLess(short["word_count"], 80)
        self.assertGreater(long["word_count"], 80)
        # Both variants are equally irrelevant, so both must sit in the same band.
        self.assertLess(short["relevance_score"], 20)
        self.assertLess(long["relevance_score"], 20)

        # Padding an irrelevant answer to 8x its length must not multiply its score.
        self.assertLessEqual(
            long["composite_score"], short["composite_score"] + 4,
            f"padding an irrelevant answer (short={short['composite_score']}, "
            f"long={long['composite_score']}) must not be rewarded",
        )

    def test_long_genuine_answer_is_not_penalised_for_length(self):
        # >80 words and, under the old relevance, would have taken the 0.55 hit.
        scored = self._score(GENUINE_PARAPHRASE)
        self.assertGreater(scored["word_count"], 80)
        self.assertGreaterEqual(
            scored["relevance_score"], 35,
            "a genuine on-topic answer must clear the anti-gaming relevance floor",
        )


class DepthConcreteSignalTest(SimpleTestCase):
    """I1 — depth/concrete must not reward generic English stuffing."""

    def test_english_filler_does_not_max_depth(self):
        from apps.interviews.services.conversation.analysis import score_technical_depth

        stuffed = (
            "because specifically technically the reason second request when "
            "because specifically the reason underlying"
        )
        genuine_depth = score_technical_depth(GENUINE_PARAPHRASE)
        stuffed_depth = score_technical_depth(stuffed)
        self.assertGreater(
            genuine_depth, stuffed_depth,
            f"real explanation depth ({genuine_depth}) must beat English stuffing ({stuffed_depth})",
        )
        self.assertLess(stuffed_depth, 25)

    def test_bare_second_request_does_not_buy_concrete(self):
        from apps.interviews.services.conversation.analysis import score_concrete_evidence

        stuffed = "in a second the request when the second request when second"
        self.assertEqual(score_concrete_evidence(stuffed), 0)
        self.assertGreater(score_concrete_evidence(GENUINE_PARAPHRASE), 40)

    def test_composite_prefers_explanation_over_english_stuffing(self):
        stuffed = (
            "because specifically technically the reason second request when "
            "because specifically the reason underlying"
        )
        genuine = compute_semantic_scores(
            candidate_answer=GENUINE_PARAPHRASE,
            question_text=QUESTION,
            round_type="technical",
        )["composite_score"]
        fake = compute_semantic_scores(
            candidate_answer=stuffed,
            question_text=QUESTION,
            round_type="technical",
        )["composite_score"]
        self.assertGreater(
            genuine, fake,
            f"genuine composite ({genuine}) must beat English stuffing ({fake})",
        )
