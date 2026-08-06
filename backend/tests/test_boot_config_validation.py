"""Audit Z6-13 — a typo in an env var name was silent.

Almost every setting is `env("NAME", default=...)`, so misspelling one means the
process boots happily on the default. Harmless for a display string; dangerous for
a security control — `JWT_ALGORITHM`, `SENTRY_DSN` and `ALERT_EMAIL` all behave
this way.

The precedent is the Vault-sealed outage (`docs/adr/0004`): a misconfiguration that
does not announce itself gets discovered by users. So the checks fail at **boot**,
before any traffic is served.

Two limits are deliberate and are tested as such:

* **Production only.** Raising on a developer's laptop because they have no
  Razorpay key would make this something people disable, and a check people disable
  protects nothing.
* **It validates what is set, not that a name exists.** `DEBUG=True` in production,
  or a `SECRET_KEY` left at a placeholder, both pass a mere presence check and are
  exactly the failures worth catching.

These call the validator directly rather than re-importing settings, because
`config.settings` is already imported by the time any test runs and re-importing it
under a mutated environment is unreliable.
"""
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config import settings as prod_settings


def _run_with(**overrides):
    """Run the validator against a patched settings module."""
    base = {
        "DEBUG": False,
        "SECRET_KEY": "x" * 50,
        "ALLOWED_HOSTS": ["fixitlab.in"],
        "SIMPLE_JWT": {"ALGORITHM": "RS256", "SIGNING_KEY": "-----BEGIN KEY-----"},
        "DATABASES": {"default": {"NAME": "fixitlab"}},
    }
    base.update(overrides)
    with mock.patch.multiple(prod_settings, **base):
        prod_settings._validate_production_config()


class AGoodConfigBootsTests(SimpleTestCase):
    def test_a_valid_production_config_passes(self):
        """Guard the guard: a validator that rejected everything would be found out
        immediately, but one that rejects nothing would not."""
        _run_with()  # must not raise


