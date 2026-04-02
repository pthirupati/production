#!/usr/bin/env python
"""
Create a superuser from environment variables.
Never hardcode credentials in source control.
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

USERNAME = os.environ.get("SUPERUSER_USERNAME", "admin")
EMAIL = os.environ.get("SUPERUSER_EMAIL", "admin@fixitlab.com")
PASSWORD = os.environ.get("SUPERUSER_PASSWORD")

if not PASSWORD:
    print("❌ SUPERUSER_PASSWORD environment variable is required")
    print("   Set it in .env or pass it directly:")
    print("   SUPERUSER_PASSWORD=MySecurePass123 python scripts/create_superuser.py")
    exit(1)

if len(PASSWORD) < 8:
    print("❌ Password must be at least 8 characters")
    exit(1)

if not User.objects.filter(username=USERNAME).exists() and not User.objects.filter(email=EMAIL).exists():
    User.objects.create_superuser(
        username=USERNAME,
        email=EMAIL,
        password=PASSWORD
    )
    print(f"✅ Superuser '{USERNAME}' created")
elif User.objects.filter(email=EMAIL).exists():
    user = User.objects.filter(email=EMAIL).first()
    changed = False
    if not user.is_superuser:
        user.is_superuser = True
        changed = True
    if not user.is_staff:
        user.is_staff = True
        changed = True
    if changed:
        user.save()
        print(f"ℹ️  Existing user '{user.username}' promoted to superuser + staff")
    else:
        print(f"ℹ️  Superuser with email '{EMAIL}' already exists")
else:
    user = User.objects.filter(username=USERNAME).first()
    if user and (not user.is_superuser or not user.is_staff):
        user.is_superuser = True
        user.is_staff = True
        user.save()
        print(f"ℹ️  Existing user '{USERNAME}' promoted to superuser + staff")
    else:
        print(f"ℹ️  Superuser '{USERNAME}' already exists")

