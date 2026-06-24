"""
Vault secret loader — injects Vault KV secrets into os.environ at Django startup.

Called from settings.py right after the .env file is read. If VAULT_ENABLED is
not set or Vault is unreachable, this is a no-op and env vars are used as-is.

Auth method: AppRole (VAULT_ROLE_ID + VAULT_SECRET_ID from env or .env file).
Secrets path: VAULT_KV_PATH (default: secret/fixitlab/config, KV v2).
"""

import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_VAULT_LOADED = False
_VAULT_LAST_PROBE: Optional[Dict[str, Any]] = None


def vault_api_reachable(timeout: int = 3) -> bool:
    """Lightweight Vault health probe for readiness checks."""
    global _VAULT_LAST_PROBE
    now = time.time()
    if _VAULT_LAST_PROBE and now - _VAULT_LAST_PROBE.get("ts", 0) < 30:
        return bool(_VAULT_LAST_PROBE.get("ok"))

    vault_enabled = os.environ.get("VAULT_ENABLED", "").lower() in ("1", "true", "yes", "on")
    if not vault_enabled:
        _VAULT_LAST_PROBE = {"ts": now, "ok": False}
        return False

    vault_addr = os.environ.get("VAULT_ADDR", "http://vault:8200")
    if "127.0.0.1" in vault_addr and os.path.exists("/.dockerenv"):
        vault_addr = "http://vault:8200"

    ok = False
    try:
        import urllib.request

        req = urllib.request.Request(
            f"{vault_addr.rstrip('/')}/v1/sys/health?standbyok=true&sealedcode=200&uninitcode=200",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ok = 200 <= resp.status < 500
    except Exception:
        try:
            import hvac

            client = hvac.Client(url=vault_addr, timeout=timeout)
            ok = client.sys.is_initialized() and not client.sys.is_sealed()
        except Exception:
            ok = False

    _VAULT_LAST_PROBE = {"ts": now, "ok": ok}
    return ok


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
    if "127.0.0.1" in vault_addr and os.path.exists("/.dockerenv"):
        vault_addr = "http://vault:8200"
    kv_path = os.environ.get("VAULT_KV_PATH", "secret/fixitlab/config")
    vault_override = os.environ.get("VAULT_OVERRIDE", "").lower() in ("1", "true", "yes")
    max_attempts = int(os.environ.get("VAULT_STARTUP_RETRIES", "3") or "3")

    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            import hvac

            client = hvac.Client(url=vault_addr, timeout=5)
            login_resp = client.auth.approle.login(role_id=role_id, secret_id=secret_id)
            client.token = login_resp["auth"]["client_token"]

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
            os.environ["VAULT_SECRETS_LOADED"] = "1"
            logger.info(
                "Vault: injected %d secrets from %s (override=%s, attempt=%d)",
                injected, kv_path, vault_override, attempt,
            )
            return

        except ImportError:
            logger.error("Vault: hvac package not installed — add hvac to requirements.txt")
            return
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts:
                delay = attempt * 2
                logger.warning(
                    "Vault: load attempt %d/%d failed (%s) — retry in %ds",
                    attempt, max_attempts, exc, delay,
                )
                time.sleep(delay)
            else:
                logger.warning(
                    "Vault: could not load secrets after %d attempts (%s) — using env file / cached secrets",
                    max_attempts, last_exc,
                )
                if os.environ.get("VAULT_SECRETS_LOADED") == "1":
                    _VAULT_LOADED = True
                    logger.info("Vault: continuing with previously loaded secrets (VAULT_SECRETS_LOADED=1)")
