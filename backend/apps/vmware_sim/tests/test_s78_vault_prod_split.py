"""Session 78: vault prod config + production.yml reusable extract contracts."""

from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[4]


class VaultProdConfigTests(SimpleTestCase):
    def test_prod_config_enables_mlock_and_tls(self):
        prod = (ROOT / "infra/vault/config.prod.hcl").read_text()
        lab = (ROOT / "infra/vault/config.hcl").read_text()
        self.assertIn("disable_mlock = false", prod)
        self.assertIn("tls_disable   = 0", prod.replace("\t", " "))
        self.assertIn("tls_cert_file", prod)
        self.assertIn("disable_mlock = true", lab)
        self.assertIn("tls_disable = 1", lab)
        compose = (ROOT / "docker-compose.vault.yml").read_text()
        self.assertIn("vault-tls", compose)
        self.assertIn("config.prod.hcl", compose)
        self.assertIn('profiles: ["tls"]', compose)


class ProductionSplitTests(SimpleTestCase):
    def test_reusable_frontend_workflow_extracted(self):
        reusable = ROOT / ".github/workflows/reusable-test-frontend.yml"
        self.assertTrue(reusable.is_file())
        body = reusable.read_text()
        self.assertIn("workflow_call", body)
        self.assertIn("npm ci && npm run build", body)
        prod = (ROOT / ".github/workflows/production.yml").read_text()
        self.assertIn("uses: ./.github/workflows/reusable-test-frontend.yml", prod)
        # Inline steps for test-frontend should be gone from production.yml
        self.assertNotIn("cache-dependency-path: frontend/package-lock.json", prod)
