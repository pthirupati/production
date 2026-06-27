"""Production settings shim.

The canonical settings live in ``config.settings``, which already:
  * reads ``.env.production`` (falling back to ``.env``), and
  * injects all secrets from Vault via ``config.vault_loader.load_vault_secrets``
    (AppRole → KV ``secret/fixitlab/config``) before any ``env()`` call.

Some deploy/.env profiles set ``DJANGO_SETTINGS_MODULE=config.settings_production``.
This module makes that reference valid by re-exporting the canonical settings, so
the app boots identically and every secret/env still comes from Vault as usual.
Prefer ``DJANGO_SETTINGS_MODULE=config.settings`` directly (see env.production.example).
"""

from config.settings import *  # noqa: F401,F403