class ItCatchesTheDangerousMisconfigurationsTests(SimpleTestCase):
    def test_debug_true_in_production_is_refused(self):
        """The single worst one: it leaks stack traces, settings and SQL."""
        with self.assertRaises(ImproperlyConfigured) as ctx:
            _run_with(DEBUG=True)
        self.assertIn("DEBUG", str(ctx.exception))

    def test_a_short_secret_key_is_refused(self):
        with self.assertRaises(ImproperlyConfigured):
            _run_with(SECRET_KEY="short")

    def test_a_placeholder_secret_key_is_refused(self):
        """Length alone would pass this — it is 50 characters of placeholder."""
        with self.assertRaises(ImproperlyConfigured) as ctx:
            _run_with(SECRET_KEY="django-insecure-" + "y" * 40)
        self.assertIn("placeholder", str(ctx.exception))

    def test_wildcard_allowed_hosts_is_refused(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            _run_with(ALLOWED_HOSTS=["*"])
        self.assertIn("ALLOWED_HOSTS", str(ctx.exception))

    def test_empty_allowed_hosts_is_refused(self):
        with self.assertRaises(ImproperlyConfigured):
            _run_with(ALLOWED_HOSTS=[])

    def test_a_mistyped_jwt_algorithm_is_refused(self):
        """`RS526` would otherwise fall through to the default and sign every token
        with an algorithm nobody chose — the exact failure mode this item names."""
        with self.assertRaises(ImproperlyConfigured) as ctx:
            _run_with(SIMPLE_JWT={"ALGORITHM": "RS526", "SIGNING_KEY": "k"})
        self.assertIn("JWT_ALGORITHM", str(ctx.exception))

    def test_an_empty_signing_key_is_refused(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            _run_with(SIMPLE_JWT={"ALGORITHM": "RS256", "SIGNING_KEY": ""})
        self.assertIn("signing key", str(ctx.exception).lower())

    def test_an_empty_database_name_is_refused(self):
        with self.assertRaises(ImproperlyConfigured):
            _run_with(DATABASES={"default": {"NAME": ""}})


class TheErrorIsActionableTests(SimpleTestCase):
    def test_every_problem_is_listed_not_just_the_first(self):
        """Reporting one at a time turns a misconfigured deploy into several rounds
        of fix-and-retry."""
        with self.assertRaises(ImproperlyConfigured) as ctx:
            _run_with(DEBUG=True, ALLOWED_HOSTS=["*"], SECRET_KEY="short")
        message = str(ctx.exception)
        self.assertIn("DEBUG", message)
        self.assertIn("ALLOWED_HOSTS", message)
        self.assertIn("SECRET_KEY", message)

    def test_it_says_what_the_consequence_is(self):
        """'DEBUG is True' is a fact; saying what it leaks is what makes someone
        act on it at 2am."""
        with self.assertRaises(ImproperlyConfigured) as ctx:
            _run_with(DEBUG=True)
        self.assertIn("stack traces", str(ctx.exception))

    def test_it_names_the_escape_hatch_and_discourages_it(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            _run_with(DEBUG=True)
        message = str(ctx.exception)
        self.assertIn("FIXITLAB_SKIP_CONFIG_CHECK", message)
        self.assertIn("should not", message)


class SoftSettingsWarnRatherThanFailTests(SimpleTestCase):
    """Missing observability degrades operations; it does not make the platform
    unsafe to run. Failing on it would be the kind of overreach that gets the whole
    check disabled."""

    def test_a_missing_sentry_dsn_does_not_block_boot(self):
        with mock.patch.multiple(
            prod_settings, SENTRY_DSN="", ALERT_EMAIL="", BUSINESS_GSTIN=""
        ):
            prod_settings._warn_on_soft_config()  # must not raise

    def test_it_logs_what_is_degraded(self):
        with mock.patch.multiple(
            prod_settings, SENTRY_DSN="", ALERT_EMAIL="", BUSINESS_GSTIN=""
        ), self.assertLogs("django", level="WARNING") as captured:
            prod_settings._warn_on_soft_config()
        joined = " ".join(captured.output)
        self.assertIn("SENTRY_DSN", joined)
        self.assertIn("error reporting", joined)

    def test_it_is_silent_when_everything_is_configured(self):
        """A warning that always fires is one nobody reads."""
        with mock.patch.multiple(
            prod_settings,
            SENTRY_DSN="https://x@sentry.io/1",
            ALERT_EMAIL="ops@fixitlab.in",
            BUSINESS_GSTIN="29ABCDE1234F1Z5",
        ):
            with self.assertNoLogs("django", level="WARNING"):
                prod_settings._warn_on_soft_config()


class ItDoesNotFireInDevelopmentTests(SimpleTestCase):
    def test_the_guard_is_conditioned_on_debug(self):
        """Raising on a laptop with no Razorpay key would make this something people
        disable, and a check people disable protects nothing."""
        import inspect
        import pathlib

        src = (
            pathlib.Path(inspect.getfile(prod_settings))
        ).read_text()
        self.assertIn("if not DEBUG and env.bool(\"FIXITLAB_SKIP_CONFIG_CHECK\"", src)

    def test_the_test_suite_itself_boots(self):
        """This test executing at all is the proof.

        The guard runs at settings-IMPORT time, when `config/test_settings.py` has
        set `DEBUG = True`, so it does not fire. Django's test runner then forces
        `settings.DEBUG = False` at runtime via `setup_test_environment()` — which
        is why asserting `settings.DEBUG` here reads False and would be testing the
        runner, not the guard.

        What matters is that importing the settings module did not raise: if the
        guard had fired, no test in this suite would run.
        """
        from django.conf import settings as active

        self.assertTrue(
            active.configured,
            "settings failed to load — the boot guard fired during the test run",
        )
