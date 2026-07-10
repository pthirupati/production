"""Vault secret-rotation refresh: re-reads Vault into the process, Vault wins,
fail-safe on error. Mocks hvac so it runs fully offline."""

import os
from unittest import mock

from django.test import SimpleTestCase

from config import vault_loader


def _base_env(**extra):
    return {
        "VAULT_ENABLED": "true",
        "VAULT_ROLE_ID": "role",
        "VAULT_SECRET_ID": "secret",
        "VAULT_ADDR": "http://vault:8200",
        **extra,
    }


def _fake_client(secrets):
    client = mock.MagicMock()
    client.auth.approle.login.return_value = {"auth": {"client_token": "tok"}}
    client.secrets.kv.v2.read_secret_version.return_value = {"data": {"data": secrets}}
    return client


class VaultRefreshTest(SimpleTestCase):
    def test_refresh_reinjects_rotated_values(self):
        secrets = {"SOME_API_KEY": "new-value", "SMTP_PASSWORD": "rotated"}
        with mock.patch.dict(os.environ, _base_env(SOME_API_KEY="old-value"), clear=False):
            with mock.patch("hvac.Client", return_value=_fake_client(secrets)):
                res = vault_loader.refresh_vault_secrets()
                # Vault value wins in-process during the call.
                self.assertEqual(os.environ.get("SOME_API_KEY"), "new-value")
        self.assertTrue(res["ok"])
        self.assertIn("SOME_API_KEY", res["updated"])
        self.assertIn("SMTP_PASSWORD", res["updated"])

    def test_refresh_is_failsafe_on_vault_error(self):
        with mock.patch.dict(os.environ, _base_env(), clear=False):
            with mock.patch("hvac.Client", side_effect=RuntimeError("vault sealed")):
                res = vault_loader.refresh_vault_secrets()
        self.assertFalse(res["ok"])
        self.assertEqual(res["updated"], [])

    def test_refresh_noop_when_vault_disabled(self):
        with mock.patch.dict(os.environ, {"VAULT_ENABLED": ""}, clear=False):
            res = vault_loader.refresh_vault_secrets()
        self.assertFalse(res["ok"])
        self.assertEqual(res["reason"], "vault_disabled")

    def test_refresh_requires_approle_credentials(self):
        with mock.patch.dict(os.environ, {"VAULT_ENABLED": "true", "VAULT_ROLE_ID": "", "VAULT_SECRET_ID": ""}, clear=False):
            res = vault_loader.refresh_vault_secrets()
        self.assertFalse(res["ok"])
        self.assertEqual(res["reason"], "missing_approle_credentials")
