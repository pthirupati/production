"""The grader-integrity gate must actually cover coding labs.

`scan_grader_integrity.py` classifies a scenario by executing its
`validation_script`. Coding labs have none — they grade through
`coding_spec.visible_tests` / `hidden_tests` — so every one of them fell through to
NO-MATCH: counted in the total, never assessed, while the gate printed
"PASS: no fail-open graders". That is how `assert callable(solution)` (true even when
the stub raises, so the lab grades as solved having done nothing) survived across 307
labs in a repo that runs this gate on every PR.

These tests pin the coding-lab classifier so the blind spot cannot reopen, and pin
the two false-positive traps found while building it:
  * `kind: prompt` labs are graded by the Prompt Playground, not by these tests, and
    many carry a vestigial `assert True` in hidden_tests — judging them would have
    produced 150 false alarms.
  * multi-statement test bodies are doing real work and must not be called weak.
"""
import functools
import importlib.util
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

_SCRIPT = Path(settings.BASE_DIR).parent / "scripts" / "scan_grader_integrity.py"


def _load():
    spec = importlib.util.spec_from_file_location("_sgi_under_test", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_sgi = _load()


@functools.lru_cache(maxsize=1)
def _catalogue():
    """Walk the 7k-file scenario tree once — it is ~30s per pass."""
    return tuple(_sgi._iter_coding_from_fs())


def _spec(visible=None, hidden=None, **extra):
    out = {"visible_tests": visible or [], "hidden_tests": hidden or []}
    out.update(extra)
    return out


def _t(code, name="t"):
    return {"name": name, "code": code}


class AssertionClassifierTests(SimpleTestCase):
    def test_callable_only_is_fail_open(self):
        """`callable(f)` is true even when f's body raises — no work required."""
        self.assertEqual(_sgi._classify_assertion("assert callable(solution)"), "fail-open")

    def test_bare_name_not_none_is_fail_open(self):
        """The function object is never None, so this asserts nothing."""
        self.assertEqual(_sgi._classify_assertion("assert solution is not None"), "fail-open")

    def test_assert_true_is_fail_open(self):
        self.assertEqual(_sgi._classify_assertion("assert True"), "fail-open")

    def test_empty_body_is_fail_open(self):
        self.assertEqual(_sgi._classify_assertion(""), "fail-open")
        self.assertEqual(_sgi._classify_assertion("pass"), "fail-open")

    def test_calling_but_only_not_none_is_decorative(self):
        """Calls the entrypoint, but `return 1` satisfies it."""
        self.assertEqual(
            _sgi._classify_assertion("assert solution() is not None"), "decorative"
        )

    def test_truthy_return_is_decorative(self):
        self.assertEqual(_sgi._classify_assertion("assert solution()"), "decorative")

    def test_real_assertion_is_graded(self):
        self.assertEqual(
            _sgi._classify_assertion("assert solution(2, 3) == 5"), "graded"
        )

    def test_multi_statement_body_is_graded(self):
        """A body doing setup + assertions is real work; never call it weak."""
        body = "got = solution([3, 1, 2])\nassert got == [1, 2, 3]"
        self.assertEqual(_sgi._classify_assertion(body), "graded")

    def test_whitespace_does_not_change_the_verdict(self):
        self.assertEqual(
            _sgi._classify_assertion("  assert   callable( solution )  "), "fail-open"
        )


class CodingSpecClassifierTests(SimpleTestCase):
    def test_all_fail_open_tests_classify_fail_open(self):
        cls, _ = _sgi.classify_coding(
            _spec(visible=[_t("assert callable(solution)")],
                  hidden=[_t("assert callable(solution)")])
        )
        self.assertEqual(cls, "CODING-FAIL-OPEN")

    def test_the_307_shape_classifies_decorative(self):
        """The exact shape of the 307 labs after the callable->is-not-None sweep."""
        cls, detail = _sgi.classify_coding(
            _spec(visible=[_t("assert solution() is not None", "placeholder")],
                  hidden=[_t("assert solution() is not None", "placeholder_hidden")])
        )
        self.assertEqual(cls, "CODING-DECORATIVE")
        self.assertIn("placeholder", detail)

    def test_one_real_hidden_test_is_enough_to_be_graded(self):
        """A weak visible test is fine when a hidden test constrains the answer."""
        cls, _ = _sgi.classify_coding(
            _spec(visible=[_t("assert callable(solution)")],
                  hidden=[_t("assert solution(2) == 4")])
        )
        self.assertEqual(cls, "CODING-GRADED")

    def test_no_tests_at_all_is_flagged(self):
        cls, detail = _sgi.classify_coding(_spec())
        self.assertEqual(cls, "CODING-NO-TESTS")
        self.assertIn("no visible_tests", detail)


class PromptLabExclusionTests(SimpleTestCase):
    """`kind: prompt` labs must be excluded — ValidateLabView short-circuits them to
    the Prompt Playground before run_validation, so their vestigial `assert True`
    never grades anything. Including them produced 150 false positives (50 read as
    fail-open, 100 as no-tests)."""

    def test_prompt_labs_are_not_scanned(self):
        slugs = {slug for slug, _tech, _spec in _catalogue()}
        self.assertNotIn("prompt-fundamentals", slugs)
        self.assertNotIn("zero-shot-vs-few-shot", slugs)

    def test_non_prompt_coding_labs_are_scanned(self):
        """Fixture note: this used to pin `ai-ml-lab-15`, which was one of the 307
        empty labs later shipped `is_active: false` — the scanner now correctly skips
        unpublished scenarios, so that assertion went stale. Pinned to a lab with a
        real grader instead, which is what the test was always trying to express."""
        slugs = {slug for slug, _tech, _spec in _catalogue()}
        self.assertIn("aiml-cosine-similarity", slugs, "a real coding lab went unscanned")

    def test_unpublished_labs_are_skipped(self):
        """An is_active:false lab cannot be started and cannot award XP, so counting
        it against the decorative ratchet would keep the gate permanently red for
        labs nobody can reach."""
        slugs = {slug for slug, _tech, _spec in _catalogue()}
        self.assertNotIn("ai-ml-lab-15", slugs)


class RatchetTests(SimpleTestCase):
    """The decorative count is a ratchet: it may shrink, never grow."""

    def test_live_catalogue_is_at_or_below_the_ceiling(self):
        from collections import Counter

        counts: Counter[str] = Counter()
        for _slug, _tech, spec in _catalogue():
            counts[_sgi.classify_coding(spec)[0]] += 1

        self.assertEqual(
            counts["CODING-FAIL-OPEN"], 0,
            "a coding lab grades as solved against its shipped stub",
        )
        self.assertEqual(
            counts["CODING-NO-TESTS"], 0, "a coding lab ships with no tests at all"
        )
        decorative = counts["CODING-DECORATIVE"]
        self.assertLessEqual(
            decorative, _sgi._CODING_DECORATIVE_CEILING,
            f"decorative coding graders grew to {decorative} (ceiling "
            f"{_sgi._CODING_DECORATIVE_CEILING}) — a test any trivial stub satisfies "
            "does not grade the lab's subject",
        )
        if decorative < _sgi._CODING_DECORATIVE_CEILING:
            self.fail(
                f"decorative graders down to {decorative} — lower "
                f"_CODING_DECORATIVE_CEILING to {decorative} to lock the gain in"
            )
