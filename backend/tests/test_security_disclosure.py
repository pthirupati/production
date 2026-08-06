"""There must be a working way to report a vulnerability.

Audit Z4-7: no SECURITY.md, no security.txt, no safe-harbour statement. Worse, the
gateway *actively 404'd* `/.well-known/security.txt`, listing it alongside `.env`
and `wp-admin` as if it were a scanner probe. It is the opposite — RFC 9116 makes it
the standard place a researcher looks to find out where to report. Blocking it told
every researcher we had no disclosure process and sent them to social media.

The date check is the one that will actually fire one day: RFC 9116 says a
security.txt whose `Expires` has passed MUST NOT be used, so a stale file is not a
weaker disclosure channel — it is an invalid one.
"""
import datetime as dt
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

_REPO = Path(settings.BASE_DIR).parent
_SECURITY_TXT = _REPO / "frontend" / "public" / ".well-known" / "security.txt"
_SECURITY_MD = _REPO / "SECURITY.md"


class SecurityTxtTests(SimpleTestCase):
    def setUp(self):
        self.assertTrue(_SECURITY_TXT.is_file(), "frontend/public/.well-known/security.txt is missing")
        self.text = _SECURITY_TXT.read_text(encoding="utf-8")

    def _field(self, name):
        m = re.search(rf"^{name}:\s*(.+)$", self.text, re.MULTILINE)
        return m.group(1).strip() if m else None

    def test_has_a_contact(self):
        """The only field RFC 9116 actually requires."""
        self.assertIsNotNone(self._field("Contact"), "no Contact: field")

    def test_has_an_expires_field(self):
        self.assertIsNotNone(self._field("Expires"), "no Expires: field (required)")

    def test_expires_is_in_the_future(self):
        """An expired security.txt MUST NOT be used — it is invalid, not just stale."""
        raw = self._field("Expires")
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        self.assertGreater(
            parsed, dt.datetime.now(dt.timezone.utc),
            f"security.txt expired on {raw} — RFC 9116 says it must not be used; "
            "push the Expires date out and re-confirm the contact still works",
        )

    def test_points_at_the_policy(self):
        self.assertIsNotNone(self._field("Policy"))

    def test_contact_is_not_a_placeholder(self):
        contact = self._field("Contact")
        for bad in ("example.com", "TODO", "changeme", "your-email"):
            self.assertNotIn(bad, contact.lower())


class SecurityPolicyTests(SimpleTestCase):
    def setUp(self):
        self.assertTrue(_SECURITY_MD.is_file(), "SECURITY.md is missing")
        self.text = _SECURITY_MD.read_text(encoding="utf-8")

    def test_tells_researchers_not_to_open_a_public_issue(self):
        self.assertIn("do not open a public issue", self.text.lower())

    def test_offers_safe_harbour(self):
        """Without it, a careful researcher has a legal reason to stay silent."""
        self.assertIn("safe harbour", self.text.lower())

    def test_states_a_response_timeline(self):
        self.assertRegex(self.text, r"\d+\s+working days")

    def test_covers_lab_container_escape(self):
        """The platform-specific risk a generic policy would miss."""
        low = self.text.lower()
        self.assertIn("container", low)
        self.assertIn("escap", low)


class GatewayServesSecurityTxtTests(SimpleTestCase):
    """The regression that made the file pointless: nginx 404'd it."""

    CONFIGS = [
        _REPO / "gateway" / "nginx.cluster.conf.template",
        _REPO / "gateway" / "nginx.prod.conf",
        _REPO / "gateway" / "nginx.conf",
    ]

    @staticmethod
    def _blocks_security_txt(line: str) -> bool:
        """True if `line` is an nginx location that would 404 security.txt.

        Note the un-escaping: in the config the pattern is written
        `\\.well-known/security\\.txt`, so a naive `"security.txt" in line` never
        matches and the check silently passes forever. That is precisely the shape
        of vacuous test this file exists to avoid.
        """
        stripped = line.strip()
        if stripped.startswith("#"):
            return False  # the explanatory comment names it deliberately
        plain = stripped.replace("\\", "")
        return "location" in plain and "security.txt" in plain

    def test_detection_would_catch_a_reintroduced_block(self):
        """Guard the guard — a matcher that cannot fire protects nothing."""
        old = (r"location ~* /(\.\.env|\.env|\.git|wp-admin|phpMyAdmin|"
               r"phpmyadmin|\.well-known/security\.txt) {")
        new = r"location ~* /(\.\.env|\.env|\.git|wp-admin|phpMyAdmin|phpmyadmin) {"
        self.assertTrue(self._blocks_security_txt(old), "matcher misses a real block")
        self.assertFalse(self._blocks_security_txt(new), "matcher flags the fixed line")

    def test_no_gateway_config_blocks_security_txt(self):
        offenders = []
        for cfg in self.CONFIGS:
            if not cfg.is_file():
                continue
            for line in cfg.read_text(encoding="utf-8").splitlines():
                if self._blocks_security_txt(line):
                    offenders.append(f"{cfg.name}: {line.strip()}")
        self.assertEqual(
            offenders, [],
            "these gateway configs still 404 the RFC 9116 disclosure endpoint: "
            + "; ".join(offenders),
        )

    def test_exploit_blocklist_still_blocks_real_probes(self):
        """Unblocking security.txt must not have unblocked .env or wp-admin."""
        cfg = _REPO / "gateway" / "nginx.cluster.conf.template"
        text = cfg.read_text(encoding="utf-8")
        for probe in ("\\.env", "wp-admin", "phpmyadmin"):
            self.assertIn(probe, text, f"{probe} is no longer blocked")
