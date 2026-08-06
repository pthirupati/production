"""The leaked-secret scanner had two blind spots and reported "clean" anyway.

Found by an adversarial re-check of an item this audit had already marked done.
`scripts/check-no-secrets-in-git.sh` exited 0 with "no secrets detected" while three
live production credentials sat in a **tracked** file:

* two 64-hex OAuth client secrets — the name list contained `KEY_SECRET`, which does
  not match `CLIENT_SECRET`;
* a RabbitMQ password embedded in `CELERY_BROKER_URL` as `amqp://user:pass@host` —
  the rule matches `KEY=value`, so a credential *inside* a value is invisible. That
  password had been redacted on two other lines of the same file, and sat in clear
  text ten lines below, which made both redactions void.

The gate was trusted repeatedly on the strength of its own green output. That is the
failure worth testing: a security check that cannot fail is worse than no check,
because it is actively believed.

**Why the patterns are tested rather than the script end-to-end.** The scanner runs
`git grep` over *tracked* files, so exercising it needs a tracked fixture containing
real-looking secrets — which the scanner would then flag forever. Testing the
extracted regexes gives the same coverage with no fixture to poison the tree.

Every sample below is **assembled at runtime from fragments** so that no line in
this file matches a secret rule. Writing them as literals would make this very file
a scanner finding.
"""

import re
import subprocess
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

SCANNER = Path(settings.BASE_DIR).parent / "scripts" / "check-no-secrets-in-git.sh"

# Split so the assembled values never appear literally in this source file.
_HEX64 = "fb6d33f81333e092cd5c83daf7e80137" + "f0ccfab127344ea5902d85c325ba9eee"
_PW = "MTKNGug" + "!wwZqWs7AKbAllR22ftiv0CMe"


def _pattern(name: str) -> str:
    """Pull a regex out of the shell script, so the test cannot drift from it.

    Reading the value rather than restating it is the point: a copy here would keep
    passing after someone narrowed the real rule.
    """
    text = SCANNER.read_text()
    match = re.search(rf"^{name}='(.*)'$", text, re.M)
    assert match, f"{name} not found in {SCANNER.name}"
    return match.group(1)


def _matches(pattern: str, line: str) -> bool:
    """Use grep -E so this tests the same engine the scanner uses, not Python's."""
    return subprocess.run(
        ["grep", "-qE", pattern], input=line, text=True
    ).returncode == 0


class TheAssignmentRuleCatchesVendorSecretNamesTests(SimpleTestCase):
    def setUp(self):
        self.rule = _pattern("SECRET_ASSIGN_RE")

    def test_it_catches_github_client_secret(self):
        """The exact miss. `KEY_SECRET` does not match `CLIENT_SECRET`."""
        self.assertTrue(_matches(self.rule, "GITHUB_CLIENT" + "_SECRET=" + _HEX64))

    def test_it_catches_google_client_secret(self):
        self.assertTrue(_matches(self.rule, "GOOGLE_CLIENT" + "_SECRET=" + _HEX64))

    def test_it_catches_an_unknown_vendors_secret(self):
        """The reason the fix is a suffix and not another name in a list: an
        enumeration of vendor spellings always trails the code."""
        self.assertTrue(_matches(self.rule, "SOMEVENDOR" + "_SECRET=" + _HEX64))

    def test_it_still_catches_the_original_classes(self):
        """Guard the guard — widening must not have dropped anything."""
        for key in ("SECRET_KEY", "DB_PASSWORD", "API_TOKEN", "AWS_ACCESS_KEY"):
            self.assertTrue(_matches(self.rule, key + "=" + _HEX64), key)


class TheUrlRuleCatchesEmbeddedCredentialsTests(SimpleTestCase):
    """A password inside a connection string is not an assignment, so the assignment
    rule structurally cannot see it."""

    def setUp(self):
        self.rule = _pattern("URL_USERINFO_RE")

    def test_it_catches_the_broker_url(self):
        line = "CELERY_BROKER_URL=amqp://fixitlab:" + _PW + "@rabbitmq:5672//"
        self.assertTrue(_matches(self.rule, line))

    def test_the_assignment_rule_alone_would_miss_it(self):
        """States the reason a second rule exists. If this ever starts failing, the
        rules overlap and one of them can be retired — but not before."""
        line = "CELERY_BROKER_URL=amqp://fixitlab:" + _PW + "@rabbitmq:5672//"
        self.assertFalse(_matches(_pattern("SECRET_ASSIGN_RE"), line))

    def test_it_catches_other_schemes(self):
        for scheme in ("postgres", "redis", "mongodb", "https"):
            self.assertTrue(
                _matches(self.rule, f"{scheme}://admin:" + _PW + "@host:5432/db"),
                scheme,
            )

    def test_it_ignores_a_url_with_no_credential(self):
        self.assertFalse(_matches(self.rule, "https://fixitlab.in/api/v1/labs"))

    def test_it_ignores_a_bare_userinfo_with_empty_password(self):
        self.assertFalse(_matches(self.rule, "amqp://guest:@localhost:5672//"))


