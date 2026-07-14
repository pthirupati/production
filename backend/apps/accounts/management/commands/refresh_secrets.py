"""Re-read secrets from Vault into the running process after a rotation.

Usage (owner/ops, after rotating a secret in Vault):
    python manage.py refresh_secrets

Re-injects rotated values into os.environ (Vault wins) and re-derives the JWT
keys so most secrets take effect without a restart. Values baked into Django
settings at import time still need a rolling restart — run this first, then
restart if the report says a JWT/import-time secret changed. Fail-safe: a Vault
error leaves the current secrets untouched.
"""

from django.core.management.base import BaseCommand

from config.vault_loader import refresh_vault_secrets


class Command(BaseCommand):
    help = "Re-read secrets from Vault (after rotation) and update the running process."

    def handle(self, *args, **options):
        result = refresh_vault_secrets()
        if not result["ok"]:
            self.stderr.write(self.style.WARNING(
                f"Vault refresh did not run: {result.get('reason')} "
                "(secrets left unchanged)."
            ))
            return
        updated = result["updated"]
        if not updated:
            self.stdout.write(self.style.SUCCESS("Vault refresh: no rotated secrets — already up to date."))
            return
        self.stdout.write(self.style.SUCCESS(
            f"Vault refresh: updated {len(updated)} secret(s): {', '.join(sorted(updated))}"
        ))
        jwt_keys = {"JWT_RSA_PRIVATE_KEY", "JWT_RSA_PUBLIC_KEY", "JWT_HS256_SECRET", "DJANGO_SECRET_KEY"}
        if set(updated) & jwt_keys:
            self.stdout.write("JWT keys were re-derived in-process. For a guaranteed cluster-wide "
                              "rollover, do a rolling restart of the backend.")
