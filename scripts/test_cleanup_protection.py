#!/usr/bin/env python3
"""
Regression test for cleanup-test-data.py PROTECTION logic (no Django required).

Run: python3 scripts/test_cleanup_protection.py

Loads protected_reason() + is_test_user() from the real cleanup script with the
import-time django.setup() side effects stubbed out, then asserts the core
invariant: a superuser / staff / configured-admin account is NEVER classified as
a deletable test user — even if its username/email looks test-like.

This complements the in-script HARD SAFETY GATE (which re-queries the DB and aborts
the whole cleanup if any privileged account is in the delete set).
"""
import importlib.util
import os
import pathlib
import sys
import types


def _load_cleanup_module():
    # Stub the Django modules the script imports at top level so import succeeds
    # off-Django (the predicate functions under test are pure Python).
    django = types.ModuleType("django")
    django.setup = lambda: None
    sys.modules["django"] = django

    sys.modules["django.contrib"] = types.ModuleType("django.contrib")
    auth = types.ModuleType("django.contrib.auth")
    auth.get_user_model = lambda: object
    sys.modules["django.contrib.auth"] = auth

    sys.modules["django.db"] = types.ModuleType("django.db")
    models = types.ModuleType("django.db.models")

    class _Q:  # placeholder; not exercised by the pure predicates
        def __init__(self, **kwargs):
            pass

    models.Q = _Q
    sys.modules["django.db.models"] = models

    sys.modules["django.core"] = types.ModuleType("django.core")
    cache_mod = types.ModuleType("django.core.cache")
    cache_mod.cache = types.SimpleNamespace(delete=lambda *a, **k: None)
    sys.modules["django.core.cache"] = cache_mod

    # PROTECTED_EMAIL is read at import time.
    os.environ["SUPERUSER_EMAIL"] = "admin@fixitlab.in"

    path = pathlib.Path(__file__).with_name("cleanup-test-data.py")
    spec = importlib.util.spec_from_file_location("cleanup_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _User:
    def __init__(self, username, email, is_superuser=False, is_staff=False):
        self.username = username
        self.email = email
        self.is_superuser = is_superuser
        self.is_staff = is_staff


def main() -> int:
    mod = _load_cleanup_module()

    cases = [
        # (user, expect_protected, expect_is_test_user)
        (_User("admin", "admin@fixitlab.in"), True, False),                    # PROTECTED_EMAIL
        (_User("root", "root@company.com", is_superuser=True), True, False),   # superuser
        (_User("ops", "ops@company.com", is_staff=True), True, False),         # staff
        (_User("e2e-1234", "e2e-1234@fixitlab-test.local"), False, True),      # real test user
        (_User("labval_x", "labval_x@example.com"), False, True),              # test prefix
        (_User("alice", "alice@gmail.com"), False, False),                     # normal user
        # Privileged AND test-looking → must stay PROTECTED:
        (_User("e2e-admin", "e2e-admin@company.com", is_superuser=True), True, False),
        # Superuser on the test domain is an intentional test fixture (not protected):
        (_User("e2e-su", "e2e-su@fixitlab-test.local", is_superuser=True), False, True),
    ]

    for user, want_protected, want_test in cases:
        reason = mod.protected_reason(user)
        is_test = mod.is_test_user(user)
        assert bool(reason) == want_protected, (
            f"protected_reason({user.username})={reason!r} expected truthy={want_protected}"
        )
        assert is_test == want_test, (
            f"is_test_user({user.username})={is_test} expected {want_test}"
        )
        # CORE INVARIANT: a protected account is never a deletion candidate.
        if reason:
            assert is_test is False, f"PROTECTED {user.username} must not be deletable"

    print(f"cleanup protection tests PASS ({len(cases)} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
