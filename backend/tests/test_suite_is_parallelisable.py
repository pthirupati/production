"""The test suite must survive `manage.py test --parallel`.

Found while running the full suite: `--parallel` died with
`TypeError: cannot pickle '_contextvars.Context' object` **before executing a single
test**. Django's parallel runner pickles test cases to hand them to worker
processes, and `unittest.IsolatedAsyncioTestCase.__init__` stores a
`contextvars.Context`, which cannot be pickled. One class using it took down the
entire run.

That matters beyond local convenience: `.github/workflows/e2e-labs.yml` runs
`manage.py test tests --parallel`. The step was failing on infrastructure rather
than on any assertion, which is the worst kind of red — it says nothing about the
code and trains people to ignore the job.

`ci.yml` runs serially, so nothing else catches this. Written as a test rather than
left as a fixed bug because the failure mode is silent at authoring time: adding an
async test the obvious way, with `IsolatedAsyncioTestCase`, passes locally, passes
in `ci.yml`, and breaks a different workflow entirely.

Django's `SimpleTestCase` supports `async def test_` methods natively and pickles
fine, so the fix is a base-class change with no loss of capability.
"""

import pickle
import unittest

from django.test.runner import DiscoverRunner
from django.test import SimpleTestCase


def _all_test_cases():
    """Every test case the runner would collect, flattened."""
    suite = DiscoverRunner(verbosity=0).build_suite(["tests"])

    def walk(s):
        for item in s:
            if isinstance(item, unittest.TestSuite):
                yield from walk(item)
            else:
                yield item

    return list(walk(suite))


class TheSuiteCanBeDistributedToWorkersTests(SimpleTestCase):
    def test_no_test_case_uses_isolated_asyncio_test_case(self):
        """The specific, fast check — names the offender directly so the failure
        message is actionable rather than a pickle traceback."""
        offenders = sorted(
            {
                f"{type(t).__module__}.{type(t).__qualname__}"
                for t in _all_test_cases()
                if isinstance(t, unittest.IsolatedAsyncioTestCase)
            }
        )
        self.assertEqual(
            offenders, [],
            "IsolatedAsyncioTestCase cannot be pickled, so these break "
            "`manage.py test --parallel` (used by e2e-labs.yml) for the whole "
            "suite. Use django.test.SimpleTestCase — it supports `async def "
            "test_` and pickles.",
        )

    def test_every_test_case_can_be_pickled(self):
        """The general check. Catches any future unpicklable attribute, not just
        the one base class that caused this — pickling is exactly what the parallel
        runner does, so this fails for the same reason the runner would."""
        unpicklable = []
        for test in _all_test_cases():
            try:
                pickle.dumps(test)
            except Exception as exc:
                unpicklable.append(
                    f"{type(test).__module__}.{type(test).__qualname__}: {exc}"
                )
        self.assertEqual(
            sorted(set(unpicklable)), [],
            "these test cases cannot be pickled, so `--parallel` aborts the entire "
            "run before executing anything",
        )
