"""Which settings `test_settings` shares with production — and why it matters.

`config/test_settings.py` does `from .settings import *`, so every setting starts as
the *same object* production uses. It then changes some of them two different ways,
and the difference is invisible at the call site but decides whether a test can see
production config at all:

* **Rebinding** (``LOGGING = {...}``) creates a new object for the test module.
  ``config.settings.LOGGING`` still holds the production value, so a test may import
  it and assert on the real thing.
* **Mutating** (``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {...}``) edits the
  shared dict in place. ``config.settings.REST_FRAMEWORK`` *is* the test-mutated
  object, so a test importing it reads **test** values while believing it checked
  production.

That second case bit a throttle test in this repo: it asserted the contact rate by
importing `config.settings` and would have passed on the `10000/minute` test value
however loose production drifted. The fix there was to read `config/settings.py` as
source text.

This file freezes the current split so a new in-place mutation cannot quietly convert
someone's production-config assertion into a tautology.
"""
import re
import pathlib
import sys

from django.conf import settings
from django.test import SimpleTestCase

_CONFIG = pathlib.Path(settings.BASE_DIR) / "config"

# Settings `test_settings` edits IN PLACE, so production and test share one object.
# Anything listed here CANNOT be verified by importing config.settings — read the
# source file instead.
KNOWN_SHARED = {"REST_FRAMEWORK"}


def _test_settings_source() -> str:
    return (_CONFIG / "test_settings.py").read_text(encoding="utf-8")


class SharedSettingsAreKnownTests(SimpleTestCase):
    def test_no_new_setting_is_mutated_in_place(self):
        """A new `SOMETHING[...] = ...` in test_settings silently makes production
        config unreadable from tests. Adding one is fine — it just has to be a
        deliberate, recorded choice rather than a surprise."""
        mutated = set(re.findall(r"^([A-Z][A-Z0-9_]*)\[", _test_settings_source(), re.M))
        unexpected = mutated - KNOWN_SHARED
        self.assertEqual(
            unexpected, set(),
            f"test_settings now mutates {sorted(unexpected)} in place. Any test that "
            "imports config.settings to assert those values is reading TEST values. "
            "Add them to KNOWN_SHARED and read them from source instead.",
        )

    def test_the_known_shared_setting_really_is_shared(self):
        """Guard the guard: if REST_FRAMEWORK ever stops being shared, KNOWN_SHARED is
        stale and the warning above misleads."""
        prod = sys.modules.get("config.settings")
        self.assertIsNotNone(prod, "config.settings not imported")
        self.assertIs(
            settings.REST_FRAMEWORK, prod.REST_FRAMEWORK,
            "REST_FRAMEWORK is no longer shared — remove it from KNOWN_SHARED",
        )


class ReboundSettingsAreReadableTests(SimpleTestCase):
    """The other half: settings that ARE safe to assert on by import."""

    def test_logging_is_distinct_so_production_handlers_are_visible(self):
        """`test_settings` rebinds LOGGING, so config.settings keeps the real one.
        `test_log_pii_redaction` relies on this to check that every production
        handler routes through the PII-masking formatter."""
        prod = sys.modules["config.settings"]
        self.assertIsNot(settings.LOGGING, prod.LOGGING)
        self.assertIn("console_json", prod.LOGGING["handlers"])
        self.assertEqual(
            prod.LOGGING["formatters"]["json"]["()"],
            "common.logging_utils.JSONFormatter",
        )

    def test_the_active_test_logging_is_the_quiet_one(self):
        """Sanity that the two really are different values, not just objects."""
        self.assertEqual(sorted(settings.LOGGING["handlers"]), ["console"])


class ProductionConfigAssertionsReadSourceTests(SimpleTestCase):
    """Tests asserting a SHARED setting must read the file, not import it."""

    def test_the_contact_throttle_test_reads_source(self):
        src = (pathlib.Path(settings.BASE_DIR) / "tests"
               / "test_contact_form_throttle.py").read_text(encoding="utf-8")
        self.assertIn(
            'read_text()', src,
            "the contact throttle test no longer reads config/settings.py as source; "
            "importing it would assert the test rate and pass however loose "
            "production became",
        )
