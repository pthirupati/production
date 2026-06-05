#!/usr/bin/env python
"""
Create or sync the production superuser from environment variables.
Never hardcode credentials in source control.
"""
import os
import sys

# Scripts live at /scripts but Django project is at /app
sys.path.insert(0, "/app")
os.chdir("/app")

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

USERNAME = os.environ.get("SUPERUSER_USERNAME", "admin")
EMAIL = os.environ.get("SUPERUSER_EMAIL", "admin@fixitlab.com")
PASSWORD = os.environ.get("SUPERUSER_PASSWORD", "")
SYNC_PASSWORD = os.environ.get("SUPERUSER_SYNC_PASSWORD", "1") == "1"


def main():
    if not EMAIL:
        print("[superuser] SUPERUSER_EMAIL not set — skipping")
        return

    if not PASSWORD:
        print("[superuser] SUPERUSER_PASSWORD not set — skipping")
        return

    if len(PASSWORD) < 8:
        print("[superuser] SUPERUSER_PASSWORD must be at least 8 characters")
        sys.exit(1)

    user = User.objects.filter(email=EMAIL).first()
    if not user:
        user = User.objects.filter(username=USERNAME).first()

    if user:
        changed = False
        if not user.is_superuser:
            user.is_superuser = True
            changed = True
        if not user.is_staff:
            user.is_staff = True
            changed = True
        if SYNC_PASSWORD and not user.check_password(PASSWORD):
            user.set_password(PASSWORD)
            changed = True
            print(f"[superuser] Password synced for {user.email}")
        if changed:
            user.save()
            print(f"[superuser] Updated existing user {user.username}")
        else:
            print(f"[superuser] User {user.email} already up to date")
        return

    user = User.objects.create_superuser(
        username=USERNAME,
        email=EMAIL,
        password=PASSWORD,
    )
    print(f"[superuser] Created {user.username} ({user.email})")


if __name__ == "__main__":
    main()
