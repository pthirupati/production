"""The published grievance contact must stay correct, and stay one value.

Under DPDP the address printed in the privacy policy is the channel a data principal
complains through, and the policy itself promises acknowledgement within 3 working
days. So the failure this guards is not cosmetic: mail to a wrong or misspelled
address bounces silently, and a grievance channel that drops mail is worse than no
channel, because the promise has already been made.

Two ways that goes wrong, and both have already happened here:

* **Drift.** The address was a string literal repeated across six frontend pages
  plus the backend. The privacy page named `fixitlab.admin@gmail.com` — a general
  support inbox — while its own text pointed the reader at "the grievance contact
  below". Now there is one constant on each side and this file holds them equal.
* **Helpful correction.** The mailbox is spelled **"piracy"**, not "privacy". It
  reads like a typo, was confirmed with the owner as literal, and is exactly the
  kind of thing a future reader fixes in passing. Renaming it to the "correct"
  spelling would point the policy at a mailbox that does not exist, and nothing
  would fail — the mail would simply stop arriving. Hence an explicit test.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

REPO = Path(settings.BASE_DIR).parent
CONTACT_JS = REPO / "frontend" / "src" / "constants" / "contact.js"
PRIVACY_JSX = REPO / "frontend" / "src" / "pages" / "Privacy.jsx"
SECURITY_TXT = REPO / "frontend" / "public" / ".well-known" / "security.txt"
SECURITY_MD = REPO / "SECURITY.md"


def _js_const(name: str) -> str:
    """Read an exported string constant out of the frontend contact module."""
    match = re.search(
        rf"export const {name} = ['\"]([^'\"]+)['\"]", CONTACT_JS.read_text()
    )
    assert match, f"{name} is not exported from {CONTACT_JS.name}"
    return match.group(1)


class TheGrievanceContactIsCorrectTests(SimpleTestCase):
    def test_the_spelling_is_the_literal_mailbox(self):
        """'piracy', not 'privacy' — deliberate, confirmed, and load-bearing.

        If this fails because someone corrected the spelling: the mailbox really is
        `piracy.fixitlab@gmail.com`. Change it only alongside an actual mailbox
        change, or privacy complaints stop being delivered.
        """
        self.assertEqual(settings.PRIVACY_EMAIL, "piracy.fixitlab@gmail.com")

    def test_the_frontend_and_backend_agree(self):
        """Two hand-maintained copies of a published address drift; that is how the
        policy came to name a general support inbox."""
        self.assertEqual(_js_const("PRIVACY_EMAIL"), settings.PRIVACY_EMAIL)

    def test_it_is_not_the_general_support_inbox(self):
        """The specific prior bug. A grievance contact that is really the sales
        inbox means complaints are triaged as sales mail."""
        self.assertNotEqual(settings.PRIVACY_EMAIL, settings.SALES_INBOX)
        self.assertNotEqual(settings.PRIVACY_EMAIL, settings.SUPPORT_EMAIL)

    def test_it_looks_like_an_address(self):
        self.assertRegex(settings.PRIVACY_EMAIL, r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ThePrivacyPagePublishesItTests(SimpleTestCase):
    """A constant nothing renders is not a published contact."""

    def test_the_privacy_page_uses_the_shared_constant(self):
        source = PRIVACY_JSX.read_text()
        self.assertIn("PRIVACY_EMAIL", source)
        self.assertIn("constants/contact", source)

    def test_the_privacy_page_hardcodes_no_address(self):
        """Re-introducing a literal is how the two got out of step before."""
        literals = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", PRIVACY_JSX.read_text())
        self.assertEqual(
            literals, [],
            f"hardcoded address(es) on the privacy page: {literals} — use the "
            "shared constant so the policy and the contact page cannot disagree",
        )


class NoFrontendPageHardcodesAContactAddressTests(SimpleTestCase):
    """Guard the guard: centralising one page while five others keep literals just
    relocates the drift."""

    def test_contact_addresses_live_only_in_the_constants_module(self):
        """Keyed on `mailto:` rather than on anything shaped like an address.

        A plain address regex flags `ssh lab@fixitlab.in` in the auth page's
        decorative terminal art, which is not a contact and should not be a
        constant. What actually matters is a *reachable* address — something a user
        can click — so that is what this looks for.
        """
        offenders = {}
        for page in (REPO / "frontend" / "src").rglob("*.jsx"):
            found = re.findall(r"mailto:([\w.+-]+@[\w.-]+\.\w+)", page.read_text())
            if found:
                offenders[str(page.relative_to(REPO))] = sorted(set(found))
        self.assertEqual(
            offenders, {},
            "these pages hardcode a mailto: address instead of importing from "
            "src/constants/contact.js",
        )


class TheSecurityAddressIsConsistentTests(SimpleTestCase):
    """`security.txt` is machine-read by researchers and scanners; if it disagrees
    with SECURITY.md, reports go to whichever one the reporter happened to read."""

    def test_security_txt_matches_the_setting(self):
        self.assertIn(settings.SECURITY_EMAIL, SECURITY_TXT.read_text())

    def test_security_md_matches_the_setting(self):
        self.assertIn(settings.SECURITY_EMAIL, SECURITY_MD.read_text())

    def test_the_security_and_privacy_channels_are_distinct(self):
        """They have different response obligations and different readers."""
        self.assertNotEqual(settings.SECURITY_EMAIL, settings.PRIVACY_EMAIL)


class TheLegalTemplatesHaveNoUnfilledContactPlaceholdersTests(SimpleTestCase):
    """`docs/private/*.md` are the drafts the published pages are derived from, and
    they shipped with `[PRIVACY_EMAIL]` still literal in three places. Legal
    placeholders (company name, jurisdiction, registered address) are deliberately
    still open — those need counsel, not a commit — but a contact placeholder is
    just unfinished, and it is the one a reader would try to email.

    **These two tests do nothing in CI, deliberately, and that is worth stating
    rather than discovering.** `docs/private/` is gitignored (`.gitignore:36`), so
    the templates exist only on the owner's machine; in CI the paths are absent and
    both tests no-op. They are a local drift guard for unpublished drafts, not a
    pipeline gate. The published policy is `frontend/src/pages/Privacy.jsx`, and
    *that* is covered for real by the classes above.
    """

    def _templates(self):
        return [
            REPO / "docs" / "private" / "PRIVACY_POLICY.md",
            REPO / "docs" / "private" / "TERMS_AND_CONDITIONS.md",
        ]

    def test_no_contact_placeholders_remain(self):
        for path in self._templates():
            if not path.exists():
                continue
            text = path.read_text()
            for token in ("[PRIVACY_EMAIL]", "[SUPPORT_EMAIL]", "[PAYMENT_EMAIL]"):
                self.assertNotIn(
                    token, text, f"{path.name} still contains {token}"
                )

    def test_the_privacy_template_names_the_grievance_address(self):
        path = REPO / "docs" / "private" / "PRIVACY_POLICY.md"
        if path.exists():
            self.assertIn(settings.PRIVACY_EMAIL, path.read_text())
