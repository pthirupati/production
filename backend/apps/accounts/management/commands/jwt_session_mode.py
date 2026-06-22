"""
Toggle JWT session enforcement on the LIVE backend WITHOUT a restart.

Why this exists
---------------
The post-deploy E2E suite logs in many parallel test users. Historically CI
disabled session enforcement by rewriting JWT_SESSION_ENFORCEMENT in
.env.production and RESTARTING the production backend (twice per deploy). That
restart + enforcement flip is exactly what logged real users out and surfaced a
"server error" popup mid-deploy.

This command instead flips a RUNTIME override stored in the shared cache (Redis),
which the auth layer (`common.security.session_enforcement_enabled`) consults on
every request. No container restart, no .env mutation, no disruption to live
sessions — and the override carries a safety TTL so a forgotten "disable"
self-heals.

Usage:
    python manage.py jwt_session_mode disable   # turn enforcement OFF (E2E)
    python manage.py jwt_session_mode enable     # turn enforcement ON
    python manage.py jwt_session_mode clear      # remove override (use static setting)
    python manage.py jwt_session_mode status      # print current effective state
"""
from django.core.management.base import BaseCommand, CommandError

from common.security import (
    set_session_enforcement_override,
    session_enforcement_enabled,
)


class Command(BaseCommand):
    help = "Toggle the runtime JWT session-enforcement override (no restart)."

    def add_arguments(self, parser):
        parser.add_argument(
            "mode",
            choices=["disable", "enable", "clear", "status"],
            help="disable | enable | clear | status",
        )

    def handle(self, *args, **options):
        mode = options["mode"]

        if mode == "disable":
            set_session_enforcement_override(False)
            self.stdout.write(self.style.SUCCESS("JWT session enforcement DISABLED (runtime override, no restart)"))
        elif mode == "enable":
            set_session_enforcement_override(True)
            self.stdout.write(self.style.SUCCESS("JWT session enforcement ENABLED (runtime override, no restart)"))
        elif mode == "clear":
            set_session_enforcement_override(None)
            self.stdout.write(self.style.SUCCESS("JWT session enforcement override CLEARED (falls back to settings)"))
        elif mode == "status":
            effective = session_enforcement_enabled()
            self.stdout.write(f"JWT session enforcement effective state: {'ON' if effective else 'OFF'}")
        else:  # pragma: no cover - choices guard
            raise CommandError(f"Unknown mode: {mode}")
