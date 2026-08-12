"""Session 77: vault unseal lab, dunning grace, project YAML loader."""

from django.test import SimpleTestCase

from apps.billing.subscription_utils import apply_dunning_status
from apps.labs.vault_lab_ops import (
    auth_vault,
    grade_vault_restore,
    issue_db_credentials,
    present_unseal_key,
    renew_lease,
    revoke_lease,
    seal_vault,
)
from apps.question_bank.management.commands.project_yaml_loader import (
    load_project_yamls,
    merge_extra_projects,
)


class _Sub:
    def __init__(self, active=True):
        self.is_active = active
        self.saves = 0

    def save(self, update_fields=None):
        self.saves += 1


class DunningGraceTests(SimpleTestCase):
    def test_past_due_keeps_active_unpaid_kills(self):
        sub = _Sub(active=True)
        r = apply_dunning_status(sub, "past_due")
        self.assertEqual(r["action"], "dunning_grace")
        self.assertTrue(sub.is_active)

        dead = apply_dunning_status(sub, "unpaid")
        self.assertEqual(dead["action"], "deactivate")
        self.assertFalse(sub.is_active)

        revived = apply_dunning_status(sub, "active")
        self.assertTrue(sub.is_active)
        self.assertEqual(revived["action"], "activate")


class VaultLabTests(SimpleTestCase):
    def test_unseal_auth_lease_renew_revoke(self):
        state = {}
        seal_vault(state)
        self.assertTrue(state["vault_lab"]["sealed"])

        # Need 3 keys
        for key in ("share-alpha", "share-bravo"):
            r = present_unseal_key(state, key)
            self.assertTrue(r["ok"])
            self.assertFalse(r.get("unsealed"))
        done = present_unseal_key(state, "share-charlie")
        self.assertTrue(done.get("unsealed"))
        self.assertFalse(state["vault_lab"]["sealed"])

        blocked = issue_db_credentials(state)
        self.assertFalse(blocked["ok"])

        auth = auth_vault(state, method="approle", role_id="lab-role", secret_id="lab-secret")
        self.assertTrue(auth["ok"], auth)
        lease = issue_db_credentials(state, ttl_seconds=30)
        self.assertTrue(lease["ok"], lease)
        lid = lease["lease"]["id"]

        renewed = renew_lease(state, lid, extend_seconds=30)
        self.assertTrue(renewed["ok"])
        self.assertEqual(grade_vault_restore(state)["passed"], True)

        revoke_lease(state, lid)
        self.assertFalse(grade_vault_restore(state)["passed"])


class ProjectYamlLoaderTests(SimpleTestCase):
    def test_yaml_fixture_overrides_python_slug(self):
        yamls = load_project_yamls()
        self.assertTrue(yamls)
        slugs = {p["slug"] for p in yamls}
        self.assertIn("ai-infra-e2e-image-to-inference", slugs)

        merged = merge_extra_projects([
            {"slug": "ai-infra-e2e-image-to-inference", "title": "FROM_PYTHON"},
            {"slug": "keep-me", "title": "Keep"},
        ])
        by_slug = {p["slug"]: p for p in merged}
        self.assertNotEqual(by_slug["ai-infra-e2e-image-to-inference"]["title"], "FROM_PYTHON")
        self.assertEqual(by_slug["keep-me"]["title"], "Keep")
