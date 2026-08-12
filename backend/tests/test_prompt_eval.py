"""Tests for rule-based prompt engineering grader.

NOTE: these were previously bare module-level functions, which Django's test
runner silently skipped (`manage.py test tests.test_prompt_eval` reported
"Ran 0 tests"). They are SimpleTestCase methods now so they actually execute.
"""

from django.test import SimpleTestCase

from apps.labs.prompt_eval import evaluate_course, evaluate_prompt


class PromptEvalBasicsTest(SimpleTestCase):
    def test_role_and_limit_pass(self):
        prompt = "You are a senior SRE. In 3 bullet points, list steps to restart nginx safely."
        chk = evaluate_prompt(prompt, {"require_any_role": True, "mentions_limit": True, "min_words": 8})
        self.assertTrue(chk.passed)
        self.assertGreaterEqual(chk.score, 80)

    def test_vague_prompt_fails(self):
        chk = evaluate_prompt("explain things", {"require_any_role": True, "min_words": 15})
        self.assertFalse(chk.passed)

    def test_course_all_exercises(self):
        config = {
            "exercises": [
                {"id": "a", "success": {"require_any_role": True, "min_words": 5}},
                {"id": "b", "success": {"mentions_limit": True, "min_words": 8}},
            ]
        }
        subs = {
            "a": "You are a tutor. Explain VPC peering.",
            "b": "Summarize in under 100 words with bullet points.",
        }
        verdict = evaluate_course(config, subs)
        self.assertTrue(verdict["all_passed"])
        self.assertEqual(verdict["passed_count"], 2)


class PromptEvalHintMatchingTest(SimpleTestCase):
    """Hint matching must be word-boundary, not raw substring.

    Every case below graded incorrectly under the old `needle in text` matching.
    """

    def test_role_hint_does_not_fire_on_incidental_substring(self):
        # 'as a ' matched inside 'was a '/'has a ', so almost any past-tense
        # sentence satisfied require_any_role.
        chk = evaluate_prompt(
            "this was a great outage and we learned many things about our systems today",
            {"require_any_role": True, "min_words": 10},
        )
        self.assertFalse(chk.passed)
        self.assertIn("assigns a role", chk.missing)

    def test_persona_hint_does_not_fire_on_personal(self):
        chk = evaluate_prompt(
            "give me personal advice about switching teams at work this quarter please",
            {"require_any_role": True, "min_words": 10},
        )
        self.assertFalse(chk.passed)

    def test_limit_hint_does_not_fire_inside_longer_words(self):
        # 'short' matched 'shortcoming', 'limit' matched 'limitations',
        # 'word' matched 'wording' — all false "states a limit" credit.
        for text in (
            "please rewrite this shortcoming report about our nginx outage using clear technical wording",
            "describe the limitations of this caching approach for our multi region deployment please",
        ):
            with self.subTest(text=text):
                chk = evaluate_prompt(text, {"mentions_limit": True, "min_words": 10})
                self.assertFalse(chk.passed)
                self.assertIn("states a length/format limit", chk.missing)

    def test_genuine_role_phrasings_are_accepted(self):
        # Real role assignments the hardcoded list used to reject outright.
        for text in (
            "Take on the identity of a veteran Kubernetes operator and diagnose this CrashLoopBackOff.",
            "Respond as a principal security engineer reviewing this Terraform plan for escalation risks.",
            "Answer from the perspective of a database reliability engineer debugging replication lag.",
        ):
            with self.subTest(text=text):
                chk = evaluate_prompt(text, {"require_any_role": True, "min_words": 10})
                self.assertTrue(chk.passed)

    def test_numeric_limit_counts_as_a_limit(self):
        # A cap expressed as number+unit is a real constraint even with no keyword.
        chk = evaluate_prompt(
            "You are an editor. Rewrite this outage report in 120 tokens for the exec summary.",
            {"mentions_limit": True, "min_words": 10},
        )
        self.assertTrue(chk.passed)


class PromptEvalSubstanceTest(SimpleTestCase):
    def test_gibberish_padding_does_not_satisfy_min_words(self):
        # A role phrase plus filler used to clear require_any_role + min_words.
        chk = evaluate_prompt(
            "you are xxx yyy zzz aaa bbb ccc ddd eee fff ggg hhh iii jjj",
            {"require_any_role": True, "min_words": 10},
        )
        self.assertFalse(chk.passed)
        self.assertIn("enough detail", chk.missing)

    def test_json_prompt_is_not_flagged_as_gibberish(self):
        # Structured-output answers are punctuation-heavy; they must still pass.
        chk = evaluate_prompt(
            'You are a data extractor. Return JSON only: {"name": string, "age": int}. No prose.',
            {"require_any_role": True, "min_words": 10, "requires_json_request": True},
        )
        self.assertTrue(chk.passed)


class PromptEvalAuthorTermsTest(SimpleTestCase):
    def test_author_supplied_terms_still_match_as_substrings(self):
        """require/any_of/must_contain_all MUST stay raw substring matches.

        These stems are taken verbatim from shipped prompt scenarios, and the
        wording below satisfies each one ONLY by substring: 'param' ->
        'parameter', 'class' -> 'classify', 'cite' -> 'cited', 'reason' ->
        'reasoning', 'valid' -> 'validation'. Applying the word-boundary matcher
        here (even with its optional trailing 's') would un-solve lessons across
        the ~150 prompt scenarios.
        """
        prompt = (
            "Classify each ticket, show your reasoning, list every cited source, "
            "and document each parameter used for validation."
        )
        chk = evaluate_prompt(
            prompt,
            {
                "require": [["param"]],
                "any_of": [["class"], ["cite"], ["reason"], ["valid"]],
                "min_words": 8,
            },
        )
        self.assertTrue(chk.passed, chk.missing)