class PlaceholdersAreStillSuppressedTests(SimpleTestCase):
    """The widened rules over-matched instructional text in three docs. Those are
    real placeholders, and flagging them trains people to ignore the scanner —
    which is how a real finding gets waved through."""

    def setUp(self):
        self.placeholder = _pattern("PLACEHOLDER_RE")

    def test_instructional_values_are_treated_as_placeholders(self):
        for value in (
            "JIRA_WEBHOOK" + "_SECRET=generate-a-long-random-string",
            "JIRA_WEBHOOK" + "_SECRET=generate-32-char-random-string",
            "RAZORPAY_WEBHOOK" + "_SECRET=paste-webhook-secret-from-dashboard",
        ):
            self.assertTrue(_matches(self.placeholder, value), value)

    def test_a_real_secret_is_not_treated_as_a_placeholder(self):
        """The important half. `PLACEHOLDER_RE` suppresses findings, so anything it
        matches is invisible — a loose pattern here silently disarms the scanner.
        The script already carries a scar from this: a bare `/your/` once suppressed
        a genuine AWS key whose value happened to contain that substring."""
        self.assertFalse(_matches(self.placeholder, "GITHUB_CLIENT" + "_SECRET=" + _HEX64))
        self.assertFalse(_matches(self.placeholder, "amqp://fixitlab:" + _PW + "@rabbitmq"))


class TheAwsExampleKeyIsAllowlistedByValueNotByPathTests(SimpleTestCase):
    """Pass 1 used to skip two whole paths so the AWS console sim could print
    Amazon's published documentation key. Suppressing a directory to excuse one
    well-known value meant a genuine `ghp_`/`dop_v1_`/PEM leak anywhere under
    `frontend/src/components/aws/` was scanned and reported clean.

    Measured before the fix: a file containing a real-shaped GitHub PAT was
    written to that directory, staged, and the scanner exited 0 with "no secrets
    detected". The same probe fails the build now.
    """

    def setUp(self):
        self.text = SCANNER.read_text()
        # Strip comments before asserting on exclusions: the script *documents*
        # the removed pathspecs by quoting them, so a whole-file substring search
        # matches the explanation and not the behaviour.
        self.code = "\n".join(
            line for line in self.text.splitlines()
            if not line.lstrip().startswith("#")
        )

    def test_the_directory_wide_exclusions_are_gone(self):
        """The specific blind spot. Named explicitly so re-adding either pathspec
        as a quick fix for a noisy sim file fails here with the reason."""
        self.assertNotIn("':!frontend/src/components/aws/**'", self.code)
        self.assertNotIn("':!backend/apps/vmware_sim/aws_engine.py'", self.code)

    def test_a_value_level_allowlist_exists(self):
        self.assertIn("ALLOWED_SECRET_VALUES=(", self.text)
        self.assertIn("AKIAIOSFODNN7EXAMPLE", self.text)

    def test_allowlist_entries_are_literals_not_patterns(self):
        """An allowlist suppresses findings, so a regex entry is a silent hole:
        `-----BEGIN RSA PRIVATE KEY-----.*` would mute every real PEM in the repo.
        Keep entries to exact, full-length credential literals."""
        block = re.search(
            r"ALLOWED_SECRET_VALUES=\((.*?)\n\)", self.text, re.S
        )
        assert block, "ALLOWED_SECRET_VALUES block not found"
        entries = re.findall(r"'([^']+)'", block.group(1))
        self.assertTrue(entries, "allowlist unexpectedly empty")
        for entry in entries:
            self.assertNotRegex(
                entry, r"[.*+?\[\]()|\\^$]",
                f"allowlist entry {entry!r} contains regex metacharacters",
            )


class TheScannerRunsCleanOnTheCurrentTreeTests(SimpleTestCase):
    """End-to-end, and meaningful only because the rules above are tested for teeth.
    On its own this assertion is what gave false confidence for three runs."""

    def test_the_tree_is_clean(self):
        result = subprocess.run(
            ["bash", str(SCANNER)], capture_output=True, text=True,
            cwd=str(Path(settings.BASE_DIR).parent),
        )
        self.assertEqual(
            result.returncode, 0,
            f"secret scanner failed:\n{result.stdout}\n{result.stderr}",
        )
