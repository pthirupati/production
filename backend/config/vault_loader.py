"""
Vault secret loader — injects Vault KV secrets into os.environ at Django startup.

Called from settings.py right after the .env file is read. If VAULT_ENABLED is
not set or Vault is unreachable, this is a no-op and env vars are used as-is.

Auth method: AppRole (VAULT_ROLE_ID + VAULT_SECRET_ID from env or .env file).
Secrets path: VAULT_KV_PATH (default: secret/fixitlab/config, KV v2).
"""

import logging
import os

logger = logging.getLogger(__name__)

_VAULT_LOADED = False


def load_vault_secrets() -> None:
    """
    Fetch secrets from Vault and inject them into os.environ.

    Existing env vars are NOT overwritten — Vault fills in only keys that are
    absent or empty, so explicit docker / CI overrides always win.

    Set VAULT_OVERRIDE=1 to reverse priority (Vault values win over env file).
    """
    global _VAULT_LOADED
    if _VAULT_LOADED:
        return

    vault_enabled = os.environ.get("VAULT_ENABLED", "").lower() in ("1", "true", "yes", "on")
    if not vault_enabled:
        return

    role_id = os.environ.get("VAULT_ROLE_ID", "").strip()
    secret_id = os.environ.get("VAULT_SECRET_ID", "").strip()
    if not role_id or not secret_id:
        logger.warning("Vault: VAULT_ENABLED=true but VAULT_ROLE_ID/VAULT_SECRET_ID not set — skipping")
        return

    vault_addr = os.environ.get("VAULT_ADDR", "http://vault:8200")
    kv_path = os.environ.get("VAULT_KV_PATH", "secret/fixitlab/config")
    vault_override = os.environ.get("VAULT_OVERRIDE", "").lower() in ("1", "true", "yes")

    try:
        import hvac  # pip install hvac

        client = hvac.Client(url=vault_addr, timeout=5)

        # AppRole login
        login_resp = client.auth.approle.login(role_id=role_id, secret_id=secret_id)
        client.token = login_resp["auth"]["client_token"]

        # Parse KV v2 path: first segment is mount point, rest is secret path
        parts = kv_path.split("/", 1)
        mount = parts[0] if len(parts) > 1 else "secret"
        path = parts[1] if len(parts) > 1 else kv_path

        secret_resp = client.secrets.kv.v2.read_secret_version(
            path=path,
            mount_point=mount,
            raise_on_deleted_version=True,
        )
        secrets: dict = secret_resp["data"]["data"]

        injected = 0
        for key, value in secrets.items():
            if value is None:
                continue
            str_value = str(value)
            if vault_override or not os.environ.get(key):
                os.environ[key] = str_value
                injected += 1

        _VAULT_LOADED = True
        logger.info("Vault: injected %d secrets from %s (override=%s)", injected, kv_path, vault_override)

    except ImportError:
        logger.error("Vault: hvac package not installed — add hvac to requirements.txt")
    except Exception as exc:
        logger.warning("Vault: could not load secrets (%s: %s) — falling back to env file", type(exc).__name__, exc)
