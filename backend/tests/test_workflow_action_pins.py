"""Third-party GitHub Actions must be pinned to immutable commit SHAs.

A mutable tag like `@v2` is a branch or a movable ref on the *upstream* repo,
so whoever controls that repo can change what our CI runs without a commit
here. That matters most for the actions that receive credentials:
`digitalocean/action-doctl` is handed DIGITALOCEAN_ACCESS_TOKEN in nine
workflows, including the vault-repair/dbrepair break-glass ones.

`digitalocean/action-doctl@v2` is not even a tag upstream -- it is a *branch*
(refs/heads/v2), which is the weakest possible pin. That is why the audit
flagged these three by name.

Scope note: this deliberately only enforces the three actions the audit item
covers, rather than every `uses:` in the tree. A blanket rule would fail on
first-party `actions/checkout` and on our own `./.github/actions/*` composites,
and would turn into a rubber stamp that gets weakened the first time it fires.
Add to ENFORCED as more actions get pinned.
"""

import re
from pathlib import Path

from django.test import SimpleTestCase

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"

# Actions this test refuses to let regress back to a mutable ref.
ENFORCED = (
    "digitalocean/action-doctl",
    "docker/build-push-action",
    "actions/github-script",
)

# `uses: owner/repo@ref` with an optional trailing `# vX.Y.Z` comment.
USES_RE = re.compile(
    r"uses:\s*(?P<action>[A-Za-z0-9._-]+/[A-Za-z0-9._-]+)@(?P<ref>\S+)"
    r"(?:\s*#\s*(?P<comment>.+))?$"
)

FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _enforced_uses():
    """Yield (path, lineno, action, ref, comment) for every enforced action."""
    for path in sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml")):
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            match = USES_RE.search(line.strip())
            if not match:
                continue
            if match.group("action") not in ENFORCED:
                continue
            yield (
                path,
                lineno,
                match.group("action"),
                match.group("ref"),
                (match.group("comment") or "").strip(),
            )


class WorkflowActionPinTests(SimpleTestCase):
    def test_workflow_directory_is_where_we_think_it_is(self):
        """Guard against the scan silently matching nothing after a repo move."""
        self.assertTrue(WORKFLOWS.is_dir(), f"missing workflow dir: {WORKFLOWS}")
        self.assertTrue(list(WORKFLOWS.glob("*.yml")), "no workflows found to scan")

    def test_enforced_actions_are_pinned_to_full_commit_shas(self):
        unpinned = [
            f"{path.name}:{lineno} {action}@{ref}"
            for path, lineno, action, ref, _ in _enforced_uses()
            if not FULL_SHA_RE.match(ref)
        ]
        self.assertEqual(
            [],
            unpinned,
            "these actions handle credentials and must be pinned to a 40-char "
            "commit SHA, not a mutable tag/branch:\n  " + "\n  ".join(unpinned),
        )

    def test_every_enforced_action_is_actually_present(self):
        """If a rename silently drops these, the pin test above passes vacuously."""
        found = {action for _, _, action, _, _ in _enforced_uses()}
        self.assertEqual(set(ENFORCED), found)

    def test_pins_carry_a_version_comment_for_dependabot(self):
        """dependabot's github-actions ecosystem maps a SHA back to a version
        via the trailing `# vX.Y.Z` comment. Without it, it stops proposing
        upgrades and the pin quietly rots."""
        missing = [
            f"{path.name}:{lineno} {action}@{ref}"
            for path, lineno, action, ref, comment in _enforced_uses()
            if not re.match(r"^v\d+(\.\d+)*$", comment)
        ]
        self.assertEqual(
            [],
            missing,
            "pinned actions need a trailing `# vX.Y.Z` version comment:\n  "
            + "\n  ".join(missing),
        )

    def test_a_single_sha_per_action_across_all_workflows(self):
        """Nine copies of action-doctl drifting to different SHAs is how a
        break-glass workflow ends up running different code than the deploy."""
        by_action = {}
        for _, _, action, ref, _ in _enforced_uses():
            by_action.setdefault(action, set()).add(ref)
        for action, refs in sorted(by_action.items()):
            self.assertEqual(
                1, len(refs), f"{action} pinned to multiple refs: {sorted(refs)}"
            )
