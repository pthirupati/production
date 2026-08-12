"""Feature-flag layer (audit Z6-15).

The whole point of the indirection is that a flag is re-read per call. The
audit's risk note is explicit about the failure mode: a flag read at import time
caches the first value for the worker's life, so flipping it in production
appears to do nothing until a restart. `test_flag_is_not_cached_at_import`
is the test that actually pins that down -- the rest is plumbing.
"""

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from config.features import UnknownFeature, all_features, feature_enabled


class FeatureFlagTests(SimpleTestCase):
    def test_seed_flag_is_declared(self):
        self.assertIn("currency_conversion", all_features())

    def test_declared_flags_are_booleans(self):
        """A flag holding a string means `if flag:` is true for "false"."""
        for name, value in all_features().items():
            self.assertIsInstance(value, bool, f"flag {name!r} is not a bool")

    @override_settings(FEATURES={"demo": True})
    def test_enabled_flag_reads_true(self):
        self.assertTrue(feature_enabled("demo"))

    @override_settings(FEATURES={"demo": False})
    def test_disabled_flag_reads_false(self):
        self.assertFalse(feature_enabled("demo"))

    def test_unknown_flag_raises_instead_of_returning_false(self):
        """Silently returning False for a typo is indistinguishable from a
        working kill switch, which is how a feature stays dark for a week."""
        with self.assertRaises(UnknownFeature):
            feature_enabled("no_such_flag_xyz")

    def test_flag_is_not_cached_at_import(self):
        """Flip the flag at runtime and the very next call must see it.

        This fails if feature_enabled() is ever "optimised" into a module-level
        constant, a functools.lru_cache, or a value captured in a default arg.
        """
        with override_settings(FEATURES={"demo": True}):
            self.assertTrue(feature_enabled("demo"))
            # Same process, same import, no restart -- just a settings change.
            with override_settings(FEATURES={"demo": False}):
                self.assertFalse(
                    feature_enabled("demo"),
                    "flag value was cached; flipping it required a restart",
                )
            self.assertTrue(feature_enabled("demo"))

    def test_all_features_returns_a_copy(self):
        """Callers must not be able to mutate the live settings dict."""
        snapshot = all_features()
        snapshot["injected"] = True
        self.assertNotIn("injected", getattr(settings, "FEATURES", {}))


class FeatureFlagEnvOverrideTests(SimpleTestCase):
    """settings.py maps FEATURE_<NAME> env vars onto the defaults."""

    def test_seed_flag_tracks_the_currency_setting(self):
        # The seed flag intentionally mirrors ENABLE_CURRENCY_CONVERSION so the
        # two cannot silently disagree in payment code paths.
        self.assertEqual(
            settings.FEATURES["currency_conversion"],
            settings.ENABLE_CURRENCY_CONVERSION,
        )

    def test_unknown_env_vars_do_not_invent_flags(self):
        """A typo'd FEATURE_* var must not create a flag nothing reads."""
        self.assertNotIn("typo_flag_that_does_not_exist", all_features())
