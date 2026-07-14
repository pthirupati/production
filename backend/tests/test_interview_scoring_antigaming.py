"""Audit P0-6 regression guard: interview scoring must not be gameable.

A long answer stuffed with topic buzzwords (and the hardcoded depth/concrete
keyword lists) must score STRICTLY BELOW a short, genuinely-correct answer.
Runs fully offline (spaCy model optional; TF-IDF fallback still applies).
"""

from django.test import SimpleTestCase


class AntiGamingScoringTest(SimpleTestCase):
    QUESTION = "How would you debug a Kubernetes pod stuck in CrashLoopBackOff?"

    def _score(self, answer):
        from apps.interviews.services.conversation.scorer import compute_semantic_scores

        return compute_semantic_scores(
            candidate_answer=answer,
            question_text=self.QUESTION,
            round_type="technical",
            expected_keywords=["kubectl", "logs", "describe", "probe", "exit code"],
        )

    def test_buzzword_dump_scores_below_correct_concise_answer(self):
        # Long jargon salad — buzzwords, no actual method. This is the gaming vector.
        buzzword = (
            "scalable resilient cloud-native microservices architecture leveraging "
            "container orchestration synergy high-availability observability "
            "infrastructure automation devops best-practices optimization throughput "
        ) * 6
        # Short but genuinely correct.
        correct = (
            "I'd run kubectl describe pod to read the events and the container exit "
            "code, then kubectl logs --previous to see why the last run crashed. "
            "Usually it's a bad command, a failing liveness probe, or a missing "
            "config/secret — I fix that and confirm the pod reaches Running."
        )
        b = self._score(buzzword)
        c = self._score(correct)
        self.assertLess(
            b["composite_score"], c["composite_score"],
            f"buzzword dump ({b['composite_score']}) must score below correct answer "
            f"({c['composite_score']})",
        )

    def test_correct_answer_scores_reasonably(self):
        # Floor is set for the offline TF-IDF relevance fallback used in CI. In
        # production the spaCy en_core_web_sm model (installed in the Dockerfile)
        # gives a stronger relevance signal and scores correct answers higher.
        c = self._score(
            "I'd run kubectl describe pod to read the events and exit code, then "
            "kubectl logs --previous for the crash reason, and check the liveness probe."
        )
        self.assertGreaterEqual(c["composite_score"], 40)
